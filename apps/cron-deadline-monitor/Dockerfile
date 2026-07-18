# Deadline Monitor cron — reuses API image layout (PYTHONPATH=/app).
FROM python:3.11-slim AS builder

WORKDIR /build

COPY api/pyproject.toml ./
RUN pip install --no-cache-dir --prefix=/install -e "." --no-build-isolation || \
    pip install --no-cache-dir --prefix=/install fastapi uvicorn[standard] \
    anthropic openai supabase redis langchain-core langchain \
    langchain-openai langchain-community langchain-anthropic langgraph \
    langgraph-checkpoint-postgres slowapi python-jose[cryptography] PyJWT[crypto] structlog \
    sentry-sdk[fastapi] pydantic-settings httpx

FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /install /usr/local

COPY api/main.py api/pyproject.toml ./
COPY api/app/ ./app/
COPY api/core/ ./core/
COPY api/middleware/ ./middleware/
COPY api/rag/ ./rag/
COPY api/routers/ ./routers/
COPY api/routes/ ./routes/
COPY api/services/ ./services/
COPY api/scripts/ ./scripts/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENV=production \
    PYTHONPATH=/app

CMD ["python", "scripts/agents/deadline_monitor.py"]
