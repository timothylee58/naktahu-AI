# Official Grafana image. Provisioning files (datasource + dashboard loader
# + alert rules) and the dashboard JSON itself are baked in, so the service
# comes up fully configured on first boot with no manual UI clicking beyond
# setting the admin password (Railway env var, not baked in here).
FROM grafana/grafana:11.3.1

COPY provisioning /etc/grafana/provisioning
COPY dashboards /var/lib/grafana/dashboards
