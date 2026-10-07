-- 029_history_title.sql
-- The sidebar/history "Rename"/"Delete" context menu was pure UI — no
-- backend endpoint or field backed it. Delete only needs a row id (already
-- the existing uuid PK, just wasn't selected/returned before); rename needs
-- somewhere to store the custom label without overwriting the original
-- query/response_summary.

ALTER TABLE user_sessions
    ADD COLUMN IF NOT EXISTS title text;
