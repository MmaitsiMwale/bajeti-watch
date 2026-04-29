# Bajeti Watch

> Budget transparency for every Kenyan citizen — via WhatsApp and a public web dashboard.

## What it does
Bajeti Watch monitors Kenyan government budget documents, translates complex
financial allocations into plain language, and delivers them to citizens via
WhatsApp. No app to download. No login. Just text your county name.

## Architecture
```
Government PDFs → Ingestion Pipeline → Supabase + pgvector
                                              ↓
                              LangGraph Agent (RAG + Llama 3.1 via Groq)
                                              ↓
                              WhatsApp (Twilio)  |  Web Dashboard (React)
```

## Project structure
See docs/structure.md for the full annotated directory tree.

## Getting started
```bash
cp .env.example .env        # fill in your keys
source .venv/bin/activate
pip install -r requirements.txt

# Run the ingestion pipeline
python ingestion/pipeline.py ./pdfs/*.pdf --auto
```

## Build phases
- Phase 1+2 ✅  Ingestion pipeline + RAG layer
- Phase 3    ✅  LangGraph agent + WhatsApp bot
- Phase 4    🔧  React dashboard MVP + deployment config
