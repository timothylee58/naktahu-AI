# Observability stack — self-hosted Prometheus + Grafana on Railway

Two Railway services, deployed from this directory, that make the metrics
already emitted at `GET /metrics` (`apps/api/app/core/prometheus_metrics.py`)
queryable and alertable. Neither existed before this change — the endpoint
was live but nothing scraped it.

```
infra/observability/
├── prometheus/
│   ├── Dockerfile          FROM prom/prometheus, bakes in prometheus.yml
│   └── prometheus.yml      scrapes @naktahu-ai over Railway private networking
└── grafana/
    ├── Dockerfile          FROM grafana/grafana, bakes in provisioning/ + dashboards/
    ├── dashboards/
    │   └── naktahu-overview.json
    └── provisioning/
        ├── datasources/prometheus.yml   points at the Prometheus service, private network
        ├── dashboards/dashboard.yml     tells Grafana to load dashboards/*.json
        └── alerting/rules.yml           3 provisioned alert rules (see below)
```

## Why two new services instead of a SaaS

Chosen over Grafana Cloud / Better Stack because it needs no new third-party
account — both images are official (`prom/prometheus`, `grafana/grafana`),
deployed the same way `apps/api` already deploys (Dockerfile + Railway
private networking), and stay inside the existing Railway project. The
tradeoff, stated plainly: this repo now owns two more services to patch and
keep running, where a SaaS free tier would have owned that instead.

## Networking

Both services talk to each other over Railway's private network
(`*.railway.internal`), never the public internet:

- Prometheus scrapes `naktahu-ai.railway.internal:8080/metrics` — the API
  service's actual private endpoint and port, read from its live Railway
  config, not guessed.
- Grafana's datasource points at `http://prometheus.railway.internal:9090`.
- Only Grafana gets a public Railway domain, so dashboards are reachable but
  Prometheus's raw (unauthenticated) query API is not exposed publicly.

## Alert rules — provisioned but not yet wired to notify anyone

`provisioning/alerting/rules.yml` ships three rules, each named after the
specific gap it closes (see the file's own comments for the exact PromQL and
why that threshold):

1. **ILMU fallback rate high** — `naktahu_provider_fallback_total` rate above
   0.1 req/s for 5m. Catches ILMU degrading silently while Claude fallback
   quietly absorbs the cost.
2. **Circuit breaker open** — any `naktahu_circuit_breaker_state` > 0 for 2m.
3. **Retrieval confidence degraded** — median `naktahu_retrieval_score` below
   0.6 for 10m, the same number `analyst_node`'s own `needs_clarification`
   gate uses, so this alert fires exactly when real users are seeing that
   degraded experience at volume.

These rules evaluate and will show as firing/pending in Grafana's Alerting UI
on their own. They will NOT page or email anyone until a contact point is
configured (Grafana Alerting → Contact points) with a real destination —
email needs SMTP credentials this repo doesn't have anywhere, a Slack/Discord
webhook needs a URL only the user can generate. That's the one manual step
left; everything else here is live.

## Manual steps for whoever deploys this

1. The Grafana admin password is set once as the Railway variable
   `GF_SECURITY_ADMIN_PASSWORD` at service-creation time (never hardcoded
   here, never committed) — rotate it after first login.
2. Configure a Grafana contact point (see above) to make the three alert
   rules actually notify someone.
3. `RAILWAY_ENVIRONMENT`/`RAILWAY_PROJECT_ID`/etc. are unused by these two
   services — they need no secrets from the API service's own variable set.
