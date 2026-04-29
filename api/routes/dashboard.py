"""
api/routes/dashboard.py

Public read-only endpoints used by the React dashboard.
"""

from __future__ import annotations

import os
from collections import defaultdict
from typing import Any

import requests
from fastapi import APIRouter, HTTPException, Query


router = APIRouter(prefix="/dashboard")

DOCUMENT_FIELDS = (
    "id,title,county,financial_year,document_type,source_url,"
    "source_file,sectors,ingested_at"
)


def _supabase_config() -> tuple[str, str]:
    return os.environ.get("SUPABASE_URL", "").rstrip("/"), os.environ.get("SUPABASE_KEY", "")


def _is_configured() -> bool:
    url, key = _supabase_config()
    return bool(url and key)


def _headers() -> dict[str, str]:
    _, key = _supabase_config()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }


def _supabase_select(params: dict[str, str]) -> list[dict[str, Any]]:
    url, _ = _supabase_config()
    try:
        response = requests.get(
            f"{url}/rest/v1/documents",
            headers=_headers(),
            params=params,
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Could not load dashboard data") from exc
    return response.json()


def _empty_summary() -> dict[str, Any]:
    return {
        "configured": False,
        "document_count": 0,
        "county_count": 0,
        "latest_year": None,
        "years": [],
        "counties": [],
    }


def _normalize_document(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "title": row.get("title") or row.get("source_file") or "Untitled budget document",
        "county": row.get("county") or "Unknown",
        "financial_year": row.get("financial_year"),
        "document_type": row.get("document_type"),
        "source_url": row.get("source_url"),
        "source_file": row.get("source_file"),
        "sectors": row.get("sectors") or [],
        "ingested_at": row.get("ingested_at"),
    }


@router.get("/summary")
async def dashboard_summary() -> dict[str, Any]:
    """Return aggregate document coverage for the dashboard landing page."""
    if not _is_configured():
        return _empty_summary()

    rows = [_normalize_document(row) for row in _supabase_select({
        "select": DOCUMENT_FIELDS,
        "order": "ingested_at.desc",
        "limit": "1000",
    })]

    by_county: dict[str, dict[str, Any]] = {}
    years = sorted({row["financial_year"] for row in rows if row["financial_year"]}, reverse=True)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["county"]].append(row)

    for county, docs in grouped.items():
        sectors = sorted({sector for doc in docs for sector in doc["sectors"]})
        latest_year = max((doc["financial_year"] for doc in docs if doc["financial_year"]), default=None)
        by_county[county] = {
            "county": county,
            "document_count": len(docs),
            "latest_year": latest_year,
            "sectors": sectors,
        }

    return {
        "configured": True,
        "document_count": len(rows),
        "county_count": len(grouped),
        "latest_year": years[0] if years else None,
        "years": years,
        "counties": sorted(by_county.values(), key=lambda item: item["county"]),
    }


@router.get("/documents")
async def dashboard_documents(
    county: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    """List budget documents, optionally scoped to one county."""
    if not _is_configured():
        return {"configured": False, "documents": []}

    params = {
        "select": DOCUMENT_FIELDS,
        "order": "ingested_at.desc",
        "limit": str(limit),
    }
    if county:
        params["county"] = f"ilike.{county}"

    return {
        "configured": True,
        "documents": [_normalize_document(row) for row in _supabase_select(params)],
    }


@router.get("/search")
async def dashboard_search(
    q: str = Query(min_length=2),
    limit: int = Query(default=20, ge=1, le=50),
) -> dict[str, Any]:
    """Run a simple text search across document titles and content."""
    if not _is_configured():
        return {"configured": False, "query": q, "results": []}

    escaped = q.replace("*", "").strip()
    params = {
        "select": f"{DOCUMENT_FIELDS},content",
        "or": f"(title.ilike.*{escaped}*,content.ilike.*{escaped}*)",
        "order": "ingested_at.desc",
        "limit": str(limit),
    }
    rows = _supabase_select(params)

    results = []
    for row in rows:
        doc = _normalize_document(row)
        content = row.get("content") or ""
        index = content.lower().find(escaped.lower())
        if index >= 0:
            start = max(index - 120, 0)
            end = min(index + len(escaped) + 180, len(content))
            doc["snippet"] = content[start:end].strip()
        else:
            doc["snippet"] = ""
        results.append(doc)

    return {"configured": True, "query": q, "results": results}
