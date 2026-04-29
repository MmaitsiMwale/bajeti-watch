"""
tests/test_tagger.py — Unit tests for md_tagger.py

Tests frontmatter building, metadata merging, and file tagging
without needing any API keys or external services.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "ingestion"))
from md_tagger import (
    build_frontmatter,
    build_metadata,
    has_frontmatter,
    strip_existing_frontmatter,
    attach_frontmatter,
)


SAMPLE_BODY = """\
## 1. Introduction

The County Government of Kisumu presents the budget for 2023/24.
Total allocation: Ksh 8.2 billion.

| Sector  | Allocation (Ksh) |
|---|---|
| Roads   | 800,000,000      |
| Health  | 1,100,000,000    |
"""


# ---------------------------------------------------------------------------
# Frontmatter building
# ---------------------------------------------------------------------------

class TestFrontmatterBuilding:
    def test_build_frontmatter_produces_valid_yaml(self):
        meta = {"title": "Kisumu Budget", "county": "Kisumu", "financial_year": "2023/24"}
        fm = build_frontmatter(meta)
        assert fm.startswith("---\n")
        assert fm.endswith("---\n\n")
        # Parse it back to confirm valid YAML
        inner = fm.strip().lstrip("---").rstrip("---").strip()
        parsed = yaml.safe_load(inner)
        assert parsed["county"] == "Kisumu"

    def test_build_frontmatter_preserves_all_fields(self):
        meta = {
            "title": "Test Doc",
            "county": "Nairobi",
            "financial_year": "2024/25",
            "document_type": "county_budget",
            "source_url": "https://example.com/budget.pdf",
            "sectors": ["roads", "health"],
        }
        fm = build_frontmatter(meta)
        assert "Nairobi" in fm
        assert "2024/25" in fm
        assert "county_budget" in fm
        assert "roads" in fm

    def test_build_frontmatter_handles_none_values(self):
        meta = {"title": None, "county": "Kisumu", "financial_year": None}
        fm = build_frontmatter(meta)
        # Should not raise and should still produce valid YAML
        assert "county: Kisumu" in fm


# ---------------------------------------------------------------------------
# Frontmatter detection and stripping
# ---------------------------------------------------------------------------

class TestFrontmatterDetection:
    def test_detects_frontmatter_present(self):
        text = "---\ntitle: Test\n---\n\nBody content"
        assert has_frontmatter(text) is True

    def test_detects_no_frontmatter(self):
        text = "# Heading\n\nBody content without frontmatter"
        assert has_frontmatter(text) is False

    def test_strips_existing_frontmatter(self):
        text = "---\ntitle: Old\ncounty: Kisumu\n---\n\nBody content here"
        stripped = strip_existing_frontmatter(text)
        assert "Old" not in stripped
        assert "Body content here" in stripped

    def test_strip_leaves_body_intact(self):
        body = "## Budget\n\nTotal: Ksh 8.2 billion"
        text = f"---\ntitle: Test\n---\n\n{body}"
        stripped = strip_existing_frontmatter(text)
        assert "8.2 billion" in stripped


# ---------------------------------------------------------------------------
# Metadata building — manual overrides
# ---------------------------------------------------------------------------

class TestMetadataBuilding:
    def test_manual_values_used_when_no_extraction(self):
        meta = build_metadata(
            extracted=None,
            county="Mombasa",
            year="2022/23",
            doc_type="county_budget",
            source_url="https://cob.go.ke/mombasa.pdf",
            sectors=["tourism", "health"],
            filename="mombasa_2022.md",
        )
        assert meta["county"] == "Mombasa"
        assert meta["financial_year"] == "2022/23"
        assert meta["document_type"] == "county_budget"
        assert "tourism" in meta["sectors"]

    def test_manual_values_override_extracted(self):
        extracted = {"county": "Wrong County", "financial_year": "1999/00"}
        meta = build_metadata(
            extracted=extracted,
            county="Kisumu",        # manual override
            year="2023/24",         # manual override
            doc_type=None,
            source_url=None,
            sectors=None,
            filename="test.md",
        )
        assert meta["county"] == "Kisumu"
        assert meta["financial_year"] == "2023/24"

    def test_extracted_values_used_when_no_manual(self):
        extracted = {
            "title": "Nairobi County Budget",
            "county": "Nairobi",
            "financial_year": "2023/24",
            "document_type": "county_budget",
            "sectors": ["roads", "education"],
        }
        meta = build_metadata(
            extracted=extracted,
            county=None,
            year=None,
            doc_type=None,
            source_url=None,
            sectors=None,
            filename="nairobi.md",
        )
        assert meta["county"] == "Nairobi"
        assert meta["financial_year"] == "2023/24"
        assert "roads" in meta["sectors"]

    def test_ingested_at_is_valid_iso_timestamp(self):
        meta = build_metadata(
            extracted=None, county="Kisumu", year="2023/24",
            doc_type="county_budget", source_url=None,
            sectors=None, filename="test.md",
        )
        # Should parse without error
        dt = datetime.fromisoformat(meta["ingested_at"])
        assert dt.tzinfo is not None  # must be timezone-aware

    def test_source_file_stored_in_metadata(self):
        meta = build_metadata(
            extracted=None, county="Kisumu", year="2023/24",
            doc_type=None, source_url=None,
            sectors=None, filename="kisumu_budget_clean.md",
        )
        assert meta["source_file"] == "kisumu_budget_clean.md"

    def test_empty_sectors_defaults_to_empty_list(self):
        meta = build_metadata(
            extracted=None, county="Kisumu", year="2023/24",
            doc_type=None, source_url=None,
            sectors=None, filename="test.md",
        )
        assert meta["sectors"] == []


# ---------------------------------------------------------------------------
# attach_frontmatter
# ---------------------------------------------------------------------------

class TestAttachFrontmatter:
    def test_prepends_frontmatter_to_body(self):
        meta = {"county": "Kisumu", "financial_year": "2023/24"}
        result = attach_frontmatter(SAMPLE_BODY, meta)
        assert result.startswith("---\n")
        assert "8.2 billion" in result

    def test_replaces_existing_frontmatter(self):
        old_text = "---\ncounty: OldCounty\n---\n\n" + SAMPLE_BODY
        meta = {"county": "Kisumu", "financial_year": "2023/24"}
        result = attach_frontmatter(old_text, meta)
        assert "OldCounty" not in result
        assert "Kisumu" in result
        assert "8.2 billion" in result

    def test_body_content_preserved_intact(self):
        meta = {"county": "Kisumu"}
        result = attach_frontmatter(SAMPLE_BODY, meta)
        assert "800,000,000" in result
        assert "| Roads" in result


# ---------------------------------------------------------------------------
# Round-trip: attach then parse
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_attach_then_parse_recovers_metadata(self):
        meta = {
            "title": "Kisumu County Budget 2023/24",
            "county": "Kisumu",
            "financial_year": "2023/24",
            "document_type": "county_budget",
            "source_url": "https://cob.go.ke/kisumu.pdf",
            "sectors": ["roads", "health", "education"],
            "ingested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        tagged = attach_frontmatter(SAMPLE_BODY, meta)

        # parse_tagged_markdown is defined in supabase_uploader — simulate it
        import re
        FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
        m = FM_RE.match(tagged)
        assert m is not None
        parsed_meta = yaml.safe_load(m.group(1))
        body = tagged[m.end():].lstrip()

        assert parsed_meta["county"] == "Kisumu"
        assert parsed_meta["financial_year"] == "2023/24"
        assert "roads" in parsed_meta["sectors"]
        assert "8.2 billion" in body
