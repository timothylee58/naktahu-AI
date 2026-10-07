-- 033_warung_checkin_price.sql
-- Adds an optional price report to warung_checkins, so the "Warung Watch
-- Price Visualizer" (price trend charts / state heatmaps) requested in the
-- product roadmap has a real, crowdsourced data source to chart instead of
-- fabricated sample numbers — see CLAUDE.md's "never render fabricated
-- data" principle, applied here to price/analytics UI rather than
-- citations. There is no government API for informal warung pricing, so
-- this is the only honest source: the existing check-in flow, extended.
--
-- Deliberately nullable and item-labelled rather than a single fixed
-- "price" column: a check-in reporting busyness status doesn't have to
-- also report a price, and different warungs sell different things (a
-- kopitiam's "nasi lemak" isn't comparable to a mamak's "roti canai") — a
-- free-text item label keeps this honest about what's actually being
-- compared, instead of implying a single canonical "price index" per
-- warung that doesn't exist.
--
-- Files touched in this same PR: this migration,
-- apps/api/services/warung_watch.py (create_checkin/get_status),
-- apps/api/routers/warung_watch.py (CheckinRequest), and the matching
-- frontend field in apps/web/src/app/warung-watch/page.tsx.

ALTER TABLE warung_checkins
    ADD COLUMN IF NOT EXISTS price_item  varchar(80),
    ADD COLUMN IF NOT EXISTS price_myr   numeric(6, 2) CHECK (price_myr IS NULL OR price_myr >= 0);

-- Both nullable together or both set together — a price without knowing
-- what it's for isn't chartable, and an item label without a price is
-- just noise. Enforced at the DB layer, not just in Pydantic, since this
-- table has no other write path than the FastAPI service today but the
-- constraint should hold even if that changes.
ALTER TABLE warung_checkins
    ADD CONSTRAINT warung_checkins_price_pair_chk
        CHECK ((price_item IS NULL) = (price_myr IS NULL));

-- Backs "price trend for this warung over time" and "recent price reports
-- across all warungs for the heatmap" — both scans filter on price_myr
-- IS NOT NULL first (most check-ins won't carry a price), so a partial
-- index only over priced rows stays small regardless of overall check-in
-- volume.
CREATE INDEX IF NOT EXISTS warung_checkins_priced_idx
    ON warung_checkins (warung_id, created_at DESC)
    WHERE price_myr IS NOT NULL;
