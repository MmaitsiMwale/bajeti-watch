# Bajeti Watch — Project Structure

```
bajeti-watch/
│
├── ingestion/                  ← PHASE 1+2 (BUILT)
│   ├── convertor/
│   │   └── pdf_to_md.py        PDF → Markdown (pymupdf4llm + GLM-OCR fallback)
│   ├── cleaner/
│   │   └── md_cleaner.py       Strip noise from converted Markdown
│   ├── tagger/
│   │   └── md_tagger.py        Attach YAML frontmatter metadata
│   ├── uploader/
│   │   └── supabase_uploader.py Chunk → Embed → Store in pgvector
│   ├── pipeline.py             Orchestrator — runs all 4 steps
│   └── schema.sql              Supabase DB schema + search function
│
├── agent/                      ← PHASE 3 (next)
│   ├── graph.py                LangGraph agent definition
│   ├── nodes/
│   │   ├── intake.py           Classify the incoming query
│   │   ├── retrieval.py        pgvector semantic search
│   │   ├── summarizer.py       Llama 3.1 via Groq
│   │   └── formatter.py        Format reply for WhatsApp or dashboard
│   ├── prompts/
│   │   └── summarize.py        LLM prompts
│   └── tools/
│       └── supabase_search.py  search_chunks() RPC wrapper
│
├── api/                        ← PHASE 3 (next)
│   ├── main.py                 FastAPI app entrypoint
│   ├── routes/
│   │   ├── whatsapp.py         Twilio webhook receiver
│   │   └── health.py           Liveness check
│   └── middleware/
│       └── twilio_auth.py      Twilio signature validation
│
├── dashboard/                  ← PHASE 4
│   └── src/
│       ├── components/         Reusable React components
│       ├── pages/              Route-level pages (map, county, search)
│       └── hooks/              Custom React hooks (useSupabase etc.)
│
├── scheduler/                  ← PHASE 3/4
│   └── fetch_new_budgets.py   Weekly document checker
│
├── database/
│   ├── migrations/             SQL migration files
│   └── seeds/                  Sample data for local testing
│
├── tests/
│   ├── ingestion/              Tests for pipeline steps
│   ├── agent/                  Tests for agent nodes
│   └── api/                    Integration tests for webhook
│
├── .github/
│   └── workflows/
│       └── weekly_ingest.yml   GitHub Actions cron job
│
├── docs/
│   └── structure.md            This file
│
├── .env.example                Environment variable template
├── .gitignore
├── requirements.txt
└── README.md
```
