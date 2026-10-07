-- Product feedback (bugs / feature requests / general) — the dedicated
-- table apps/web/src/app/profile/page.tsx's "Give Feedback" card has been
-- pointing a mailto: at since it was built (see that file's own code
-- comment): the existing feedback table (006) is purpose-built for
-- per-answer thumbs ratings feeding the eval-harness mining pipeline
-- (scripts/mine_feedback_gaps.py) — query/response_summary/rating are all
-- NOT NULL there, so posting general product feedback through it would
-- inject non-answer rows into that pipeline. This is the separate table
-- that comment was waiting on.
--
-- No public status-triage UI in this PR (category defaults to 'new' and
-- stays there until someone manually updates it in the Supabase table
-- editor) — the ask was "let users submit bugs/feature requests and see
-- their own", not an admin dashboard.

CREATE TABLE IF NOT EXISTS product_feedback (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  category     varchar(24) NOT NULL CHECK (category IN ('bug', 'feature_request', 'general')),
  title        text NOT NULL,
  description  text NOT NULL,
  page_context text,        -- optional: the app path the user was on when they submitted
  status       varchar(16) NOT NULL DEFAULT 'new'
    CHECK (status IN ('new', 'reviewing', 'planned', 'done', 'declined')),
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_product_feedback_user_created
  ON product_feedback(user_id, created_at DESC);

ALTER TABLE product_feedback ENABLE ROW LEVEL SECURITY;

-- Users can read only their own submissions (the profile page's "your
-- feedback" list) — no cross-user visibility, no anon read. Writes go
-- through the backend's service-role client only (POST /api/v1/product-
-- feedback validates and bounds every field before insert), so there is
-- deliberately no INSERT policy for authenticated here.
DROP POLICY IF EXISTS "own product feedback" ON product_feedback;
CREATE POLICY "own product feedback"
  ON product_feedback FOR SELECT TO authenticated USING (auth.uid() = user_id);
