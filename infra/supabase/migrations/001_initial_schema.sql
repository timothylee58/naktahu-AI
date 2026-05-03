-- 001_initial_schema.sql
-- Enable pgvector and create the document_chunks table with hybrid search indexes.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS document_chunks (
    id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    content      text        NOT NULL,
    content_hash text        NOT NULL,
    language     varchar(2)  NOT NULL,
    domain       varchar(32) NOT NULL,
    source_title text        NOT NULL,
    source_url   text        NOT NULL,
    ministry     text        NOT NULL,
    embedding    vector(1536),
    created_at   timestamptz NOT NULL DEFAULT now()
);

-- Stable identity key so ingestion reruns upsert rather than duplicate rows
CREATE UNIQUE INDEX IF NOT EXISTS document_chunks_content_hash_uq
    ON document_chunks (content_hash);

-- BM25 full-text search index using simple (language-neutral) tokenisation
CREATE INDEX IF NOT EXISTS document_chunks_content_fts
    ON document_chunks
    USING GIN (to_tsvector('simple', content));

-- ivfflat approximate nearest-neighbour index for cosine similarity
-- lists=100 is suitable for up to ~1M rows; re-index with more lists as data grows.
CREATE INDEX IF NOT EXISTS document_chunks_embedding_cosine
    ON document_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
