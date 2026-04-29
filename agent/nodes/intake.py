"""
agent/nodes/intake.py

First node in the LangGraph agent.
Receives the raw citizen message and extracts:
  - cleaned query text
  - county hint (if mentioned)
  - financial year hint (if mentioned)
  - query type (county_lookup | sector_query | comparison | general)
"""

from __future__ import annotations
import re
from typing import TypedDict


# ---------------------------------------------------------------------------
# Agent state — shared across all nodes
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    # Input
    raw_message:     str
    channel:         str          # "whatsapp" | "dashboard"

    # Set by intake node
    query:           str          # cleaned query text
    county_hint:     str | None   # extracted county name
    year_hint:       str | None   # extracted financial year
    query_type:      str          # county_lookup | sector_query | comparison | general

    # Set by retrieval node
    chunks:          list[dict]

    # Set by summarizer node
    llm_response:    str

    # Set by formatter node
    final_reply:     str


# ---------------------------------------------------------------------------
# County name list for extraction
# ---------------------------------------------------------------------------

KENYAN_COUNTIES = [
    "Baringo", "Bomet", "Bungoma", "Busia", "Elgeyo-Marakwet", "Embu",
    "Garissa", "Homa Bay", "Isiolo", "Kajiado", "Kakamega", "Kericho",
    "Kiambu", "Kilifi", "Kirinyaga", "Kisii", "Kisumu", "Kitui", "Kwale",
    "Laikipia", "Lamu", "Machakos", "Makueni", "Mandera", "Marsabit",
    "Meru", "Migori", "Mombasa", "Murang'a", "Nairobi", "Nakuru", "Nandi",
    "Narok", "Nyamira", "Nyandarua", "Nyeri", "Samburu", "Siaya",
    "Taita-Taveta", "Tana River", "Tharaka-Nithi", "Trans Nzoia", "Turkana",
    "Uasin Gishu", "Vihiga", "Wajir", "West Pokot",
]

COUNTY_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(c) for c in KENYAN_COUNTIES) + r")\b",
    re.IGNORECASE,
)

YEAR_PATTERN = re.compile(r"\b(20\d{2})[/\-](2\d)\b")

SECTOR_KEYWORDS = [
    "roads", "health", "education", "agriculture", "water", "housing",
    "security", "environment", "tourism", "energy", "finance", "transport",
]

COMPARISON_KEYWORDS = ["compare", "vs", "versus", "difference", "change", "increase", "decrease"]


# ---------------------------------------------------------------------------
# Intake node function
# ---------------------------------------------------------------------------

def intake_node(state: AgentState) -> AgentState:
    """
    Cleans the raw message and extracts structured hints.
    Returns updated state — does not call any external service.
    """
    raw = state["raw_message"].strip()

    # Clean — strip WhatsApp formatting artefacts
    query = re.sub(r"\*+", "", raw)      # bold markers
    query = re.sub(r"\s+", " ", query).strip()

    # Extract county
    county_match = COUNTY_PATTERN.search(query)
    county_hint = county_match.group(1).title() if county_match else None

    # Extract financial year
    year_match = YEAR_PATTERN.search(query)
    year_hint = f"{year_match.group(1)}/{year_match.group(2)}" if year_match else None

    # Classify query type
    lower = query.lower()
    if any(kw in lower for kw in COMPARISON_KEYWORDS):
        query_type = "comparison"
    elif any(kw in lower for kw in SECTOR_KEYWORDS):
        query_type = "sector_query"
    elif county_hint and len(query.split()) <= 3:
        # Just a county name — broad overview request
        query_type = "county_lookup"
    else:
        query_type = "general"

    return {
        **state,
        "query":       query,
        "county_hint": county_hint,
        "year_hint":   year_hint,
        "query_type":  query_type,
    }
