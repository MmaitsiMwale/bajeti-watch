"""
agent/nodes/formatter.py

Final node in the LangGraph agent.
Formats the LLM response differently depending on the channel:
  - whatsapp:  plain text, short, no markdown, adds help footer
  - dashboard: can include richer formatting
"""

from __future__ import annotations
import re
from .intake import AgentState


# WhatsApp max message length (Twilio enforces 1600 chars)
WHATSAPP_MAX_CHARS = 1500

WHATSAPP_FOOTER = (
    "\n\n─────────────────\n"
    "Bajeti Watch 🇰🇪\n"
    "Text a county name for its budget summary.\n"
    "E.g: *Kisumu* or *Nairobi health budget*"
)


def formatter_node(state: AgentState) -> AgentState:
    """
    Formats the LLM response for the appropriate channel.
    """
    channel  = state.get("channel", "whatsapp")
    response = state.get("llm_response", "")

    if channel == "whatsapp":
        final_reply = _format_whatsapp(response)
    else:
        final_reply = _format_dashboard(response)

    return {
        **state,
        "final_reply": final_reply,
    }


def _format_whatsapp(text: str) -> str:
    """
    Clean up for WhatsApp:
    - Strip markdown headers (# ##)
    - Strip code blocks
    - Truncate if too long
    - Add footer
    """
    # Strip markdown headers
    text = re.sub(r"^#{1,4}\s+", "", text, flags=re.MULTILINE)

    # Strip code blocks
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)

    # Collapse excess blank lines
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    # Truncate if too long (rare but possible)
    if len(text) > WHATSAPP_MAX_CHARS:
        text = text[:WHATSAPP_MAX_CHARS - 30] + "...\n(Message truncated)"

    return text + WHATSAPP_FOOTER


def _format_dashboard(text: str) -> str:
    """
    Dashboard can handle richer content — just clean it up lightly.
    """
    return text.strip()