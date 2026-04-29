"""
agent/nodes/retrieval.py

Second node in the LangGraph agent.
Embeds the citizen's query and retrieves the most relevant
budget chunks from Supabase pgvector.
"""

from __future__ import annotations

from ..tools.supabase_search import embed_query, search_chunks
from .intake import AgentState


# How many chunks to retrieve — 5 is a good balance between
# context richness and staying within Llama's prompt limits
DEFAULT_MATCH_COUNT = 5


def retrieval_node(state: AgentState) -> AgentState:
    """
    1. Embeds the cleaned query
    2. Searches pgvector for the most semantically similar chunks
    3. Filters by county and year if extracted by the intake node
    """
    query      = state["query"]
    county     = state.get("county_hint")
    year       = state.get("year_hint")

    # For a county_lookup (just a county name), broaden the query
    # so we get a general overview rather than one narrow match
    if state.get("query_type") == "county_lookup" and county:
        search_query = f"{county} county budget allocation sectors overview"
    else:
        search_query = query

    # Embed
    embedding = embed_query(search_query)

    # Search
    chunks = search_chunks(
        query_embedding=embedding,
        county_filter=county,
        year_filter=year,
        match_count=DEFAULT_MATCH_COUNT,
    )

    return {
        **state,
        "chunks": chunks,
    }
