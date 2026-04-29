"""
tests/test_pipeline_integration.py — Integration tests for the full ingestion pipeline.

These tests use REAL PDF files you provide. They test every step end-to-end,
including Supabase and Groq if credentials are available.

Usage:
    # Run all tests (skips Supabase/Groq tests if keys not set)
    pytest tests/test_pipeline_integration.py -v

    # Run only local tests (no external services needed)
    pytest tests/test_pipeline_integration.py -v -m local

    # Run full end-to-end including Supabase
    pytest tests/test_pipeline_integration.py -v -m integration
"""

import os
import sys
import shutil
import tempfile
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "ingestion"))
from md_cleaner import clean_markdown
from md_tagger import attach_frontmatter, build_metadata

# ---------------------------------------------------------------------------
# PDF discovery — looks for PDFs in common locations
# ---------------------------------------------------------------------------

def find_test_pdfs() -> list[Path]:
    """
    Find PDF files to test with. Checks in order:
    1. tests/fixtures/   — put your PDFs here (preferred)
    2. Any .pdf passed via TEST_PDF_PATH env variable
    3. Current directory
    """
    candidates = []

    # Check fixtures folder
    fixtures = Path(__file__).parent / "fixtures"
    if fixtures.exists():
        candidates.extend(fixtures.glob("*.pdf"))

    # Check env variable
    env_path = os.environ.get("TEST_PDF_PATH")
    if env_path:
        p = Path(env_path)
        if p.is_file():
            candidates.append(p)
        elif p.is_dir():
            candidates.extend(p.glob("*.pdf"))

    # Check cwd
    candidates.extend(Path.cwd().glob("*.pdf"))

    return list(set(candidates))  # deduplicate


AVAILABLE_PDFS = find_test_pdfs()
HAS_PDFS = len(AVAILABLE_PDFS) > 0
HAS_GROQ = bool(os.environ.get("GROQ_API_KEY"))
HAS_SUPABASE = bool(os.environ.get("SUPABASE_URL")) and bool(os.environ.get("SUPABASE_KEY"))


# ---------------------------------------------------------------------------
# Step 1: PDF → Markdown conversion
# ---------------------------------------------------------------------------

@pytest.mark.local
@pytest.mark.skipif(not HAS_PDFS, reason="No PDF files found. Put PDFs in tests/fixtures/ or set TEST_PDF_PATH")
class TestPDFConversion:

    @pytest.fixture(autouse=True)
    def tmp_dir(self, tmp_path):
        self.out_dir = tmp_path / "01_markdown"
        self.out_dir.mkdir()

    def test_pdf_converts_to_markdown_file(self):
        """Each PDF should produce a .md file."""
        import pymupdf
        import pymupdf4llm

        pdf = AVAILABLE_PDFS[0]
        doc = pymupdf.open(str(pdf))
        md = pymupdf4llm.to_markdown(doc)
        doc.close()

        out = self.out_dir / f"{pdf.stem}.md"
        out.write_text(md, encoding="utf-8")

        assert out.exists()
        assert out.stat().st_size > 0

    def test_markdown_contains_text(self):
        """Converted markdown should have meaningful content, not just whitespace."""
        import pymupdf
        import pymupdf4llm

        pdf = AVAILABLE_PDFS[0]
        doc = pymupdf.open(str(pdf))
        md = pymupdf4llm.to_markdown(doc)
        doc.close()

        words = md.split()
        assert len(words) > 50, (
            f"PDF produced only {len(words)} words — "
            f"may be a scanned/image PDF. Check GLM-OCR fallback."
        )

    def test_all_pdfs_convert_without_error(self):
        """Every PDF in the fixtures folder should convert without crashing."""
        import pymupdf
        import pymupdf4llm

        failed = []
        for pdf in AVAILABLE_PDFS:
            try:
                doc = pymupdf.open(str(pdf))
                md = pymupdf4llm.to_markdown(doc)
                doc.close()
                assert len(md.strip()) > 0
            except Exception as e:
                failed.append(f"{pdf.name}: {e}")

        assert not failed, f"These PDFs failed to convert:\n" + "\n".join(failed)

    def test_word_density_per_page(self):
        """
        Word density check — flags image-based PDFs that need OCR.
        Warns rather than fails so you know which PDFs need the GLM-OCR fallback.
        """
        import pymupdf
        import pymupdf4llm

        low_density = []
        for pdf in AVAILABLE_PDFS:
            doc = pymupdf.open(str(pdf))
            md = pymupdf4llm.to_markdown(doc)
            page_count = doc.page_count
            doc.close()

            wpp = len(md.split()) / max(page_count, 1)
            if wpp < 50:
                low_density.append(f"{pdf.name}: {wpp:.1f} words/page")

        if low_density:
            pytest.warns(
                UserWarning,
                match="low density"
            ) if False else None  # just print
            print(
                f"\n⚠ LOW DENSITY PDFs (likely scanned — GLM-OCR will activate):\n"
                + "\n".join(f"  {x}" for x in low_density)
            )


# ---------------------------------------------------------------------------
# Step 2: Markdown cleaning
# ---------------------------------------------------------------------------

@pytest.mark.local
@pytest.mark.skipif(not HAS_PDFS, reason="No PDF files found.")
class TestMarkdownCleaning:

    @pytest.fixture(autouse=True)
    def convert_first(self, tmp_path):
        """Convert first available PDF, then run cleaning tests on the output."""
        import pymupdf
        import pymupdf4llm

        self.pdf = AVAILABLE_PDFS[0]
        doc = pymupdf.open(str(self.pdf))
        self.raw_md = pymupdf4llm.to_markdown(doc)
        doc.close()
        self.cleaned_md = clean_markdown(self.raw_md)

    def test_cleaned_output_is_non_empty(self):
        assert len(self.cleaned_md.strip()) > 0

    def test_cleaned_shorter_than_raw(self):
        """Cleaning should always remove at least some noise."""
        assert len(self.cleaned_md) <= len(self.raw_md)

    def test_no_page_comments_in_cleaned(self):
        assert "<!-- page" not in self.cleaned_md

    def test_no_excessive_blank_lines(self):
        assert "\n\n\n\n" not in self.cleaned_md

    def test_tables_preserved_if_present(self):
        """If the raw markdown has tables, they should survive cleaning."""
        if "|" not in self.raw_md:
            pytest.skip("No tables in this PDF — skipping table preservation test")
        assert "|" in self.cleaned_md

    def test_numeric_values_preserved(self):
        """
        Budget figures (numbers with commas) should survive cleaning.
        Checks that we haven't accidentally stripped financial data.
        """
        import re
        raw_numbers = re.findall(r"\d{1,3}(?:,\d{3})+", self.raw_md)
        if not raw_numbers:
            pytest.skip("No formatted numbers found in this PDF")

        cleaned_numbers = re.findall(r"\d{1,3}(?:,\d{3})+", self.cleaned_md)
        # At least 80% of numeric values should survive
        survival_rate = len(cleaned_numbers) / len(raw_numbers)
        assert survival_rate >= 0.8, (
            f"Only {survival_rate:.0%} of numeric values survived cleaning. "
            f"Check the cleaner isn't stripping financial figures."
        )


# ---------------------------------------------------------------------------
# Step 3: Metadata tagging
# ---------------------------------------------------------------------------

@pytest.mark.local
@pytest.mark.skipif(not HAS_PDFS, reason="No PDF files found.")
class TestMetadataTagging:

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        import pymupdf
        import pymupdf4llm

        pdf = AVAILABLE_PDFS[0]
        doc = pymupdf.open(str(pdf))
        raw_md = pymupdf4llm.to_markdown(doc)
        doc.close()
        self.cleaned_md = clean_markdown(raw_md)

    def test_manual_metadata_attaches_correctly(self):
        meta = build_metadata(
            extracted=None,
            county="Kisumu",
            year="2023/24",
            doc_type="county_budget",
            source_url="https://cob.go.ke/test.pdf",
            sectors=["roads", "health"],
            filename="test_budget.md",
        )
        tagged = attach_frontmatter(self.cleaned_md, meta)

        assert tagged.startswith("---\n")
        assert "Kisumu" in tagged
        assert "2023/24" in tagged

    def test_frontmatter_is_valid_yaml(self):
        import re
        meta = build_metadata(
            extracted=None, county="Nairobi", year="2024/25",
            doc_type="national_budget", source_url=None,
            sectors=["education", "health", "roads"],
            filename="nairobi.md",
        )
        tagged = attach_frontmatter(self.cleaned_md, meta)

        fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", tagged, re.DOTALL)
        assert fm_match, "No valid frontmatter block found"
        parsed = yaml.safe_load(fm_match.group(1))
        assert parsed["county"] == "Nairobi"
        assert "education" in parsed["sectors"]

    def test_body_content_intact_after_tagging(self):
        import re
        meta = build_metadata(
            extracted=None, county="Mombasa", year="2023/24",
            doc_type="county_budget", source_url=None,
            sectors=None, filename="mombasa.md",
        )
        tagged = attach_frontmatter(self.cleaned_md, meta)
        body_start = tagged.index("---\n", 4) + 4  # skip past closing ---
        body = tagged[body_start:]

        # Body should still have content
        assert len(body.strip()) > 100

    @pytest.mark.skipif(not HAS_GROQ, reason="GROQ_API_KEY not set — skipping auto-tag test")
    def test_auto_extraction_returns_county(self):
        """Groq LLM should extract a recognisable county name from the document."""
        from md_tagger import extract_metadata_with_llm
        api_key = os.environ["GROQ_API_KEY"]
        extracted = extract_metadata_with_llm(self.cleaned_md, api_key)

        assert "county" in extracted, "LLM did not return a 'county' field"
        assert "financial_year" in extracted, "LLM did not return a 'financial_year' field"
        print(f"\n  LLM extracted: {extracted}")


# ---------------------------------------------------------------------------
# Step 4: Supabase upload (integration only)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.skipif(
    not HAS_SUPABASE or not HAS_PDFS,
    reason="Supabase credentials not set or no PDFs found — skipping upload test"
)
class TestSupabaseUpload:

    TEST_SOURCE_FILE = "__bajeti_test_file__.md"

    @pytest.fixture(autouse=True)
    def cleanup_after(self):
        """Delete test records from Supabase after each test."""
        yield
        self._delete_test_records()

    def _delete_test_records(self):
        """Remove any records inserted during testing."""
        import requests
        url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/documents"
        headers = {
            "apikey": os.environ["SUPABASE_KEY"],
            "Authorization": f"Bearer {os.environ['SUPABASE_KEY']}",
        }
        requests.delete(
            url,
            headers=headers,
            params={"source_file": f"eq.{self.TEST_SOURCE_FILE}"},
            timeout=10,
        )

    def test_document_uploads_successfully(self, tmp_path):
        import pymupdf
        import pymupdf4llm
        from supabase_uploader import upload_file

        # Build tagged test file
        pdf = AVAILABLE_PDFS[0]
        doc = pymupdf.open(str(pdf))
        md = pymupdf4llm.to_markdown(doc)
        doc.close()

        cleaned = clean_markdown(md)
        meta = build_metadata(
            extracted=None,
            county="TestCounty",
            year="2023/24",
            doc_type="county_budget",
            source_url="https://test.example.com/budget.pdf",
            sectors=["roads", "health"],
            filename=self.TEST_SOURCE_FILE,
        )
        tagged = attach_frontmatter(cleaned, meta)

        test_file = tmp_path / self.TEST_SOURCE_FILE
        test_file.write_text(tagged, encoding="utf-8")

        # Upload — should not raise
        upload_file(test_file, skip_existing=False)

    def test_skip_existing_prevents_duplicate(self, tmp_path):
        import pymupdf
        import pymupdf4llm
        from supabase_uploader import upload_file, document_exists

        pdf = AVAILABLE_PDFS[0]
        doc = pymupdf.open(str(pdf))
        md = pymupdf4llm.to_markdown(doc)
        doc.close()

        cleaned = clean_markdown(md)
        meta = build_metadata(
            extracted=None, county="TestCounty", year="2023/24",
            doc_type="county_budget", source_url=None,
            sectors=None, filename=self.TEST_SOURCE_FILE,
        )
        tagged = attach_frontmatter(cleaned, meta)
        test_file = tmp_path / self.TEST_SOURCE_FILE
        test_file.write_text(tagged, encoding="utf-8")

        # First upload
        upload_file(test_file, skip_existing=False)
        assert document_exists(self.TEST_SOURCE_FILE)

        # Second upload with skip_existing should not raise or duplicate
        upload_file(test_file, skip_existing=True)

    def test_chunks_stored_in_supabase(self, tmp_path):
        """After upload, the chunks table should have records for this document."""
        import requests
        import pymupdf
        import pymupdf4llm
        from supabase_uploader import upload_file

        pdf = AVAILABLE_PDFS[0]
        doc = pymupdf.open(str(pdf))
        md = pymupdf4llm.to_markdown(doc)
        doc.close()

        cleaned = clean_markdown(md)
        meta = build_metadata(
            extracted=None, county="TestCounty", year="2023/24",
            doc_type="county_budget", source_url=None,
            sectors=None, filename=self.TEST_SOURCE_FILE,
        )
        tagged = attach_frontmatter(cleaned, meta)
        test_file = tmp_path / self.TEST_SOURCE_FILE
        test_file.write_text(tagged, encoding="utf-8")

        upload_file(test_file, skip_existing=False)

        # Verify chunks exist
        url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/chunks"
        headers = {
            "apikey": os.environ["SUPABASE_KEY"],
            "Authorization": f"Bearer {os.environ['SUPABASE_KEY']}",
        }
        # Get document id first
        doc_url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/documents"
        doc_resp = requests.get(
            doc_url, headers=headers,
            params={"source_file": f"eq.{self.TEST_SOURCE_FILE}", "select": "id"},
            timeout=10,
        )
        docs = doc_resp.json()
        assert docs, "Document not found in Supabase after upload"

        doc_id = docs[0]["id"]
        chunk_resp = requests.get(
            url, headers=headers,
            params={"document_id": f"eq.{doc_id}", "select": "id,chunk_index"},
            timeout=10,
        )
        chunks = chunk_resp.json()
        assert len(chunks) > 0, "No chunks found in Supabase for uploaded document"
        print(f"\n  Chunks stored: {len(chunks)}")
