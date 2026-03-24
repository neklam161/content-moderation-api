from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import openai
import pytest

from app.core.config import Environment, LLMProvider, Settings
from app.core.exceptions import LLMTimeoutError
from app.services.llm_client import LLMClient


@pytest.fixture
def settings() -> Settings:
    return Settings(
        llm_provider=LLMProvider.GOOGLE,
        openai_api_key="test-key",  # type: ignore[arg-type]
        llm_model="gemini-2.0-flash",
        environment=Environment.TEST,
    )


@pytest.fixture
def llm_client(settings: Settings) -> LLMClient:
    return LLMClient(settings)


# ── Helper ─────────────────────────────────────────────────────────────────────


def _make_completion(content: str) -> MagicMock:
    """Build a minimal mock that looks like an openai ChatCompletion response."""
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


# ── classify() ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_classify_returns_raw_content(llm_client: LLMClient) -> None:
    expected = '{"scores": []}'
    llm_client._client.chat.completions.create = AsyncMock(return_value=_make_completion(expected))

    result = await llm_client.classify("some text")

    assert result == expected


@pytest.mark.asyncio
async def test_classify_empty_content_returns_empty_string(llm_client: LLMClient) -> None:
    """If the model returns None content, classify() should return '' not crash."""
    choice = MagicMock()
    choice.message.content = None
    response = MagicMock()
    response.choices = [choice]

    llm_client._client.chat.completions.create = AsyncMock(return_value=response)

    result = await llm_client.classify("text")
    assert result == ""


@pytest.mark.asyncio
async def test_classify_raises_llm_timeout_on_api_timeout(llm_client: LLMClient) -> None:
    """
    This is the critical regression test for the original bug.

    The old code caught `TimeoutError` (built-in) which the openai SDK never raises.
    The SDK raises `openai.APITimeoutError`. This test would have caught the bug
    because it verifies the correct exception is re-raised as LLMTimeoutError.
    """
    llm_client._client.chat.completions.create = AsyncMock(
        side_effect=openai.APITimeoutError(request=MagicMock())
    )

    with pytest.raises(LLMTimeoutError) as exc_info:
        await llm_client.classify("some text")

    assert exc_info.value.context["provider"] == "google"


@pytest.mark.asyncio
async def test_classify_builtin_timeout_is_not_caught(llm_client: LLMClient) -> None:
    """
    Python's built-in TimeoutError should NOT be silently swallowed.
    If something other than the SDK raises it, we want it to propagate.
    """
    llm_client._client.chat.completions.create = AsyncMock(
        side_effect=TimeoutError("some other timeout")
    )

    # Should propagate as-is, not wrapped in LLMTimeoutError
    with pytest.raises(TimeoutError):
        await llm_client.classify("some text")


@pytest.mark.asyncio
async def test_classify_provider_in_timeout_error_matches_settings(
    settings: Settings,
) -> None:
    """Provider string in the exception must reflect actual settings, not be hardcoded."""
    client = LLMClient(settings)
    client._client.chat.completions.create = AsyncMock(
        side_effect=openai.APITimeoutError(request=MagicMock())
    )

    with pytest.raises(LLMTimeoutError) as exc_info:
        await client.classify("text")

    # This would have failed with the old hardcoded provider="google" if using Ollama
    assert exc_info.value.context["provider"] == settings.llm_provider.value


@pytest.mark.asyncio
async def test_classify_api_status_error_propagates(llm_client: LLMClient) -> None:
    """Non-timeout API errors (e.g. 401, 429) should propagate uncaught."""
    llm_client._client.chat.completions.create = AsyncMock(
        side_effect=openai.APIStatusError(
            "Unauthorized",
            response=MagicMock(status_code=401),
            body=None,
        )
    )

    with pytest.raises(openai.APIStatusError):
        await llm_client.classify("text")


# ── correct() ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_correct_sends_full_conversation_history(llm_client: LLMClient) -> None:
    """
    correct() must send original_text, bad_output, and the correction instruction
    as a multi-turn conversation — not as a fresh classify() call.
    """
    mock_create = AsyncMock(return_value=_make_completion('{"scores": []}'))
    llm_client._client.chat.completions.create = mock_create

    await llm_client.correct(
        original_text="Buy cheap meds",
        bad_output='{"scores": [broken',
        parse_error="Expecting value: line 1 column 14",
    )

    call_messages = mock_create.call_args.kwargs["messages"]

    roles = [m["role"] for m in call_messages]
    assert roles == ["system", "user", "assistant", "user"], (
        "correct() must send system + original user turn + bad assistant output "
        "+ correction instruction — not just a fresh user message"
    )

    # The bad output must appear as the assistant's prior turn
    assistant_turn = next(m for m in call_messages if m["role"] == "assistant")
    assert '{"scores": [broken' in assistant_turn["content"]


@pytest.mark.asyncio
async def test_correct_raises_llm_timeout_on_api_timeout(llm_client: LLMClient) -> None:
    llm_client._client.chat.completions.create = AsyncMock(
        side_effect=openai.APITimeoutError(request=MagicMock())
    )

    with pytest.raises(LLMTimeoutError):
        await llm_client.correct("text", "bad output", "parse error")


@pytest.mark.asyncio
async def test_correct_returns_raw_content(llm_client: LLMClient) -> None:
    fixed_json = '{"scores": [{"category": "spam", "score": 0.9, "flagged": true, "reason": "x"}]}'
    llm_client._client.chat.completions.create = AsyncMock(
        return_value=_make_completion(fixed_json)
    )

    result = await llm_client.correct("text", "broken", "json error")
    assert result == fixed_json
