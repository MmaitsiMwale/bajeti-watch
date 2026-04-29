"""
tests/test_cleaner.py — Unit tests for md_cleaner.py

Tests every cleaning rule in isolation so you know exactly
which one breaks if something goes wrong.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "ingestion"))
from md_cleaner import clean_markdown, detect_repeated_lines, is_govt_header


# ---------------------------------------------------------------------------
# Page number removal
# ---------------------------------------------------------------------------

class TestPageNumberRemoval:
    def test_removes_standalone_page_number(self):
        md = "Some content\n\n1\n\nMore content"
        result = clean_markdown(md)
        assert "\n1\n" not in result

    def test_removes_page_N_of_M(self):
        md = "Content\n\nPage 3 of 50\n\nMore content"
        result = clean_markdown(md)
        assert "Page 3 of 50" not in result

    def test_removes_dash_number_dash(self):
        md = "Content\n\n- 12 -\n\nMore content"
        result = clean_markdown(md)
        assert "- 12 -" not in result

    def test_removes_N_of_M_without_page_word(self):
        md = "Content\n\n4 of 100\n\nMore"
        result = clean_markdown(md)
        assert "4 of 100" not in result

    def test_preserves_numbers_in_sentences(self):
        md = "The county received 45,000,000 Kenya Shillings."
        result = clean_markdown(md)
        assert "45,000,000" in result

    def test_preserves_numbers_in_tables(self):
        md = "| Roads | 45,000,000 | 38,000,000 |"
        result = clean_markdown(md)
        assert "45,000,000" in result


# ---------------------------------------------------------------------------
# Government header removal
# ---------------------------------------------------------------------------

class TestGovtHeaderRemoval:
    def test_removes_republic_of_kenya(self):
        md = "REPUBLIC OF KENYA\n\nBudget content here"
        result = clean_markdown(md)
        assert "REPUBLIC OF KENYA" not in result

    def test_removes_national_treasury(self):
        md = "The National Treasury\n\nContent"
        result = clean_markdown(md)
        assert "The National Treasury" not in result

    def test_removes_controller_of_budget(self):
        md = "Controller of Budget\n\nContent"
        result = clean_markdown(md)
        assert "Controller of Budget" not in result

    def test_removes_county_government_of(self):
        md = "County Government of Kisumu\n\nContent"
        result = clean_markdown(md)
        assert "County Government of Kisumu" not in result

    def test_preserves_unrelated_headings(self):
        md = "## Roads and Infrastructure\n\nContent about roads"
        result = clean_markdown(md)
        assert "Roads and Infrastructure" in result


# ---------------------------------------------------------------------------
# Separator noise removal
# ---------------------------------------------------------------------------

class TestSeparatorRemoval:
    def test_removes_dash_separators(self):
        md = "Content\n\n-------------------\n\nMore content"
        result = clean_markdown(md)
        assert "-------------------" not in result

    def test_removes_underscore_separators(self):
        md = "Content\n\n___________\n\nMore"
        result = clean_markdown(md)
        assert "___________" not in result

    def test_removes_equals_separators(self):
        md = "Content\n\n===========\n\nMore"
        result = clean_markdown(md)
        assert "===========" not in result

    def test_preserves_markdown_table_dividers(self):
        # Markdown table rows with | should survive
        md = "| Col1 | Col2 |\n|---|---|\n| val | val |"
        result = clean_markdown(md)
        assert "|---|---|" in result


# ---------------------------------------------------------------------------
# Blank line collapsing
# ---------------------------------------------------------------------------

class TestBlankLineCollapsing:
    def test_collapses_many_blank_lines_to_two(self):
        md = "Content\n\n\n\n\n\nMore content"
        result = clean_markdown(md)
        # Should not have more than 2 consecutive blank lines
        assert "\n\n\n\n" not in result

    def test_preserves_single_blank_lines(self):
        md = "Paragraph one.\n\nParagraph two."
        result = clean_markdown(md)
        assert "Paragraph one." in result
        assert "Paragraph two." in result

    def test_strips_leading_blank_lines(self):
        md = "\n\n\nActual content"
        result = clean_markdown(md)
        assert result.startswith("Actual content")

    def test_strips_trailing_blank_lines(self):
        md = "Actual content\n\n\n\n"
        result = clean_markdown(md)
        assert result.strip().endswith("Actual content")


# ---------------------------------------------------------------------------
# pymupdf4llm page comment removal
# ---------------------------------------------------------------------------

class TestPageCommentRemoval:
    def test_removes_page_comment(self):
        md = "<!-- page 1 -->\n\nContent\n\n<!-- page 2 -->\n\nMore"
        result = clean_markdown(md)
        assert "<!-- page" not in result

    def test_preserves_content_around_page_comment(self):
        md = "<!-- page 5 -->\n\nImportant budget line"
        result = clean_markdown(md)
        assert "Important budget line" in result


# ---------------------------------------------------------------------------
# Repeated line detection
# ---------------------------------------------------------------------------

class TestRepeatedLineDetection:
    def test_detects_repeated_header(self):
        # Simulate a header repeated across many "pages"
        repeated = "KISUMU COUNTY BUDGET 2023/24"
        lines = []
        for i in range(10):
            lines.append(f"<!-- page {i+1} -->")
            lines.append(repeated)
            lines.append("Some unique budget content for section " + str(i))
        repeated_set = detect_repeated_lines(lines, threshold=0.3)
        assert repeated in repeated_set

    def test_does_not_flag_unique_lines(self):
        lines = [
            "<!-- page 1 -->",
            "Roads allocation: Ksh 45,000,000",
            "<!-- page 2 -->",
            "Health allocation: Ksh 80,000,000",
            "<!-- page 3 -->",
            "Education allocation: Ksh 60,000,000",
        ]
        repeated_set = detect_repeated_lines(lines, threshold=0.3)
        assert "Roads allocation: Ksh 45,000,000" not in repeated_set

    def test_does_not_flag_table_rows(self):
        lines = ["<!-- page 1 -->"] * 5 + ["| Roads | 45M |"] * 5
        repeated_set = detect_repeated_lines(lines)
        assert "| Roads | 45M |" not in repeated_set  # table rows excluded


# ---------------------------------------------------------------------------
# Realistic budget document
# ---------------------------------------------------------------------------

class TestRealisticBudgetDocument:
    SAMPLE = """\
<!-- page 1 -->

REPUBLIC OF KENYA

County Government of Kisumu

COUNTY FISCAL STRATEGY PAPER 2023/24

Page 1 of 45

-------------------

## 1. Introduction

The County Government of Kisumu presents the County Fiscal Strategy Paper for the
financial year 2023/24. Total budget allocation stands at Ksh 8.2 billion.

<!-- page 2 -->

REPUBLIC OF KENYA

County Government of Kisumu

Page 2 of 45

-------------------

## 2. Budget Allocation by Sector

| Sector          | Approved (Ksh) | Previous Year (Ksh) |
|---|---|---|
| Roads           | 800,000,000    | 720,000,000         |
| Health          | 1,100,000,000  | 980,000,000         |
| Education       | 650,000,000    | 600,000,000         |

<!-- page 3 -->

REPUBLIC OF KENYA

County Government of Kisumu

Page 3 of 45

The roads sector received an increase of 11.1% from the previous financial year.
"""

    def test_removes_all_noise(self):
        result = clean_markdown(self.SAMPLE)
        assert "REPUBLIC OF KENYA" not in result
        assert "Page 1 of 45" not in result
        assert "<!-- page" not in result
        assert "-------------------" not in result

    def test_preserves_all_content(self):
        result = clean_markdown(self.SAMPLE)
        assert "COUNTY FISCAL STRATEGY PAPER" in result or "County Fiscal Strategy Paper" in result
        assert "8.2 billion" in result
        assert "800,000,000" in result
        assert "11.1%" in result

    def test_preserves_tables(self):
        result = clean_markdown(self.SAMPLE)
        assert "| Roads" in result
        assert "| Health" in result
        assert "|---|---|" in result

    def test_output_is_shorter_than_input(self):
        result = clean_markdown(self.SAMPLE)
        assert len(result) < len(self.SAMPLE)
