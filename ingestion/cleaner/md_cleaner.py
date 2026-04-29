#!/usr/bin/env python3
"""
md_cleaner.py — Step 2 of the Bajeti Watch ingestion pipeline.

Cleans Markdown files produced by pdf_to_md.py, removing noise common
in Kenyan government budget PDFs:
  - Repeated page headers / footers (e.g. "REPUBLIC OF KENYA" on every page)
  - Page number patterns  (Page 1 of 50 | - 1 - | 1 | etc.)
  - Horizontal separator noise (long dash/underscore/dot lines)
  - Page-break comments left by pymupdf4llm  (<!-- page N -->)
  - Excessive blank lines (collapses to max 2)
  - Trailing whitespace on every line

Usage:
    python md_cleaner.py input.md                    # writes input_clean.md
    python md_cleaner.py input.md -o output.md       # explicit output path
    python md_cleaner.py *.md --out-dir ./cleaned    # batch, keeps filenames
"""

from __future__ import annotations

import argparse
import glob
import re
import sys
from collections import Counter
from pathlib import Path


# ---------------------------------------------------------------------------
# Regex patterns — all compiled once at module level
# ---------------------------------------------------------------------------

# Page number patterns:  "Page 1 of 50" | "1 of 50" | "- 1 -" | lone digit line
RE_PAGE_NUM = re.compile(
    r"^\s*("
    r"[-–]\s*\d+\s*[-–]"           # - 1 -
    r"|Page\s+\d+\s*(of\s+\d+)?"  # Page 1  |  Page 1 of 50
    r"|\d+\s+of\s+\d+"             # 1 of 50
    r"|\d+"                        # lone number on its own line
    r")\s*$",
    re.IGNORECASE,
)

# Separator lines: 3+ dashes, underscores, dots, equals, or asterisks
RE_SEPARATOR = re.compile(r"^\s*[-_.*=]{3,}\s*$")

# pymupdf4llm page-break comment
RE_PAGE_COMMENT = re.compile(r"<!--\s*page\s*\d+\s*-->", re.IGNORECASE)

# Common Kenyan government PDF running headers / footers
# Add more patterns here as you encounter them in real documents
GOVT_HEADER_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"republic\s+of\s+kenya",
        r"the\s+national\s+treasury",
        r"controller\s+of\s+budget",
        r"county\s+government\s+of",
        r"ministry\s+of\s+finance",
        r"printed\s+by\s+the\s+government",
        r"confidential\s*[-–]?\s*not\s+for\s+circulation",
        r"draft\s*[-–]?\s*not\s+for\s+distribution",
    ]
]

# Watermark-style lines (all caps, short, standalone)
RE_WATERMARK = re.compile(r"^\s*[A-Z\s]{4,40}\s*$")


# ---------------------------------------------------------------------------
# Core cleaning logic
# ---------------------------------------------------------------------------

def detect_repeated_lines(lines: list[str], threshold: float = 0.3) -> set[str]:
    """
    Find lines that repeat suspiciously often — likely running headers/footers.
    threshold: fraction of total pages above which a line is considered repeated.
    Ignores blank lines, Markdown table rows, and heading lines.
    """
    # Count page breaks to estimate page count
    page_count = max(1, sum(1 for l in lines if RE_PAGE_COMMENT.search(l)))

    counts: Counter = Counter()
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("|"):      # table row
            continue
        if stripped.startswith("#"):      # markdown heading
            continue
        if len(stripped) < 5:
            continue
        counts[stripped] += 1

    min_repeats = max(2, int(page_count * threshold))
    return {line for line, count in counts.items() if count >= min_repeats}


def is_govt_header(line: str) -> bool:
    """True if the line matches a known government running header pattern."""
    stripped = line.strip()
    return any(pat.search(stripped) for pat in GOVT_HEADER_PATTERNS)


def clean_markdown(text: str, aggressive: bool = False) -> str:
    """
    Clean a Markdown string and return the cleaned version.

    aggressive=True also removes:
      - Short all-caps lines (watermark heuristic)
      - Lines that look like form-feed artefacts
    """
    lines = text.splitlines()

    # ── Pass 1: detect repeated headers/footers ──────────────────────────────
    repeated = detect_repeated_lines(lines)

    # ── Pass 2: line-by-line filtering ──────────────────────────────────────
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()

        # Remove pymupdf page comments
        if RE_PAGE_COMMENT.match(stripped):
            continue

        # Remove page numbers
        if RE_PAGE_NUM.match(stripped):
            continue

        # Remove separator noise
        if RE_SEPARATOR.match(stripped):
            continue

        # Remove known government running headers
        if is_govt_header(line):
            continue

        # Remove detected repeated lines
        if stripped in repeated:
            continue

        # Aggressive: remove short all-caps watermark lines
        if aggressive and RE_WATERMARK.match(stripped) and len(stripped) < 30:
            continue

        # Strip trailing whitespace, keep the line
        cleaned.append(line.rstrip())

    # ── Pass 3: collapse excessive blank lines ───────────────────────────────
    result: list[str] = []
    blank_count = 0
    for line in cleaned:
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 2:
                result.append("")
        else:
            blank_count = 0
            result.append(line)

    # ── Pass 4: strip leading/trailing blanks from the whole document ────────
    while result and result[0].strip() == "":
        result.pop(0)
    while result and result[-1].strip() == "":
        result.pop()

    return "\n".join(result) + "\n"


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def clean_file(src: Path, dst: Path, aggressive: bool = False) -> None:
    text = src.read_text(encoding="utf-8")
    cleaned = clean_markdown(text, aggressive=aggressive)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(cleaned, encoding="utf-8")

    original_words = len(text.split())
    cleaned_words = len(cleaned.split())
    removed_pct = 100 * (1 - cleaned_words / max(original_words, 1))
    print(f"{src.name} -> {dst.name}  [{removed_pct:.1f}% noise removed]")


def default_output(src: Path, out_dir: Path | None) -> Path:
    if out_dir:
        return out_dir / src.name
    return src.parent / f"{src.stem}_clean{src.suffix}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Clean Markdown files from PDF conversion for LLM ingestion.")
    parser.add_argument("inputs", nargs="+", help="Markdown files or glob patterns")
    parser.add_argument("-o", "--output", type=Path, help="Output file (single-file mode only)")
    parser.add_argument("--out-dir", type=Path, help="Output directory (batch mode)")
    parser.add_argument("--aggressive", action="store_true", help="Also strip watermarks and short all-caps lines")
    args = parser.parse_args()

    # Expand globs
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
            else:
                dst = default_output(src, args.out_dir)
            clean_file(src, dst, aggressive=args.aggressive)
        except Exception as e:
            print(f"error: {src}: {e}", file=sys.stderr)
            errors += 1

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())