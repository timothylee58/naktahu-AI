-- Fix a real race in services/redeem_codes.py: uses_count was incremented
-- via a Python read-then-write (`row.get("uses_count", 0) + 1`), where
-- `row` was fetched at the START of redeem_code(), before the atomic
-- redemption claim insert. Per-user double-redemption is correctly blocked
-- by the unique constraint on redeem_code_redemptions — this only matters
-- for a shared multi-use code redeemed concurrently by two DIFFERENT
-- users: both read the same stale count, both pass the max_uses check,
-- both win their own claim (different users, no conflict), both grant
-- credits, then both write uses_count from the same stale base — the
-- second write clobbers the first, so uses_count under-counts and
-- max_uses can be exceeded.
--
-- Same fix shape as add_agent_credits (migration 007): a single SQL
-- statement does the increment under Postgres's own row lock, so there's
-- no read-then-write window in application code at all.
CREATE OR REPLACE FUNCTION increment_redeem_code_uses(p_code_id uuid)
RETURNS void AS $$
BEGIN
    UPDATE redeem_codes
    SET uses_count = uses_count + 1
    WHERE id = p_code_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
