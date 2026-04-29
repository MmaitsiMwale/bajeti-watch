"""
agent/tools/supabase_search.py

Wrapper around the search_chunks() Supabase RPC function.
Called by the retrieval node to fetch relevant budget chunks.
"""

from __future__ import annotations

import os
import requests


SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")


def search_chunks(
    query_embedding: list[float],
    county_filter: str | None = None,
    year_filter: str | None = None,
    match_count: int = 5,
) -> list[dict]:
    """
    Call the search_chunks() Postgres function via Supabase RPC.
    Returns a list of chunk dicts with: content, metadata, similarity.
    """
    url = SUPABASE_URL.rstrip("/") + "/rest/v1/rpc/search_chunks"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "query_embedding": query_embedding,
        "match_count": match_count,
    }
    if county_filter:
        payload["county_filter"] = county_filter
    if year_filter:
        payload["year_filter"] = year_filter

    resp = requests.post(url, headers=headers, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def embed_query(text: str) -> list[float]:
    """
    Embed a query string using nomic-embed-text.
    Routes to Ollama locally or Nomic API in production
    based on EMBEDDING_PROVIDER env variable.
    """
    provider = os.environ.get("EMBEDDING_PROVIDER", "ollama")

    if provider == "nomic":
        return _embed_nomic_api(text)
    return _embed_ollama(text)


def _embed_ollama(text: str) -> list[float]:
    resp = requests.post(
        "http://localhost:11434/api/embeddings",
        json={"model": "nomic-embed-text", "prompt": text},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]


def _embed_nomic_api(text: str) -> list[float]:
    api_key = os.environ.get("NOMIC_API_KEY", "")
    resp = requests.post(
        "https://api-atlas.nomic.ai/v1/embedding/text",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": "nomic-embed-text-v1.5",
            "texts": [text],
            "task_type": "search_query",   # query mode (vs search_document for ingestion)
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"][0]