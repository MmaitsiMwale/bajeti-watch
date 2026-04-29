-- Bajeti Watch — Initial Supabase schema
-- Run this once in the Supabase SQL editor before the first ingestion run.

-- Enable pgvector for semantic search.
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
  source_file      text unique,
  sectors          text[],
  content          text not null,
  ingested_at      timestamptz default now()
);

create index if not exists idx_documents_county
  on documents(county);

create index if not exists idx_documents_financial_year
  on documents(financial_year);

create index if not exists idx_documents_document_type
  on documents(document_type);

-- ── Chunks table ─────────────────────────────────────────────────────────────
-- Stores text chunks and their 768-dimension nomic-embed-text embeddings.
create table if not exists chunks (
  id           uuid primary key default gen_random_uuid(),
  document_id  uuid not null references documents(id) on delete cascade,
  chunk_index  integer not null,
  content      text not null,
  embedding    vector(768),
  metadata     jsonb default '{}'
);

create index if not exists idx_chunks_embedding
  on chunks using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

create index if not exists idx_chunks_document_id
  on chunks(document_id);

-- ── Subscribers table ────────────────────────────────────────────────────────
-- Stores WhatsApp subscribers with hashed phone numbers.
create table if not exists subscribers (
  id            uuid primary key default gen_random_uuid(),
  phone_hash    text unique not null,
  county        text,
  subscribed_at timestamptz default now(),
  active        boolean default true
);

create index if not exists idx_subscribers_county
  on subscribers(county);

create index if not exists idx_subscribers_active
  on subscribers(active);

-- ── RAG search function ──────────────────────────────────────────────────────
-- Called by the LangGraph retrieval node via Supabase RPC.
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
