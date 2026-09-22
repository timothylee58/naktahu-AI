# Official Prometheus image — no third-party template, no unverified
# maintainer. Its own ENTRYPOINT already reads /etc/prometheus/prometheus.yml
# and listens on 9090, so nothing else here needs overriding.
FROM prom/prometheus:v3.0.1

COPY prometheus.yml /etc/prometheus/prometheus.yml
