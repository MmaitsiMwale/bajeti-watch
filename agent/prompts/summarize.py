"""
agent/prompts/summarize.py

System and user prompt templates for the summarization node.
Designed for Llama 3.1 70B via Groq.
"""

SYSTEM_PROMPT = """You are Bajeti Watch, a budget transparency assistant for Kenyan citizens.

Your job is to read budget document excerpts and answer questions in plain, simple language
that any Kenyan citizen can understand — whether or not they have a finance background.

Rules:
- Answer only from the budget excerpts provided. Do not invent figures.
- Always mention specific Ksh amounts when available.
- If asked about a county, focus only on that county's allocation.
- Compare to previous year if the data is available.
- Keep replies SHORT — maximum 5 sentences for WhatsApp.
- End every reply with the source document name so citizens can verify.
- If the excerpts do not contain enough information to answer, say so honestly.
- Never use jargon like "MTEF", "recurrent expenditure", or "absorption rate" without explaining them.
- You may respond in English or Swahili depending on which language the citizen used.
"""

def build_user_prompt(query: str, chunks: list[dict]) -> str:
    """
    Build the user prompt by combining the citizen's query
    with the retrieved budget chunks as context.
    """
    if not chunks:
        return f"""The citizen asked: "{query}"

No relevant budget data was found for this query. Tell them politely and suggest
they try a different county name or ask about a specific sector like roads or health."""

    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata", {})
        county = meta.get("county", "Unknown")
        year   = meta.get("financial_year", "Unknown")
        source = meta.get("source_file", "Unknown document")
        similarity = chunk.get("similarity", 0)

        context_parts.append(
            f"[Excerpt {i} — {county} | {year} | {source} | relevance: {similarity:.0%}]\n"
            f"{chunk['content']}"
        )

    context = "\n\n---\n\n".join(context_parts)

    return f"""The citizen asked: "{query}"

Here are the relevant budget excerpts to answer from:

{context}

Now answer the citizen's question clearly and briefly based only on the excerpts above."""