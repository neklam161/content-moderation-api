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

