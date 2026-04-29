#!/usr/bin/env python3
"""
supabase_uploader.py — Step 4 (final) of the Bajeti Watch ingestion pipeline.

Takes tagged Markdown files (with YAML frontmatter) and:
  1. Parses the frontmatter metadata
  2. Stores the full document in Supabase (documents table)
  3. Splits the body into overlapping chunks (LangChain)
  4. Embeds each chunk with nomic-embed-text (via Ollama locally, or
     nomic's API in production)
  5. Stores chunks + embeddings in Supabase pgvector (chunks table)

Supabase schema expected (run schema.sql first):
  documents(id, title, county, financial_year, document_type, source_url,
            source_file, sectors, content, ingested_at)
  chunks(id, document_id, chunk_index, content, embedding, metadata)

Usage:
    # Single file
    python supabase_uploader.py tagged.md

    # Batch
    python supabase_uploader.py ./tagged/*.md

    # Skip re-uploading files already in the database
    python supabase_uploader.py ./tagged/*.md --skip-existing

Environment variables required:
    SUPABASE_URL        — e.g. https://xxxx.supabase.co
    SUPABASE_KEY        — service role key (not anon key — needs insert access)
    EMBEDDING_PROVIDER  — "ollama" (local) or "nomic" (cloud API). Default: ollama
    NOMIC_API_KEY       — required if EMBEDDING_PROVIDER=nomic
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
import yaml  # pip install pyyaml


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
EMBEDDING_PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "ollama")
NOMIC_API_KEY = os.environ.get("NOMIC_API_KEY", "")

# Chunking config — tuned for budget documents
# 500 tokens ~ 375 words. Overlap helps the LLM see context across chunk edges.
CHUNK_SIZE    = 500   # tokens (approximate — we use chars / 4)
CHUNK_OVERLAP = 80    # tokens overlap between adjacent chunks

# Ollama local endpoint
OLLAMA_URL   = "http://localhost:11434/api/embeddings"
OLLAMA_MODEL = "nomic-embed-text"

# Nomic cloud endpoint
NOMIC_URL    = "https://api-atlas.nomic.ai/v1/embedding/text"
NOMIC_MODEL  = "nomic-embed-text-v1.5"

# Supabase REST endpoints
DOCUMENTS_ENDPOINT = "/rest/v1/documents"
CHUNKS_ENDPOINT    = "/rest/v1/chunks"


# ---------------------------------------------------------------------------
# Frontmatter parser
# ---------------------------------------------------------------------------

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_tagged_markdown(text: str) -> tuple[dict, str]:
    """
    Split a tagged Markdown file into (metadata dict, body text).
    Raises ValueError if no frontmatter is found.
    """
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("No YAML frontmatter found. Run md_tagger.py first.")
    meta = yaml.safe_load(m.group(1)) or {}
    body = text[m.end():].lstrip()
    return meta, body


# ---------------------------------------------------------------------------
# Chunker — simple character-based with overlap (no external dependency)
# ---------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split text into overlapping chunks.
    chunk_size and overlap are in approximate tokens (chars / 4).
    Tries to split on paragraph boundaries to keep semantic units together.
    """
    char_size    = chunk_size * 4
    char_overlap = overlap * 4

    # Split on double newlines first (paragraph boundaries)
    paragraphs = re.split(r"\n\n+", text.strip())

    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If adding this paragraph keeps us under chunk_size, add it
        if len(current) + len(para) + 2 <= char_size:
            current = f"{current}\n\n{para}".lstrip()
        else:
            # Save current chunk if it has content
            if current:
                chunks.append(current)
            # If the paragraph itself is larger than chunk_size, hard-split it
            if len(para) > char_size:
                for i in range(0, len(para), char_size - char_overlap):
                    piece = para[i : i + char_size]
                    if piece.strip():
                        chunks.append(piece)
                current = ""
            else:
                # Start new chunk with overlap from end of previous chunk
                if chunks:
                    overlap_text = chunks[-1][-char_overlap:]
                    current = f"{overlap_text}\n\n{para}".lstrip()
                else:
                    current = para

    if current.strip():
        chunks.append(current)

    return chunks


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

def embed_ollama(texts: list[str]) -> list[list[float]]:
    """Get embeddings from local Ollama (nomic-embed-text)."""
    embeddings = []
    for text in texts:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": text},
            timeout=60,
        )
        resp.raise_for_status()
        embeddings.append(resp.json()["embedding"])
    return embeddings


def embed_nomic_api(texts: list[str]) -> list[list[float]]:
    """Get embeddings from Nomic Atlas cloud API (batched)."""
    headers = {
        "Authorization": f"Bearer {NOMIC_API_KEY}",
        "Content-Type": "application/json",
    }
    resp = requests.post(
        NOMIC_URL,
        headers=headers,
        json={"model": NOMIC_MODEL, "texts": texts, "task_type": "search_document"},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"]


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Route embedding request to the configured provider."""
    if EMBEDDING_PROVIDER == "nomic":
        if not NOMIC_API_KEY:
            raise ValueError("NOMIC_API_KEY not set but EMBEDDING_PROVIDER=nomic")
        # Nomic API supports batches of up to 100
        results = []
        for i in range(0, len(texts), 100):
            batch = texts[i : i + 100]
            results.extend(embed_nomic_api(batch))
        return results
    else:
        # Ollama: one at a time (local, no batching needed)
        return embed_ollama(texts)


# ---------------------------------------------------------------------------
# Supabase REST helpers
# ---------------------------------------------------------------------------

def supabase_headers() -> dict:
    return {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "return=representation",
    }


def supabase_insert(endpoint: str, payload: dict | list) -> dict | list:
    url = SUPABASE_URL.rstrip("/") + endpoint
    resp = requests.post(url, headers=supabase_headers(), json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def supabase_select(endpoint: str, params: dict) -> list:
    url = SUPABASE_URL.rstrip("/") + endpoint
    resp = requests.get(url, headers=supabase_headers(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def document_exists(source_file: str) -> bool:
    """Check if a document with this source filename is already in the DB."""
    results = supabase_select(
        DOCUMENTS_ENDPOINT,
        {"select": "id", "source_file": f"eq.{source_file}", "limit": "1"},
    )
    return len(results) > 0


# ---------------------------------------------------------------------------
# Main upload logic
# ---------------------------------------------------------------------------

def upload_file(src: Path, skip_existing: bool = False) -> None:
    text = src.read_text(encoding="utf-8")
    meta, body = parse_tagged_markdown(text)

    # ── Skip check ────────────────────────────────────────────────────────
    if skip_existing and document_exists(src.name):
        print(f"skip (already uploaded): {src.name}")
        return

    # ── 1. Insert document record ─────────────────────────────────────────
    doc_record = {
        "title":          meta.get("title"),
        "county":         meta.get("county"),
        "financial_year": meta.get("financial_year"),
        "document_type":  meta.get("document_type"),
        "source_url":     meta.get("source_url"),
        "source_file":    meta.get("source_file", src.name),
        "sectors":        meta.get("sectors", []),
        "content":        body,
        "ingested_at":    meta.get("ingested_at"),
    }

    inserted = supabase_insert(DOCUMENTS_ENDPOINT, doc_record)
    doc_id = inserted[0]["id"]
    print(f"  Document record created: id={doc_id}")

    # ── 2. Chunk the body ─────────────────────────────────────────────────
    chunks = chunk_text(body)
    print(f"  Chunked into {len(chunks)} pieces")

    # ── 3. Embed all chunks ───────────────────────────────────────────────
    print(f"  Embedding {len(chunks)} chunks via {EMBEDDING_PROVIDER} ...")
    embeddings = get_embeddings(chunks)

    # ── 4. Insert chunks with embeddings ─────────────────────────────────
    chunk_records = []
    for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        chunk_records.append({
            "document_id":  doc_id,
            "chunk_index":  idx,
            "content":      chunk,
            "embedding":    embedding,     # pgvector accepts a plain float list
            "metadata": {
                "county":         meta.get("county"),
                "financial_year": meta.get("financial_year"),
                "document_type":  meta.get("document_type"),
                "source_file":    src.name,
                "chunk_index":    idx,
                "total_chunks":   len(chunks),
            },
        })

    # Batch insert in groups of 50 to stay within Supabase request limits
    for i in range(0, len(chunk_records), 50):
        batch = chunk_records[i : i + 50]
        supabase_insert(CHUNKS_ENDPOINT, batch)
        print(f"  Inserted chunks {i + 1}–{min(i + 50, len(chunk_records))} / {len(chunk_records)}")
        time.sleep(0.2)  # brief pause to avoid rate limiting

    county = meta.get("county", "unknown")
    year   = meta.get("financial_year", "unknown")
    print(f"{src.name} -> Supabase  [{county} | {year} | {len(chunks)} chunks]")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def validate_env() -> list[str]:
    errors = []
    if not SUPABASE_URL:
        errors.append("SUPABASE_URL not set")
    if not SUPABASE_KEY:
        errors.append("SUPABASE_KEY not set")
    if EMBEDDING_PROVIDER == "nomic" and not NOMIC_API_KEY:
        errors.append("EMBEDDING_PROVIDER=nomic but NOMIC_API_KEY not set")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload tagged Markdown budget files to Supabase with embeddings.")
    parser.add_argument("inputs", nargs="+", help="Tagged .md files or glob patterns")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip files already present in the database (idempotent runs)")
    args = parser.parse_args()

    env_errors = validate_env()
    if env_errors:
        for e in env_errors:
            print(f"ERROR: {e}", file=sys.stderr)
        print("Set the required environment variables and retry.", file=sys.stderr)
        return 1

    # Expand inputs
    paths: list[Path] = []
    for raw in args.inputs:
        if any(c in raw for c in "*?[]"):
            paths.extend(Path(p) for p in sorted(glob.glob(raw)) if p.endswith(".md"))
        else:
            p = Path(raw)
            if p.exists():
                paths.append(p)
            else:
                print(f"skip (not found): {raw}", file=sys.stderr)

    if not paths:
        print("No Markdown files found.", file=sys.stderr)
        return 1

    errors = 0
    for src in paths:
        try:
            upload_file(src, skip_existing=args.skip_existing)
        except Exception as exc:
            print(f"error: {src}: {exc}", file=sys.stderr)
            errors += 1

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())