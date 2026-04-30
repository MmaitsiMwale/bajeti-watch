"""
agent/nodes/summarizer.py

Third node in the LangGraph agent.
Sends retrieved chunks + citizen query to Llama 3.1 70B via Groq
and gets back a plain-language budget summary.
"""

from __future__ import annotations

import os
from groq import Groq

from ..prompts.summarize import SYSTEM_PROMPT, build_user_prompt
from .intake import AgentState


GROQ_MODEL      = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
MAX_TOKENS      = 512    # keeps WhatsApp replies concise
TEMPERATURE     = 0.2    # low — we want factual answers, not creativity


def summarizer_node(state: AgentState) -> AgentState:
    """
    Builds the prompt from retrieved chunks and calls Groq.
    Falls back to a helpful error message if Groq is unavailable.
    """
    user_prompt = build_user_prompt(
        query=state["query"],
        chunks=state.get("chunks", []),
    )

    try:
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
        )
        llm_response = response.choices[0].message.content.strip()

    except Exception as e:
        # Graceful fallback — never leave citizen without a reply
        llm_response = (
            "Samahani, nimekutana na tatizo la muda. Tafadhali jaribu tena baadaye.\n"
            "(Sorry, I encountered a temporary issue. Please try again shortly.)"
        )
        print(f"[summarizer] Groq error: {e}")

    return {
        **state,
        "llm_response": llm_response,
    }