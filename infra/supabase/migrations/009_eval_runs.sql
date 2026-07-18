-- 009_eval_runs.sql
-- Track eval-harness runs and their gate scores so deploys can be gated on
-- quality/freshness over time. avg_temporal_accuracy is the freshness gate
-- (chunk currency) that sits alongside the existing faithfulness gate —
-- faithfulness alone can't tell that a chunk is out of date.

CREATE TABLE IF NOT EXISTS eval_runs (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at            timestamptz NOT NULL DEFAULT now(),
    git_sha               text,
    faithfulness          numeric,   -- RAGAS faithfulness (answer-to-chunk)
    avg_temporal_accuracy numeric,   -- chunk currency (this migration's gate)
    passed                boolean NOT NULL DEFAULT false,
    scores                jsonb NOT NULL DEFAULT '{}'::jsonb,  -- full score dump
    notes                 text
);

-- Idempotent for a pre-existing eval_runs table (columns added if missing).
ALTER TABLE eval_runs
  ADD COLUMN IF NOT EXISTS faithfulness          numeric,
  ADD COLUMN IF NOT EXISTS avg_temporal_accuracy numeric,
  ADD COLUMN IF NOT EXISTS passed                boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS scores                jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS git_sha               text,
  ADD COLUMN IF NOT EXISTS notes                 text;

CREATE INDEX IF NOT EXISTS eval_runs_created_at ON eval_runs (created_at DESC);
