# ── Stage 1: dependency builder ─────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

COPY pyproject.toml ./
RUN pip install --no-cache-dir --prefix=/install -e "." --no-build-isolation || \
    pip install --no-cache-dir --prefix=/install fastapi uvicorn[standard] \
    anthropic openai supabase redis langchain-core langchain \
    langchain-openai langchain-community langchain-anthropic langgraph \
    slowapi python-jose[cryptography] PyJWT[crypto] structlog \
    sentry-sdk[fastapi] pydantic-settings

# ── Stage 2: production image ────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy all source files
COPY main.py pyproject.toml ./
COPY app/ ./app/
COPY core/ ./core/
COPY middleware/ ./middleware/
COPY rag/ ./rag/
COPY routers/ ./routers/
COPY routes/ ./routes/
COPY services/ ./services/

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENV=production \
    PYTHONPATH=/app

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --no-access-log
