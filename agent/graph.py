"""
agent/graph.py

Defines the LangGraph agent as a directed graph of nodes.
Flow: intake → retrieval → summarizer → formatter → END

Usage:
    from agent.graph import run_agent

    reply = run_agent(
        message="What did Kisumu get for roads?",
        channel="whatsapp"
    )
    print(reply)
"""

from __future__ import annotations

from langgraph.graph import StateGraph, END

from .nodes.intake     import intake_node,     AgentState
from .nodes.retrieval  import retrieval_node
from .nodes.summarizer import summarizer_node
from .nodes.formatter  import formatter_node


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("intake",     intake_node)
    graph.add_node("retrieval",  retrieval_node)
    graph.add_node("summarizer", summarizer_node)
    graph.add_node("formatter",  formatter_node)

    # Wire edges in sequence
    graph.set_entry_point("intake")
    graph.add_edge("intake",     "retrieval")
    graph.add_edge("retrieval",  "summarizer")
    graph.add_edge("summarizer", "formatter")
    graph.add_edge("formatter",  END)

    return graph.compile()


# Compile once at import time — reused across requests
_graph = build_graph()


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def run_agent(message: str, channel: str = "whatsapp") -> str:
    """
    Run the full agent pipeline for a citizen message.

    Args:
        message: Raw text from WhatsApp or dashboard
        channel: "whatsapp" or "dashboard"

    Returns:
        Formatted reply string ready to send back to the citizen
    """
    initial_state: AgentState = {
        "raw_message":  message,
        "channel":      channel,
        "query":        "",
        "county_hint":  None,
        "year_hint":    None,
        "query_type":   "general",
        "chunks":       [],
        "llm_response": "",
        "final_reply":  "",
    }

    result = _graph.invoke(initial_state)
    return result["final_reply"]
