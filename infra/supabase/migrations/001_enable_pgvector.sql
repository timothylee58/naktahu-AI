-- Enable pgvector extension
create extension if not exists vector;

-- DOSM documents table for RAG
create table if not exists dosm_documents (
  id bigserial primary key,
  content text not null,
  metadata jsonb,
  embedding vector(1536)
);

-- Vector similarity search function
create or replace function match_documents (
  query_embedding vector(1536),
  match_count int default 5
) returns table (
  id bigint,
  content text,
  metadata jsonb,
  similarity float
)
language sql stable
as $$
  select
    id, content, metadata,
    1 - (embedding <=> query_embedding) as similarity
  from dosm_documents
  order by embedding <=> query_embedding
  limit match_count;
$$;
