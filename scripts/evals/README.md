# Offline eval metrics

## `temporal_accuracy` — chunk currency ("is this chunk current as of today?")

RAGAS **faithfulness** only measures *answer-to-chunk* consistency, never
*chunk-to-reality* accuracy. A stale chunk reproduced perfectly scores 1.0
faithful while being factually wrong:

```
EPF Budget 2023: withdrawal cap = RM1,000   ← old chunk, still in corpus
Budget 2024:     withdrawal cap = RM500      ← new rule
stale-only corpus → answer says RM1,000 → faithfulness 1.0 → silently wrong
```

`temporal_accuracy` is the missing metric. It scores each retrieved chunk's
**currency** from its metadata (`effective_date` / `superseded_by` — the same
columns `analyst_node` enforces, migrations 007/008), so an eval gate can catch
stale-but-faithful answers. It is deterministic (no LLM call).

### Scoring rubric (per chunk)

| condition | score |
|---|---|
| `superseded_by` set (a newer version exists) | `0.0` (hard fail) |
| no `effective_date` metadata | `0.5` (unknown, risky) |
| not yet in effect, or within the domain window | `1.0` |
| within 2× the domain window | `0.6` |
| older | linear decay `1 - days/(4×window)`, floored at `0.1` |

Recency window by domain: **180 days** for strict policy domains
(`tax`, `epf`, `immigration`), **365 days** otherwise.

Per answer, the metric takes the **minimum** across the chunks used — an answer
can be no more current than the least-current source it cites.

### Usage

```python
from scripts.evals.temporal_scorer import (
    score_temporal_accuracy,       # single chunk
    aggregate_temporal_accuracy,   # worst-case over an answer's chunks
    temporal_accuracy,             # RAGAS-style metric object (name/score/passes)
    TEMPORAL_ACCURACY_GATE,        # default pass bar (0.6)
)

# single chunk
score_temporal_accuracy(effective_date, superseded_by, domain="epf")

# per-answer sample (contexts RAGAS already carries per row)
sample = {"domain": "epf", "retrieved_chunks": [chunk_a, chunk_b]}  # dicts or ChunkResult-like
temporal_accuracy.score(sample)       # 0.0–1.0
temporal_accuracy.passes(sample)      # bool, score >= gate
```

`aggregate_temporal_accuracy` reads `effective_date` / `superseded_by` (and an
optional per-chunk `domain`) from either dicts or objects (e.g.
`app.services.vector_store.ChunkResult`), so the same retrieved chunks the
pipeline returns can be scored directly.

### Registering with RAGAS (optional)

RAGAS is not a project dependency (the scorer is pure-Python). If you add it, a
custom metric is a thin wrapper — the currency logic stays here:

```python
from ragas.metrics.base import Metric
from scripts.evals.temporal_scorer import aggregate_temporal_accuracy

class TemporalAccuracy(Metric):
    name = "temporal_accuracy"
    # map each RAGAS sample's retrieved contexts' metadata → aggregate_temporal_accuracy(...)
```

### Running

```bash
PYTHONPATH=. pytest scripts/evals/ -q
```

See also `apps/api/evals/test_freshness.py`, which gates `analyst_node`'s
runtime freshness behaviour (stale flagging, superseded hard-reject,
prefer-newest) — the metric here is the dataset-level scorer for the same axis.
