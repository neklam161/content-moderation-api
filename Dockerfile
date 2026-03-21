FROM python:3.12-slim AS builder

WORKDIR /app

COPY pyproject.toml ./

RUN python -m venv /app/venv && \
    /app/venv/bin/pip install --upgrade pip --no-cache-dir && \
    /app/venv/bin/pip install . --no-cache-dir

FROM python:3.12-slim AS runtime

RUN groupadd --system app && \
    useradd --system --gid app --no-create-home app

WORKDIR /app

COPY --from=builder /app/venv /app/venv

COPY app/ ./app/
COPY prompts/ ./prompts/

RUN chown -R app:app /app

USER app

ENV PATH="/app/venv/bin:$PATH"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" \
    || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
