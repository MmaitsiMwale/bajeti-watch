#!/usr/bin/env python3
"""
Convert PDF files to Markdown using pymupdf4llm. Writes .md files to the
current working directory (or --out-dir) by default. Extracted images go to
``<markdown_basename>_images`` under that output directory when the PDF has
embedded images (PyMuPDF ``page.get_images()``); otherwise no folder is created.

GLM-OCR FALLBACK (requires Ollama running locally with glm-ocr pulled):
  If the extracted markdown has fewer than --min-words-per-page words per page
  on average, the PDF is re-processed page-by-page via GLM-OCR.
  Install:  ollama pull glm-ocr
  Deps:     pip install ollama pymupdf pymupdf4llm
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import glob
import io
import os
import sys
from pathlib import Path

import pymupdf
import pymupdf4llm

# ---------------------------------------------------------------------------
# GLM-OCR via Ollama  (imported lazily so the script still works without it)
# ---------------------------------------------------------------------------
try:
    import ollama as _ollama_lib
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def working_directory(path: Path):
    prev = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


def collect_pdfs(paths: list[str]) -> list[Path]:
    """Expand paths: files, directories (non-recursive), and globs."""
    seen: set[Path] = set()
    out: list[Path] = []

    for raw in paths:
        p = Path(raw).expanduser()
        if any(c in raw for c in "*?[]"):
            for match in sorted(glob.glob(raw, recursive=True)):
                mp = Path(match)
                if mp.is_file() and mp.suffix.lower() == ".pdf":
                    rp = mp.resolve()
                    if rp not in seen:
                        seen.add(rp)
                        out.append(mp)
            continue

        if not p.exists():
            print(f"skip (not found): {raw}", file=sys.stderr)
            continue

        if p.is_dir():
            for child in sorted(p.iterdir()):
                if child.is_file() and child.suffix.lower() == ".pdf":
                    rp = child.resolve()
                    if rp not in seen:
                        seen.add(rp)
                        out.append(child)
        elif p.suffix.lower() == ".pdf":
            rp = p.resolve()
            if rp not in seen:
                seen.add(rp)
                out.append(p)
        else:
            print(f"skip (not a PDF): {raw}", file=sys.stderr)

    return out


def unique_out_path(out_dir: Path, stem: str, used: dict[str, int]) -> Path:
    """Avoid overwriting when multiple PDFs share the same basename."""
    n = used.get(stem, 0)
    used[stem] = n + 1
    if n == 0:
        return out_dir / f"{stem}.md"
    return out_dir / f"{stem}_{n + 1}.md"


def pdf_has_embedded_images(doc: pymupdf.Document) -> bool:
    """True if any page references embedded images (xref bitmaps)."""
    return any(doc[pno].get_images() for pno in range(doc.page_count))


def remove_dir_if_empty(path: Path) -> None:
    try:
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Quality check  — did pymupdf4llm actually get real text?
# ---------------------------------------------------------------------------

def words_per_page(md_text: str, page_count: int) -> float:
    """Average word count per page from the extracted markdown."""
    if page_count == 0:
        return 0.0
    word_count = len(md_text.split())
    return word_count / page_count


def is_low_quality(md_text: str, page_count: int, threshold: int) -> bool:
    """
    Returns True when the markdown looks like it came from a scanned/image PDF.
    'threshold' is the minimum acceptable words-per-page average.
    """
    wpp = words_per_page(md_text, page_count)
    return wpp < threshold


# ---------------------------------------------------------------------------
# GLM-OCR fallback via Ollama
# ---------------------------------------------------------------------------

def page_to_png_bytes(page: pymupdf.Page, dpi: int = 150) -> bytes:
    """
    Render a single PDF page to PNG bytes.
    dpi=150 is a good balance between speed and readability for GLM-OCR.
    Increase to 200-300 for very small text or dense tables.
    """
    mat = pymupdf.Matrix(dpi / 72, dpi / 72)   # 72 is the default PDF dpi
    pix = page.get_pixmap(matrix=mat, alpha=False)
    return pix.tobytes("png")


def ocr_page_with_glm(png_bytes: bytes, task: str = "Text Recognition") -> str:
    """
    Send a single page image to GLM-OCR running in Ollama.
    task options: "Text Recognition" | "Table Recognition" | "Figure Recognition"
    """
    b64 = base64.standard_b64encode(png_bytes).decode()
    response = _ollama_lib.chat(
        model="glm-ocr",
        messages=[
            {
                "role": "user",
                "content": task + ":",   # GLM-OCR prompt format
                "images": [b64],
            }
        ],
    )
    return response.message.content.strip()


def convert_with_glm_ocr(doc: pymupdf.Document, dpi: int = 150) -> str:
    """
    Convert every page via GLM-OCR and stitch into a single markdown string.
    Automatically picks Table Recognition for pages that have tables,
    otherwise defaults to Text Recognition.
    """
    pages_md: list[str] = []
    total = doc.page_count

    for pno in range(total):
        page = doc[pno]
        print(f"  GLM-OCR: page {pno + 1}/{total} ...", end="\r", flush=True)

        png = page_to_png_bytes(page, dpi=dpi)

        # Simple heuristic: if the page has table-like structure detected by
        # pymupdf (find_tables), use Table Recognition mode.
        try:
            tabs = page.find_tables()
            task = "Table Recognition" if tabs.tables else "Text Recognition"
        except Exception:
            task = "Text Recognition"

        text = ocr_page_with_glm(png, task=task)
        pages_md.append(f"<!-- page {pno + 1} -->\n{text}")

    print()  # newline after progress
    return "\n\n---\n\n".join(pages_md)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Convert PDFs to Markdown with pymupdf4llm; writes .md under --out-dir. "
            "Falls back to GLM-OCR (via Ollama) for scanned/image-heavy PDFs. "
            "Creates <name>_images/ only for PDFs with embedded images."
        ),
    )
    parser.add_argument(
        "pdfs",
        nargs="+",
        help="PDF file paths, directories containing PDFs, or globs (e.g. *.pdf)",
    )
    parser.add_argument(
        "-o",
        "--out-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory for .md output (default: current working directory)",
    )
    parser.add_argument(
        "--show-progress",
        action="store_true",
        help="Pass show_progress=True to pymupdf4llm.to_markdown",
    )
    # --- GLM-OCR options ---
    parser.add_argument(
        "--no-ocr-fallback",
        action="store_true",
        help="Disable GLM-OCR fallback; always use pymupdf4llm only",
    )
    parser.add_argument(
        "--min-words-per-page",
        type=int,
        default=50,
        help=(
            "If extracted markdown has fewer than this many words per page on average, "
            "fall back to GLM-OCR. Default: 50"
        ),
    )
    parser.add_argument(
        "--ocr-dpi",
        type=int,
        default=150,
        help="DPI when rendering PDF pages to images for GLM-OCR. Default: 150",
    )
    args = parser.parse_args()

    out_dir = args.out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    pdf_list = collect_pdfs([str(p) for p in args.pdfs])
    if not pdf_list:
        print("No PDF files to convert.", file=sys.stderr)
        return 1

    # Warn early if fallback is wanted but ollama isn't installed
    use_ocr_fallback = not args.no_ocr_fallback
    if use_ocr_fallback and not OLLAMA_AVAILABLE:
        print(
            "WARNING: ollama Python package not found. GLM-OCR fallback disabled.\n"
            "         Install with:  pip install ollama",
            file=sys.stderr,
        )
        use_ocr_fallback = False

    used_stems: dict[str, int] = {}
    errors = 0

    for pdf_path in pdf_list:
        pdf_abs = pdf_path.expanduser().resolve()
        stem = pdf_path.stem
        md_path = unique_out_path(out_dir, stem, used_stems)
        images_subdir = f"{md_path.stem}_images"
        images_dir = out_dir / images_subdir

        try:
            doc = pymupdf.open(str(pdf_abs))
            used_glm = False

            try:
                write_images = pdf_has_embedded_images(doc)

                with working_directory(out_dir):
                    md = pymupdf4llm.to_markdown(
                        doc,
                        write_images=write_images,
                        image_path=images_subdir if write_images else "",
                        show_progress=args.show_progress,
                    )

                # ── Quality gate ──────────────────────────────────────────
                if use_ocr_fallback and is_low_quality(
                    md, doc.page_count, args.min_words_per_page
                ):
                    wpp = words_per_page(md, doc.page_count)
                    print(
                        f"  ⚠  Low text density ({wpp:.1f} words/page) — "
                        f"switching to GLM-OCR for: {pdf_path}"
                    )
                    try:
                        md = convert_with_glm_ocr(doc, dpi=args.ocr_dpi)
                        used_glm = True
                    except Exception as ocr_err:
                        print(
                            f"  GLM-OCR failed ({ocr_err}), keeping pymupdf4llm output.",
                            file=sys.stderr,
                        )

            finally:
                doc.close()

            md_path.write_text(md, encoding="utf-8")
            if write_images and not used_glm:
                remove_dir_if_empty(images_dir)

            # ── Status line ───────────────────────────────────────────────
            suffix = " [glm-ocr]" if used_glm else ""
            if not used_glm and write_images and images_dir.is_dir():
                print(f"{pdf_path} -> {md_path} (images: {images_dir}){suffix}")
            else:
                print(f"{pdf_path} -> {md_path}{suffix}")

        except Exception as e:
            print(f"error: {pdf_path}: {e}", file=sys.stderr)
            errors += 1
            remove_dir_if_empty(images_dir)

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
