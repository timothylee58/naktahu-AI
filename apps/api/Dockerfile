# ── Stage 1: dependency builder ─────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

COPY pyproject.toml ./
RUN pip install --no-cache-dir --prefix=/install -e "." --no-build-isolation || \
    pip install --no-cache-dir --prefix=/install fastapi uvicorn[standard] \
    anthropic openai supabase redis langchain-core langchain \
    langchain-openai langchain-community langchain-anthropic langgraph \
    slowapi python-jose[cryptography] PyJWT[crypto] structlog \
    sentry-sdk[fastapi] pydantic-settings "weasyprint>=63.0"

# ── Stage 2: production image ────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Native libraries for WeasyPrint (PDF generation in app/agents/tools.py).
# python:3.11-slim ships none of them, and without them `import weasyprint`
# raises OSError at runtime; generate_pdf then fails closed (no PDF, no URL).
#   libpango-1.0-0, libpangoft2-1.0-0, libharfbuzz0b, libfontconfig1:
#     text layout and font lookup, dlopen()ed by weasyprint/text/ffi.py
#   libharfbuzz-subset0: optional (WeasyPrint falls back to fontTools without
#     it) but it is the documented Debian dependency and is tiny
#   fonts-dejavu-core: Latin/Malay glyphs
#   fonts-wqy-microhei: Chinese glyphs (reports can be in zh). About 5 MB
#     installed (Debian Installed-Size), versus about 91 MB for fonts-noto-cjk,
#     which looks better but costs image size and pull time. Swap it in if
#     typography matters more than size.
# apt lists are removed in the same layer so they never reach the image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libharfbuzz-subset0 \
        libfontconfig1 \
        fonts-dejavu-core \
        fonts-wqy-microhei \
    && rm -rf /var/lib/apt/lists/*

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
COPY scripts/ ./scripts/

COPY start.sh ./
RUN chmod +x start.sh

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENV=production \
    PYTHONPATH=/app

CMD ["./start.sh"]
