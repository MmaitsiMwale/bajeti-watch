#!/usr/bin/env python3
"""
pipeline.py — Bajeti Watch full ingestion pipeline orchestrator.

Runs all four steps in sequence for one or more PDF files:
  1. pdf_to_md.py       — PDF -> Markdown
  2. md_cleaner.py      — Remove noise from Markdown
  3. md_tagger.py       — Attach YAML metadata frontmatter
  4. supabase_uploader.py — Chunk, embed, store in Supabase

Directory layout (auto-created under --work-dir, default: ./pipeline_work):
  pipeline_work/
    01_markdown/      raw .md files from pdf_to_md
    02_cleaned/       noise-removed .md files
    03_tagged/        frontmatter-tagged .md files (ready for upload)

Usage:
    # Minimal — auto-extracts metadata via LLM
    python pipeline.py budget.pdf --source-url https://treasury.go.ke/budget.pdf

    # With manual metadata (no LLM token cost)
    python pipeline.py budget.pdf \\
        --county Kisumu --year 2023/24 --doc-type county_budget \\
        --source-url https://cob.go.ke/kisumu-2023.pdf

    # Batch — process all PDFs in a directory
    python pipeline.py ./downloads/*.pdf --auto --source-url https://treasury.go.ke

    # Skip re-uploading files already in the DB (safe to re-run)
    python pipeline.py ./downloads/*.pdf --skip-existing

Environment variables (set before running):
    SUPABASE_URL
    SUPABASE_KEY
    GROQ_API_KEY        (required if --auto)
    EMBEDDING_PROVIDER  (ollama | nomic, default: ollama)
    NOMIC_API_KEY       (required if EMBEDDING_PROVIDER=nomic)
"""

from __future__ import annotations

import argparse
import glob
import importlib.util
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Dynamic imports — load sibling scripts as modules
# ---------------------------------------------------------------------------

def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


HERE = Path(__file__).parent

pdf_to_md_mod        = _load("pdf_to_md",        HERE / "pdf_to_md.py")
md_cleaner_mod       = _load("md_cleaner",        HERE / "md_cleaner.py")
md_tagger_mod        = _load("md_tagger",         HERE / "md_tagger.py")
supabase_upload_mod  = _load("supabase_uploader", HERE / "supabase_uploader.py")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DIVIDER = "─" * 60


def banner(step: int, title: str) -> None:
    print(f"\n{DIVIDER}")
    print(f"  STEP {step}: {title}")
    print(DIVIDER)


def collect_pdfs(patterns: list[str]) -> list[Path]:
    return pdf_to_md_mod.collect_pdfs(patterns)


# ---------------------------------------------------------------------------
# Step runners
# ---------------------------------------------------------------------------

def step1_convert(pdf_paths: list[Path], out_dir: Path, show_progress: bool) -> list[Path]:
    """Convert PDFs to Markdown."""
    out_dir.mkdir(parents=True, exist_ok=True)
    used_stems: dict[str, int] = {}
    md_files: list[Path] = []

    for pdf_path in pdf_paths:
        pdf_abs = pdf_path.expanduser().resolve()
        stem    = pdf_path.stem
        md_path = pdf_to_md_mod.unique_out_path(out_dir, stem, used_stems)

        try:
            import pymupdf
            import pymupdf4llm

            doc = pymupdf.open(str(pdf_abs))
            images_subdir = f"{md_path.stem}_images"
            write_images  = pdf_to_md_mod.pdf_has_embedded_images(doc)

            import os, contextlib

            @contextlib.contextmanager
            def _cd(p):
                prev = Path.cwd(); os.chdir(p)
                try: yield
                finally: os.chdir(prev)

            with _cd(out_dir):
                md = pymupdf4llm.to_markdown(
                    doc,
                    write_images=write_images,
                    image_path=images_subdir if write_images else "",
                    show_progress=show_progress,
                )

            doc.close()
            md_path.write_text(md, encoding="utf-8")
            print(f"  {pdf_path.name} -> {md_path.name}")
            md_files.append(md_path)

        except Exception as exc:
            print(f"  ERROR converting {pdf_path.name}: {exc}", file=sys.stderr)

    return md_files


def step2_clean(md_files: list[Path], out_dir: Path, aggressive: bool) -> list[Path]:
    """Clean noise from Markdown files."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cleaned: list[Path] = []

    for src in md_files:
        dst = out_dir / src.name
        try:
            md_cleaner_mod.clean_file(src, dst, aggressive=aggressive)
            cleaned.append(dst)
        except Exception as exc:
            print(f"  ERROR cleaning {src.name}: {exc}", file=sys.stderr)

    return cleaned


def step3_tag(
    cleaned_files: list[Path],
    out_dir: Path,
    auto: bool,
    api_key: str | None,
    county: str | None,
    year: str | None,
    doc_type: str | None,
    source_url: str | None,
    sectors: list[str] | None,
) -> list[Path]:
    """Tag Markdown files with YAML frontmatter metadata."""
    out_dir.mkdir(parents=True, exist_ok=True)
    tagged: list[Path] = []

    for src in cleaned_files:
        dst = out_dir / src.name
        try:
            md_tagger_mod.tag_file(
                src=src, dst=dst,
                auto=auto, api_key=api_key,
                county=county, year=year,
                doc_type=doc_type, source_url=source_url,
                sectors=sectors,
            )
            tagged.append(dst)
        except Exception as exc:
            print(f"  ERROR tagging {src.name}: {exc}", file=sys.stderr)

    return tagged


def step4_upload(tagged_files: list[Path], skip_existing: bool) -> None:
    """Upload tagged files to Supabase."""
    for src in tagged_files:
        try:
            supabase_upload_mod.upload_file(src, skip_existing=skip_existing)
        except Exception as exc:
            print(f"  ERROR uploading {src.name}: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bajeti Watch full ingestion pipeline: PDF -> Markdown -> Clean -> Tag -> Supabase."
    )
    parser.add_argument("pdfs", nargs="+", help="PDF files, directories, or globs")
    parser.add_argument("--work-dir", type=Path, default=Path("./pipeline_work"),
                        help="Working directory for intermediate files (default: ./pipeline_work)")
    parser.add_argument("--show-progress", action="store_true", help="Show pymupdf4llm progress")
    parser.add_argument("--aggressive",    action="store_true", help="Aggressive Markdown cleaning")
    parser.add_argument("--auto",          action="store_true", help="Auto-extract metadata via Groq LLM")
    parser.add_argument("--skip-existing", action="store_true", help="Skip files already in Supabase")

    # Metadata overrides
    parser.add_argument("--county",     help="County name")
    parser.add_argument("--year",       help="Financial year e.g. 2023/24")
    parser.add_argument("--doc-type",   choices=md_tagger_mod.VALID_DOC_TYPES)
    parser.add_argument("--source-url", help="Source URL of the PDF")
    parser.add_argument("--sectors",    nargs="+", help="Budget sectors")

    # Step control — useful for debugging one step at a time
    parser.add_argument("--only-step", type=int, choices=[1, 2, 3, 4],
                        help="Run only this step (for debugging)")

    args = parser.parse_args()

    import os
    api_key = os.environ.get("GROQ_API_KEY")
    if args.auto and not api_key:
        print("ERROR: --auto requires GROQ_API_KEY environment variable.", file=sys.stderr)
        return 1

    work_dir = args.work_dir.resolve()
    dirs = {
        1: work_dir / "01_markdown",
        2: work_dir / "02_cleaned",
        3: work_dir / "03_tagged",
    }

    pdf_paths = collect_pdfs(args.pdfs)
    if not pdf_paths:
        print("No PDF files found.", file=sys.stderr)
        return 1

    print(f"\nBajeti Watch Ingestion Pipeline")
    print(f"PDFs to process : {len(pdf_paths)}")
    print(f"Working dir     : {work_dir}")
    print(f"Metadata mode   : {'auto (LLM)' if args.auto else 'manual'}")

    start = time.time()

    # ── Step 1 ────────────────────────────────────────────────────────────
    if args.only_step in (None, 1):
        banner(1, "PDF -> Markdown")
        md_files = step1_convert(pdf_paths, dirs[1], args.show_progress)
        if not md_files:
            print("No Markdown files produced. Aborting.", file=sys.stderr)
            return 1
    else:
        md_files = list(dirs[1].glob("*.md")) if dirs[1].exists() else []

    # ── Step 2 ────────────────────────────────────────────────────────────
    if args.only_step in (None, 2):
        banner(2, "Clean Markdown")
        cleaned_files = step2_clean(md_files, dirs[2], args.aggressive)
        if not cleaned_files:
            print("No files survived cleaning. Aborting.", file=sys.stderr)
            return 1
    else:
        cleaned_files = list(dirs[2].glob("*.md")) if dirs[2].exists() else []

    # ── Step 3 ────────────────────────────────────────────────────────────
    if args.only_step in (None, 3):
        banner(3, "Tag with Metadata")
        tagged_files = step3_tag(
            cleaned_files,
            dirs[3],
            auto=args.auto,
            api_key=api_key,
            county=args.county,
            year=args.year,
            doc_type=args.doc_type,
            source_url=args.source_url,
            sectors=args.sectors,
        )
        if not tagged_files:
            print("No files tagged. Aborting.", file=sys.stderr)
            return 1
    else:
        tagged_files = list(dirs[3].glob("*.md")) if dirs[3].exists() else []

    # ── Step 4 ────────────────────────────────────────────────────────────
    if args.only_step in (None, 4):
        banner(4, "Upload to Supabase")
        step4_upload(tagged_files, skip_existing=args.skip_existing)

    elapsed = time.time() - start
    print(f"\n{DIVIDER}")
    print(f"  Pipeline complete in {elapsed:.1f}s")
    print(f"  {len(pdf_paths)} PDF(s) processed")
    print(DIVIDER)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())