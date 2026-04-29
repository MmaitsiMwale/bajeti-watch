# Bajeti Watch Dashboard

React + Tailwind frontend for browsing public budget coverage.

## Pages
- `/` — county coverage overview
- `/county/:name` — county document list
- `/search` — full text search across uploaded budget documents
- `/about` — about Bajeti Watch

## Local development
```bash
cp .env.template .env
npm install
npm run dev
```

Run the FastAPI backend separately:
```bash
uvicorn api.main:app --reload --port 8000
```

## Deployment
This app can deploy as a static Vercel project from the `dashboard/` directory.
Set `VITE_API_BASE_URL` to the public API base URL in Vercel project settings.
