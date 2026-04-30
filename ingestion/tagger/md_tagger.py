#!/usr/bin/env python3
"""
md_tagger.py — Step 3 of the Bajeti Watch ingestion pipeline.

Extracts metadata from cleaned Markdown budget documents and attaches it
as YAML frontmatter. Metadata is critical for the RAG layer — without it,
retrieved chunks have no context about which budget, county, or year they
came from.

Two modes:
  1. AUTO   — sends the first 2000 chars of the Markdown to an LLM (Groq)
              to extract county, year, document_type, and sector automatically.
  2. MANUAL — you pass metadata as CLI flags (useful for known documents or
              when you don't want to burn LLM tokens on extraction).

Frontmatter output example:
  ---
  title: Kisumu County Budget 2023/24
  county: Kisumu
  financial_year: 2023/24
  document_type: county_budget
  source_url: https://cob.go.ke/reports/kisumu-2023.pdf
  ingested_at: 2026-04-16T10:32:00
  sectors: [roads, health, education]
  ---

Usage:
    # Auto-extract (requires GROQ_API_KEY in env)
    python md_tagger.py cleaned.md --source-url https://cob.go.ke/...

    # Manual
    python md_tagger.py cleaned.md --county Kisumu --year 2023/24 \
        --doc-type county_budget --source-url https://...

    # Batch auto-extract
    python md_tagger.py ./cleaned/*.md --out-dir ./tagged --source-url https://...
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml  # pip install pyyaml


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_MAX_TOKENS = 512

# How many characters of the document to send to the LLM for extraction
EXTRACTION_SAMPLE_CHARS = 2000

VALID_DOC_TYPES = [
    "national_budget",
    "county_budget",
    "supplementary_estimates",
    "budget_implementation_report",
    "mtef",            # Medium Term Expenditure Framework
    "county_fiscal",
    "other",
]

KENYAN_COUNTIES = [
    "Baringo", "Bomet", "Bungoma", "Busia", "Elgeyo-Marakwet", "Embu",
    "Garissa", "Homa Bay", "Isiolo", "Kajiado", "Kakamega", "Kericho",
    "Kiambu", "Kilifi", "Kirinyaga", "Kisii", "Kisumu", "Kitui", "Kwale",
    "Laikipia", "Lamu", "Machakos", "Makueni", "Mandera", "Marsabit",
    "Meru", "Migori", "Mombasa", "Murang'a", "Nairobi", "Nakuru", "Nandi",
    "Narok", "Nyamira", "Nyandarua", "Nyeri", "Samburu", "Siaya",
    "Taita-Taveta", "Tana River", "Tharaka-Nithi", "Trans Nzoia", "Turkana",
    "Uasin Gishu", "Vihiga", "Wajir", "West Pokot", "National",
]


# ---------------------------------------------------------------------------
# LLM extraction via Groq
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT = """You are a metadata extractor for Kenyan government budget documents.

Given the beginning of a budget document below, extract the following fields as JSON.
Be precise. If a field cannot be determined, use null.

Fields to extract:
- title: Full document title as it appears in the document
- county: One of the 47 Kenyan counties, or "National" for national budget. Null if unclear.
- financial_year: Budget year in format YYYY/YY (e.g. 2023/24). Null if unclear.
- document_type: One of: national_budget, county_budget, supplementary_estimates, budget_implementation_report, mtef, county_fiscal, other
- sectors: List of main budget sectors mentioned (e.g. ["roads", "health", "education", "agriculture"])

Return ONLY valid JSON. No explanation, no markdown, no extra text.

Document excerpt:
{excerpt}
"""


def extract_metadata_with_llm(text: str, api_key: str) -> dict:
    """
    Send document excerpt to Groq Llama and parse the JSON response.
    Returns a dict with extracted fields (values may be None).
    """
    excerpt = text[:EXTRACTION_SAMPLE_CHARS].strip()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "max_tokens": GROQ_MAX_TOKENS,
        "temperature": 0,  # deterministic — we want facts not creativity
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "user", "content": EXTRACTION_PROMPT.format(excerpt=excerpt)}
        ],
    }

    resp = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=30)
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        detail = resp.text[:500]
        raise requests.HTTPError(
            f"{exc}. Groq response body: {detail}",
            response=resp,
        ) from exc

    content = resp.json()["choices"][0]["message"]["content"].strip()

    # Strip accidental markdown fences
    content = re.sub(r"^```json?\s*", "", content)
    content = re.sub(r"\s*```$", "", content)

    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError(f"Groq returned non-JSON metadata response: {content[:500]!r}") from exc


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def has_frontmatter(text: str) -> bool:
    return bool(FRONTMATTER_RE.match(text))


def strip_existing_frontmatter(text: str) -> str:
    return FRONTMATTER_RE.sub("", text, count=1)


def build_frontmatter(meta: dict) -> str:
    """Convert a metadata dict to a YAML frontmatter block."""
    return "---\n" + yaml.dump(meta, allow_unicode=True, sort_keys=False) + "---\n\n"


def attach_frontmatter(text: str, meta: dict) -> str:
    """Strip any existing frontmatter and prepend new one."""
    body = strip_existing_frontmatter(text) if has_frontmatter(text) else text
    return build_frontmatter(meta) + body.lstrip()


# ---------------------------------------------------------------------------
# Metadata assembly
# ---------------------------------------------------------------------------

def build_metadata(
    extracted: dict | None,
    county: str | None,
    year: str | None,
    doc_type: str | None,
    source_url: str | None,
    sectors: list[str] | None,
    filename: str = "",
) -> dict:
    """
    Merge LLM-extracted metadata with any manually provided overrides.
    Manual values always win over LLM values.
    """
    e = extracted or {}

    resolved_county  = county    or e.get("county")
    resolved_year    = year      or e.get("financial_year")
    resolved_type    = doc_type  or e.get("document_type", "other")
    resolved_sectors = sectors   or e.get("sectors") or []
    resolved_title   = e.get("title") or _infer_title(resolved_county, resolved_year, resolved_type, filename)

    return {
        "title":          resolved_title,
        "county":         resolved_county,
        "financial_year": resolved_year,
        "document_type":  resolved_type,
        "source_url":     source_url,
        "source_file":    filename,
        "sectors":        resolved_sectors,
        "ingested_at":    datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _infer_title(county, year, doc_type, filename) -> str:
    parts = []
    if county:
        parts.append(county)
    if doc_type and doc_type != "other":
        parts.append(doc_type.replace("_", " ").title())
    if year:
        parts.append(year)
    return " ".join(parts) if parts else Path(filename).stem.replace("_", " ").title()


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def tag_file(
    src: Path,
    dst: Path,
    auto: bool,
    api_key: str | None,
    county: str | None,
    year: str | None,
    doc_type: str | None,
    source_url: str | None,
    sectors: list[str] | None,
) -> None:
    text = src.read_text(encoding="utf-8")

    extracted = None
    if auto:
        if not api_key:
            raise ValueError("GROQ_API_KEY not set — cannot auto-extract metadata.")
        print(f"  Extracting metadata via LLM for: {src.name} ...")
        extracted = extract_metadata_with_llm(text, api_key)

    meta = build_metadata(
        extracted=extracted,
        county=county,
        year=year,
        doc_type=doc_type,
        source_url=source_url,
        sectors=sectors,
        filename=src.name,
    )

    tagged = attach_frontmatter(text, meta)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(tagged, encoding="utf-8")

    county_str = meta.get("county") or "unknown county"
    year_str   = meta.get("financial_year") or "unknown year"
    print(f"{src.name} -> {dst.name}  [{county_str} | {year_str}]")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Tag cleaned Markdown budget files with YAML frontmatter metadata.")
    parser.add_argument("inputs", nargs="+", help="Cleaned .md files or glob patterns")
    parser.add_argument("-o", "--output",   type=Path, help="Output file (single-file mode)")
    parser.add_argument("--out-dir",        type=Path, help="Output directory (batch mode)")

    # Auto extraction
    parser.add_argument("--auto", action="store_true",
                        help="Use LLM (Groq) to auto-extract metadata from document content")

    # Manual overrides — always take precedence over LLM extraction
    parser.add_argument("--county",     help=f"County name. One of: {', '.join(KENYAN_COUNTIES[:6])}...")
    parser.add_argument("--year",       help="Financial year, e.g. 2023/24")
    parser.add_argument("--doc-type",   choices=VALID_DOC_TYPES, help="Document type")
    parser.add_argument("--source-url", help="Source URL where the PDF was downloaded from")
    parser.add_argument("--sectors",    nargs="+", help="Budget sectors e.g. roads health education")

    args = parser.parse_args()

    api_key = os.environ.get("GROQ_API_KEY")
    if args.auto and not api_key:
        print("ERROR: --auto requires GROQ_API_KEY environment variable to be set.", file=sys.stderr)
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
            if args.output and len(paths) == 1:
                dst = args.output
            elif args.out_dir:
                dst = args.out_dir / src.name
            else:
                dst = src.parent / f"{src.stem}_tagged{src.suffix}"

            tag_file(
                src=src,
                dst=dst,
                auto=args.auto,
                api_key=api_key,
                county=args.county,
                year=args.year,
                doc_type=args.doc_type,
                source_url=args.source_url,
                sectors=args.sectors,
            )
        except Exception as exc:
            print(f"error: {src}: {exc}", file=sys.stderr)
            errors += 1

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())