-- Bajeti Watch — Supabase Schema
-- Run this once in your Supabase SQL editor before the first pipeline run.

-- Enable pgvector extension
create extension if not exists vector;

-- ── Documents table ──────────────────────────────────────────────────────────
-- Stores the full cleaned Markdown content + metadata for each budget document.

create table if not exists documents (
  id               uuid primary key default gen_random_uuid(),
  title            text,
  county           text,
  financial_year   text,
  document_type    text,
  source_url       text,
  source_file      text unique,     -- prevents duplicate ingestion
  sectors          text[],          -- array of sector strings
  content          text not null,   -- full cleaned Markdown body
  ingested_at      timestamptz default now()
);

-- Index for common query patterns
create index if not exists idx_documents_county         on documents(county);
create index if not exists idx_documents_financial_year on documents(financial_year);
create index if not exists idx_documents_document_type  on documents(document_type);

-- ── Chunks table ─────────────────────────────────────────────────────────────
-- Stores individual text chunks with their vector embeddings.
-- nomic-embed-text produces 768-dimension vectors.

create table if not exists chunks (
  id           uuid primary key default gen_random_uuid(),
  document_id  uuid not null references documents(id) on delete cascade,
  chunk_index  integer not null,
  content      text not null,
  embedding    vector(768),         -- nomic-embed-text dimension
  metadata     jsonb default '{}'   -- county, year, doc_type, source_file etc.
);

-- pgvector index for fast cosine similarity search
-- ivfflat is good for datasets up to ~1M vectors
create index if not exists idx_chunks_embedding
  on chunks using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

-- Index on document_id for cascade queries
create index if not exists idx_chunks_document_id on chunks(document_id);

-- ── Subscribers table ────────────────────────────────────────────────────────
-- Stores WhatsApp subscribers (phone numbers hashed for privacy).

create table if not exists subscribers (
  id            uuid primary key default gen_random_uuid(),
  phone_hash    text unique not null,  -- SHA-256 of the phone number
  county        text,                  -- their county of interest
  subscribed_at timestamptz default now(),
  active        boolean default true
);

create index if not exists idx_subscribers_county on subscribers(county);
create index if not exists idx_subscribers_active on subscribers(active);

-- ── RAG search function ──────────────────────────────────────────────────────
-- Convenience function for semantic search — call this from your Python agent
-- instead of writing raw pgvector SQL every time.
--
-- Usage (from Python via supabase-py):
--   result = supabase.rpc("search_chunks", {
--     "query_embedding": [...],   # 768-dim float list
--     "county_filter": "Kisumu",  # optional
--     "match_count": 5
--   }).execute()

create or replace function search_chunks(
  query_embedding  vector(768),
  county_filter    text    default null,
  year_filter      text    default null,
  match_count      integer default 5
)
returns table (
  id           uuid,
  document_id  uuid,
  chunk_index  integer,
  content      text,
  metadata     jsonb,
  similarity   float
)
language sql stable
as $$
  select
    c.id,
    c.document_id,
    c.chunk_index,
    c.content,
    c.metadata,
    1 - (c.embedding <=> query_embedding) as similarity
  from chunks c
  join documents d on d.id = c.document_id
  where
    (county_filter is null or d.county ilike county_filter)
    and (year_filter is null or d.financial_year = year_filter)
  order by c.embedding <=> query_embedding
  limit match_count;
$$;