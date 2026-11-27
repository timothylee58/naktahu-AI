-- 063_policy_watch_items.sql
--
-- Review queue for the policy watcher (apps/api/scripts/policy_watch.py).
--
-- What it fixes: ingestion sources were a fixed URL list re-read weekly, so a
-- new circular, statement or policy page on a ministry or state site was never
-- noticed. The watcher reads listing pages (press statements, circulars,
-- announcements), and every link it has not seen before lands here for a human
-- to approve or reject. Nothing in this table reaches document_chunks, so
-- nothing here can change a live answer.
--
-- Rows:
--   baseline  seen on the first scan of a target; recorded so the existing
--             back catalogue is not flooded into the review queue.
--   pending   new since the baseline; waiting for a reviewer.
--   approved  a reviewer accepted it (ingestion of approved items is a
--             separate, later step).
--   rejected  a reviewer dismissed it; it will not be queued again.
--
-- Access: service role only. RLS is enabled with deliberately NO policies, so
-- anon and authenticated roles are denied everything. This is an internal
-- operations table, not public content (unlike shared_answers), so it gets no
-- public SELECT policy.
--
-- The backend degrades gracefully until this is applied: the watcher prints the
-- items it found and the path of this file instead of failing.

create table if not exists policy_watch_items (
    id            uuid primary key default gen_random_uuid(),
    target_name   text not null check (char_length(target_name) between 1 and 80),
    item_url      text not null check (char_length(item_url) between 10 and 2048),
    title         text not null check (char_length(title) between 1 and 500),
    published_on  date,
    status        text not null default 'pending'
                  check (status in ('baseline', 'pending', 'approved', 'rejected')),
    first_seen_at timestamptz not null default now(),
    reviewed_at   timestamptz,
    review_note   text check (review_note is null or char_length(review_note) <= 500),
    constraint policy_watch_items_target_url_key unique (target_name, item_url)
);

create index if not exists policy_watch_items_status_seen_idx
    on policy_watch_items (status, first_seen_at desc);

alter table policy_watch_items enable row level security;
