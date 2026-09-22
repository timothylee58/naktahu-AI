#!/bin/sh
# Substitutes METRICS_AUTH_TOKEN into the scrape config's bearer credentials
# at container start, so the token lives only in a Railway env var and the
# runtime filesystem — never in the image or this repo. Uses sed (present
# in the official prom/prometheus base image), not envsubst, which that
# image does not ship.
set -eu

if [ -z "${METRICS_AUTH_TOKEN:-}" ]; then
  echo "docker-entrypoint.sh: METRICS_AUTH_TOKEN is not set — the naktahu-api" >&2
  echo "scrape job will send an empty bearer token and get 401'd. Set it as a" >&2
  echo "Railway variable on this service (same value as the API service's)." >&2
fi

sed "s|__METRICS_AUTH_TOKEN__|${METRICS_AUTH_TOKEN:-}|g" \
  /etc/prometheus/prometheus.yml.template > /etc/prometheus/prometheus.yml

exec /bin/prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/prometheus \
  --web.console.libraries=/usr/share/prometheus/console_libraries \
  --web.console.templates=/usr/share/prometheus/consoles
