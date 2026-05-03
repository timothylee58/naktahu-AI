# ── Stage 1: dependency builder ─────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

COPY pyproject.toml ./
# Install only runtime dependencies into an isolated prefix
RUN pip install --no-cache-dir --prefix=/install -e "." 2>/dev/null || \
    pip install --no-cache-dir --prefix=/install \
        fastapi uvicorn[standard] python-dotenv "pydantic>=2.0" \
        anthropic openai supabase "redis[asyncio]" langchain-core \
        "langgraph>=0.2" langchain-anthropic slowapi \
        "python-jose[cryptography]" structlog "sentry-sdk[fastapi]"

# ── Stage 2: production image ────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY app/ ./app/

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENV=production

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--no-access-log"]
