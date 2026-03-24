from __future__ import annotations

from pathlib import Path

import openai
from openai import AsyncOpenAI

from app.core.config import LLMProvider, Settings
from app.core.exceptions import LLMTimeoutError
from app.core.logging import get_logger

log = get_logger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self._model = settings.llm_model
        self._max_tokens = settings.llm_max_tokens
        self._timeout = settings.llm_timeout_seconds
        self._provider = settings.llm_provider.value
        self._system_prompt = (_PROMPTS_DIR / "moderation_v1.txt").read_text()

        base_url: str | None = None
        match settings.llm_provider:
            case LLMProvider.GOOGLE:
                base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            case LLMProvider.OLLAMA:
                base_url = "http://localhost:11434/v1"
            case LLMProvider.OPENAI:
                base_url = None

        self._client = AsyncOpenAI(
            api_key=settings.active_api_key.get_secret_value(),
            base_url=base_url,
            timeout=self._timeout,
        )

        log.info(
            "llm_client_initialized",
            model=self._model,
            provider=self._provider,
        )

    async def classify(self, text: str) -> str:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=self._max_tokens,
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": text},
                ],
            )
        except openai.APITimeoutError as exc:
            raise LLMTimeoutError(
                timeout_seconds=self._timeout,
                provider=self._provider,
            ) from exc
        except openai.APIStatusError as exc:
            log.error(
                "llm_api_error",
                status_code=exc.status_code,
                provider=self._provider,
            )
            raise

        raw = response.choices[0].message.content or ""
        log.debug("llm_response_received", raw_length=len(raw))
        return raw

    async def correct(self, original_text: str, bad_output: str, parse_error: str) -> str:

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=self._max_tokens,
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": original_text},
                    {"role": "assistant", "content": bad_output},  # what it produced
                    {
                        "role": "user",
                        "content": (
                            f"Your response could not be parsed as JSON.\n"
                            f"Error: {parse_error}\n\n"
                            "Return ONLY a valid JSON object matching the required schema. "
                            "No markdown, no code fences, no explanation."
                        ),
                    },
                ],
            )
        except openai.APITimeoutError as exc:
            raise LLMTimeoutError(
                timeout_seconds=self._timeout,
                provider=self._provider,
            ) from exc
        except openai.APIStatusError as exc:
            log.error(
                "llm_api_error_on_correction",
                status_code=exc.status_code,
                provider=self._provider,
            )
            raise

        raw = response.choices[0].message.content or ""
        log.debug("llm_correction_received", raw_length=len(raw))
        return raw
