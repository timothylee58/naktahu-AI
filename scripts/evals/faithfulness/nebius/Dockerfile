# Runner image for the faithfulness-judge calibration job (CPU only).
# Build from the REPOSITORY ROOT:
#   docker build -f scripts/evals/faithfulness/nebius/Dockerfile -t naktahu-faithfulness-pilot .
# NOT BUILT OR RUN where this was written (no Docker daemon in that sandbox).
FROM python:3.11.9-slim
WORKDIR /app
# httpx is the only third-party dependency of the pilot (the JEV client).
RUN pip install --no-cache-dir "httpx>=0.28,<0.29"
COPY scripts/evals scripts/evals
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1
ENTRYPOINT ["bash", "/app/scripts/evals/faithfulness/nebius/entrypoint.sh"]
