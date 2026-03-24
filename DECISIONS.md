# Architectural Decisions

Key design choices and the reasoning behind them. Written so reviewers and
future-me don't have to reverse-engineer intent from code.

---

## 1. Google Gemini (free tier) instead of Anthropic/OpenAI

Gemini 2.0 Flash has a generous free tier with no credit card required. For a
portfolio project that needs to actually run during review, that matters more
than marginal quality gains from GPT-4o.

Switching providers is an env var change: `LLM_PROVIDER=google`. The
abstraction in `llm_client.py` handles the rest — no code changes.

Latency on Flash is fast enough for synchronous calls at this scale.

In production I'd move to Anthropic or OpenAI for stronger safety guarantees
and SLA-backed uptime. But not yet.

---

## 2. Pydantic Settings instead of `os.getenv()`

If `RATE_LIMIT_RPM=abc` gets into the environment, I want the process to
refuse to start — not crash silently on the first request that hits the rate
limiter. `BaseSettings` gives you that for free.

Two other things that came for free: `SecretStr` fields never show up in logs
or tracebacks, and `@lru_cache` on `get_settings()` means the `.env` file gets
parsed exactly once per process.

The tradeoff is more boilerplate than `os.getenv()`. Worth it past the
prototype stage.

---

## 3. Lifespan context manager instead of `@app.on_event`

`@app.on_event("startup")` has been deprecated since FastAPI 0.93. The
lifespan pattern also makes the startup/shutdown pair obvious — both are
visible in the same function rather than split across two decorators.

It's also easier to test. You can pass a custom `lifespan` into `create_app()`
in test fixtures without patching globals.

---

## 4. App factory instead of a module-level `app`

Tests call `create_app(settings=test_settings)` to get an isolated instance
with test config. No module-level state to reset between tests, no
monkey-patching.

`uvicorn app.main:app` still works because `app = create_app()` sits at the
bottom of `main.py`. No operational cost.

---

## 5. In-memory rate limiter instead of Redis

Redis is the right call for multi-replica deployments. This isn't one yet.

For Phase 1 (single process), a process-level dict for the token bucket is
sufficient and removes an external dependency from the dev setup. The
`RateLimiter` class has a clean enough interface that swapping the backend
to Redis is isolated to `middleware/rate_limiter.py`.

That swap becomes necessary the moment there are two replicas behind a load
balancer — in-memory state is per-process, so a client can exceed limits by
hitting different instances.

---

## 6. Prompt as a `.txt` file instead of a Python string

Prompts are content. They should live in version control as plain text, not
embedded in a string assignment inside a Python file.

Keeping them separate means someone can improve the prompt without touching
Python. Versioning in the filename (`v1`, `v2`) makes it straightforward to
A/B test variants or roll back to a known-good version.

---

## 7. Bottlenecks at 1,000 req/s

Three things break first:

**In-memory rate limiter** — replace with a Redis cluster using a
Lua-scripted token bucket so state is shared across replicas.

**Synchronous LLM calls** — move to a request queue with async workers.
Allows back-pressure and retry budgets without blocking API threads.

**No response caching** — add a Redis semantic cache to short-circuit
identical or near-identical moderation requests.


## 8. Why async Python matters for this project

So every request to the moderation API makes a network call to the LLM provider. And that involve
waiting
This is why with `async/await`, the process can handle other requests while waiting for the LLM response
to arrive.

## 9. Why scores instead of binary flags from the LLM

The LLM returns a float score (0.0-1.0) per category rather than just
true/false. This was a deliberate design choice I initially didn't fully
understand.

Binary flags remove nuance:
```json
{"category": "spam", "flagged": true}   // is it 0.71 or 0.99?
```

Scores preserve it:
```json
{"category": "spam", "score": 0.71, "flagged": true}  // borderline
{"category": "spam", "score": 0.99, "flagged": true}  // definitive
```

The distinction matters for:
- Routing borderline cases to human review instead of auto-rejecting
- Tuning thresholds per category based on production data
- Explaining decisions to users who appeal a moderation decision
- Monitoring score distributions over time to detect model drift

The `flagged` field uses `score >= 0.7` as its threshold, but that threshold
is a starting point. In production, different categories warrant different
thresholds — toxicity should flag at 0.6 (protect users), off_topic at 0.8
(very subjective). The architecture separates scoring (LLM) from thresholding
(business logic) so thresholds can be tuned without touching the model.


## 10. `max_tokens` is a ceiling, not a spend
 
Setting `llm_max_tokens=1024` does not mean every request costs 1024 tokens.
The model is billed for tokens it actually generates — if the response is 180
tokens, you pay for 180 regardless of the cap.
 
The original default of 512 caused a real bug: the 4-category JSON response
with reason strings can exceed 200 tokens, and the model would hit the cap
mid-response and stop, producing truncated JSON that failed to parse. Every
request then exhausted all 3 retries, meaning 4 LLM calls instead of 1 — the
opposite of cost efficiency.
 
Raising the ceiling to 1024 fixed the truncation so setting `max_tokens` high enough that the model never gets cut off mid-response. The floor matters more than the ceiling.

## 13. How `classify()` connects to the rest of the system
 
`classify()` is a single method on `LLMClient` but it sits at the centre of
the entire moderation pipeline. Every request passes through it exactly once.
 
```
POST /moderate
      │
      ▼
ModerationService.moderate()
      │
      ├── InjectionDetector.detect()   ← pre-flight: is this a jailbreak attempt?
      │       if confidence >= 0.8 → raise InjectionError → 400 Bad Request
      │
      ├── LLMClient.classify(text)     ← the main event
      │       sends: system prompt + user text
      │       returns: raw string (ideally JSON, sometimes broken)
      │
      └── OutputValidator.validate()
              │
              ├── _parse(raw)          ← try to parse the raw string into a response
              │       success → return ModerationResponse
              │
              └── on failure → LLMClient.correct()   ← retry with full history
                      returns: better raw string
                      back to _parse() → success or LLMOutputError → 502
```
 
`classify()` itself does three things and nothing else:
 
```python
async def classify(self, text: str) -> str:
    # 1. Send the system prompt + user text to the LLM
    response = await self._client.chat.completions.create(
        messages=[
            {"role": "system", "content": self._system_prompt},
            {"role": "user",   "content": text},
        ]
    )
    # 2. Extract the raw string content
    return response.choices[0].message.content or ""
    # 3. If the SDK timed out, translate it to our own LLMTimeoutError
```
 
It doesn't parse. It doesn't validate. It doesn't retry. Those are
`OutputValidator`'s responsibilities. `classify()` has one job: talk to the
LLM and hand back whatever it said.
 
This separation matters because it keeps each class testable in isolation.
`test_llm_client.py` mocks the SDK and only tests the network call.
`test_output_validator.py` mocks `LLMClient` entirely and only tests parsing
and retry logic. Neither test needs a real API key or costs anything to run.
 
---


