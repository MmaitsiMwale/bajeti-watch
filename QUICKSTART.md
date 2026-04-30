# Bajeti Watch Quickstart

This guide covers local development, Supabase testing, ingestion, the WhatsApp API, the dashboard, and production deployment.

## 1. Prerequisites

- Python 3.11+
- Node.js 20+
- Ollama, if using local embeddings
- A hosted Supabase project
- A Groq API key
- Twilio WhatsApp Sandbox credentials, for WhatsApp testing
- ngrok, for local Twilio webhook testing

## 2. Clone And Install

```bash
git clone https://github.com/MmaitsiMwale/bajeti-watch.git
cd bajeti-watch

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd dashboard
npm install
cd ..
```

## 3. Configure Environment

Create the root backend environment file:

```bash
cp .env.example .env
```

Fill in:

```env
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_KEY=your-service-role-key

GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=llama-3.3-70b-versatile

EMBEDDING_PROVIDER=ollama
NOMIC_API_KEY=

TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

APP_ENV=development
LOG_LEVEL=INFO
```

Use the Supabase `service_role` key only in the backend/root `.env`. Never put it in the dashboard environment or commit it.

For the dashboard:

```bash
cd dashboard
cp .env.template .env
cd ..
```

Local dashboard value:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## 4. Create Supabase Tables

Open your Supabase project, go to SQL Editor, and run:

```sql
-- paste database/migrations/001_initial_schema.sql here
```

When Supabase asks about Row Level Security, choose:

```text
Run and enable RLS
```

The backend uses the service role key, so ingestion and API reads still work with RLS enabled.

Confirm Supabase has:

- `documents`
- `chunks`
- `subscribers`
- `search_chunks` RPC function

## 5. Ollama Embeddings

If `EMBEDDING_PROVIDER=ollama`, start Ollama and install the embedding model:

```bash
ollama serve
ollama pull nomic-embed-text
ollama list
```

The app calls:

```text
http://localhost:11434/api/embeddings
```

with model:

```text
nomic-embed-text
```

## 6. Run Tests

Fast local unit checks:

```bash
source .venv/bin/activate
python -m pytest tests/ingestion/test_cleaner.py tests/ingestion/test_tagger.py tests/agent/test_graph.py tests/api/test_whatsapp.py tests/api/test_dashboard.py -v
```

Local PDF pipeline test with Groq auto-tagging:

```bash
TEST_PDF_PATH=tests/fixtures/kisumu_county_budget_23_24.pdf \
python -m pytest tests/ingestion/test_pipeline_integration.py -m local -v
```

Supabase integration test:

```bash
TEST_PDF_PATH=tests/fixtures/kisumu_county_budget_23_24.pdf \
python -m pytest tests/ingestion/test_pipeline_integration.py -m integration -v
```

Expected Supabase result:

```text
3 passed, 14 deselected
```

Dashboard build:

```bash
cd dashboard
npm run build
cd ..
```

## 7. Ingest Budget PDFs

Put PDFs in a folder such as `pdfs/`, then run:

```bash
source .venv/bin/activate
python ingestion/pipeline.py ./pdfs/*.pdf --auto
```

Manual metadata example:

```bash
python ingestion/pipeline.py ./pdfs/kisumu.pdf \
  --county Kisumu \
  --year 2023/24 \
  --doc-type county_budget
```

The pipeline converts PDFs, cleans markdown, attaches metadata, chunks content, embeds chunks, and uploads to Supabase.

## 8. Run The API Locally

```bash
source .venv/bin/activate
uvicorn api.main:app --reload --port 8000
```

Useful URLs:

- API root: `http://localhost:8000/`
- Health: `http://localhost:8000/health`
- API docs: `http://localhost:8000/docs`
- Dashboard summary API: `http://localhost:8000/dashboard/summary`

## 9. Run The Dashboard Locally

In a second terminal:

```bash
cd dashboard
npm run dev
```

Open the Vite URL printed in the terminal, usually:

```text
http://localhost:5173
```

## 10. Test WhatsApp Locally

Use the helper script:

```bash
chmod +x dev.sh
./dev.sh
```

The script starts FastAPI, starts ngrok, and prints the webhook URL.

In Twilio WhatsApp Sandbox, set:

```text
When a message comes in: https://your-ngrok-url/webhook/whatsapp
Method: POST
```

## 11. Production Deployment

Recommended MVP production setup:

- Supabase hosted project for Postgres, pgvector, and storage of budget documents.
- Render, Railway, or Fly.io for the FastAPI backend.
- Vercel for the static React dashboard.
- GitHub Actions or a scheduled worker for recurring ingestion jobs.

### Backend Environment

Set these on the backend hosting platform:

```env
SUPABASE_URL=...
SUPABASE_KEY=...
GROQ_API_KEY=...
GROQ_MODEL=llama-3.3-70b-versatile
EMBEDDING_PROVIDER=nomic
NOMIC_API_KEY=...
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=...
APP_ENV=production
LOG_LEVEL=INFO
```

For production, prefer `EMBEDDING_PROVIDER=nomic` unless you are deploying and managing an Ollama service yourself.

Backend start command:

```bash
uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

### Dashboard Environment

Deploy `dashboard/` to Vercel and set:

```env
VITE_API_BASE_URL=https://your-api-domain.example.com
```

The dashboard is static, so it should not receive any private Supabase service role key.

### Twilio Production Webhook

Set the Twilio WhatsApp webhook to:

```text
https://your-api-domain.example.com/webhook/whatsapp
```

In production, keep Twilio signature validation enabled. Do not set `SKIP_TWILIO_AUTH=true`.

## 12. Production Recommendation

Best setup for this project:

- Use Vercel for the React dashboard.
- Use Render or Railway for the FastAPI backend.
- Use Supabase hosted Postgres/pgvector.
- Use Nomic cloud embeddings in production.

Vercel is excellent for the static dashboard, but it is not the best primary home for this FastAPI backend because the app has webhooks, PDF ingestion, long-running tests, and external API calls. A container-friendly platform like Render, Railway, or Fly.io is a better fit for the backend.

For the quickest MVP, use:

```text
Dashboard: Vercel
API: Render
Database/vector search: Supabase
Embeddings: Nomic API
LLM: Groq
Scheduler: GitHub Actions initially, then a Render/Railway scheduled job if needed
```

