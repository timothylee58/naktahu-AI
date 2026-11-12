#!/bin/sh
# Workers share one metrics directory so /metrics reports all of them, not just
# whichever worker answers the scrape (see app/core/prometheus_metrics.py).
# Exported before uvicorn starts because prometheus_client reads it at import.
# Wiped on every start: stale files from a previous run would be re-counted.
export PROMETHEUS_MULTIPROC_DIR="${PROMETHEUS_MULTIPROC_DIR:-/tmp/naktahu_prometheus}"
rm -rf "$PROMETHEUS_MULTIPROC_DIR"
mkdir -p "$PROMETHEUS_MULTIPROC_DIR"

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 2 --no-access-log
