-- 012_storage_generated_documents.sql
-- Private bucket for agent-generated PDFs (Compliance Drafter, etc.).
-- API uploads via service role; users access files via signed URLs.

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'generated-documents',
    'generated-documents',
    false,
    52428800, -- 50 MiB
    ARRAY['application/pdf']::text[]
)
ON CONFLICT (id) DO UPDATE SET
    public             = EXCLUDED.public,
    file_size_limit    = EXCLUDED.file_size_limit,
    allowed_mime_types = EXCLUDED.allowed_mime_types;

-- Service role bypasses RLS; these policies cover authenticated direct access.
DROP POLICY IF EXISTS "generated_documents_select_own" ON storage.objects;
CREATE POLICY "generated_documents_select_own"
    ON storage.objects
    FOR SELECT
    TO authenticated
    USING (
        bucket_id = 'generated-documents'
        AND (storage.foldername(name))[1] = 'agents'
        AND auth.uid()::text = (storage.foldername(name))[3]
    );

DROP POLICY IF EXISTS "generated_documents_insert_own" ON storage.objects;
CREATE POLICY "generated_documents_insert_own"
    ON storage.objects
    FOR INSERT
    TO authenticated
    WITH CHECK (
        bucket_id = 'generated-documents'
        AND (storage.foldername(name))[1] = 'agents'
        AND auth.uid()::text = (storage.foldername(name))[3]
    );
