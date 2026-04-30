# Bajeti Watch

> Budget transparency for Kenyan citizens through WhatsApp, retrieval-augmented AI, and a public dashboard.

## Overview

Bajeti Watch turns Kenyan budget PDFs into searchable, citizen-friendly information. It ingests government budget documents, stores cleaned content and vector embeddings in Supabase, answers public questions through a LangGraph RAG agent, and exposes the same budget coverage through a React dashboard.

The goal is simple: a citizen should be able to text a county or sector question, such as `Kisumu roads budget`, and get a short plain-language answer grounded in uploaded budget documents.

## Features

- PDF ingestion pipeline: PDF to Markdown, cleaning, metadata tagging, chunking, embeddings, and Supabase upload.
- Supabase + pgvector storage: documents, chunks, subscribers, and semantic search RPC.
- LangGraph RAG agent: intake, retrieval, Groq summarization, and channel-specific formatting.
- WhatsApp webhook: FastAPI + Twilio TwiML endpoint for citizen messages.
- Public dashboard: Vite React app with county coverage, document list, search, and about pages.
- Tests: local ingestion tests, agent/API tests, dashboard API tests, and Supabase integration tests.

## Architecture

```text
Government PDFs
    ↓
Ingestion Pipeline
    ↓
Supabase Postgres + pgvector
    ↓
LangGraph RAG Agent + Groq
    ↓
FastAPI
    ↓
WhatsApp via Twilio | React Dashboard
```

## Tech Stack

- Python, FastAPI, LangGraph
- Groq with `llama-3.3-70b-versatile`
- Supabase Postgres + pgvector
- Ollama `nomic-embed-text` for local embeddings, or Nomic API for production embeddings
- Twilio WhatsApp
- React, Vite, Tailwind CSS
- Pytest

## Quick Start

See `QUICKSTART.md` for the full setup and runbook.

Minimal local setup:

```bash
cp .env.example .env
source .venv/bin/activate
pip install -r requirements.txt

cd dashboard
npm install
cd ..
```

Create the Supabase schema by running `database/migrations/001_initial_schema.sql` in the Supabase SQL editor.

Run the API:

```bash
uvicorn api.main:app --reload --port 8000
```

Run the dashboard:

```bash
cd dashboard
npm run dev
```

## Testing

Local unit and API checks:

```bash
python -m pytest tests/ingestion/test_cleaner.py tests/ingestion/test_tagger.py tests/agent/test_graph.py tests/api/test_whatsapp.py tests/api/test_dashboard.py -v
```

Local PDF pipeline test:

```bash
TEST_PDF_PATH=tests/fixtures/kisumu_county_budget_23_24.pdf \
python -m pytest tests/ingestion/test_pipeline_integration.py -m local -v
```

Supabase integration test:

```bash
TEST_PDF_PATH=tests/fixtures/kisumu_county_budget_23_24.pdf \
python -m pytest tests/ingestion/test_pipeline_integration.py -m integration -v
```

Dashboard build:

```bash
cd dashboard
npm run build
```

## Ingestion

After configuring `.env` and creating the Supabase schema:

```bash
python ingestion/pipeline.py ./pdfs/*.pdf --auto
```

For known metadata:

```bash
python ingestion/pipeline.py ./pdfs/kisumu.pdf \
  --county Kisumu \
  --year 2023/24 \
  --doc-type county_budget
```

## Deployment

Recommended production setup:

- Dashboard: Vercel
- API: Render, Railway, or Fly.io
- Database/vector search: Supabase
- Embeddings: Nomic API
- LLM: Groq
- Scheduled ingestion: GitHub Actions first, then platform scheduler if needed

Vercel is a good fit for the static React dashboard. The FastAPI backend is better suited to a container-friendly platform because it handles webhooks, external API calls, ingestion, and potentially long-running jobs.

## Project Structure

See `docs/structure.md` for the annotated directory tree.

## Status

- Ingestion pipeline: working and tested.
- Supabase integration: working with hosted Supabase and pgvector.
- LangGraph agent and WhatsApp webhook: implemented with local tests.
- Dashboard MVP: implemented and builds successfully.
- Production deployment: documented, not yet deployed.
