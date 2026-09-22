# Official Prometheus image — no third-party template, no unverified
# maintainer. Entrypoint overridden to substitute METRICS_AUTH_TOKEN into
# the scrape config at container start (see docker-entrypoint.sh) so the
# API service's bearer token never lands in the image or this repo.
FROM prom/prometheus:v3.0.1

COPY prometheus.yml.template /etc/prometheus/prometheus.yml.template
COPY docker-entrypoint.sh /docker-entrypoint.sh

USER root
RUN chmod +x /docker-entrypoint.sh
USER nobody

ENTRYPOINT ["/docker-entrypoint.sh"]
