# JEEVAN — JEEVAN

FastAPI backend + SvelteKit frontend for a smart ambulance dispatch / routing prototype.

## Quickstart

### 1) Backend (FastAPI)

1. Install Python dependencies:

	```bash
	pip install -r requirements.txt
	```

2. (Recommended) Create a `.env` file in the repo root (see **Environment variables** below).

3. Start the API:

	```bash
	npm run backend
	# or: uvicorn backend.main:app --reload --port 8000
	```

Backend URLs:

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs

### 2) Frontend (SvelteKit/Vite)

1. Install frontend dependencies:

	```bash
	npm --prefix frontend install
	# or: cd frontend && npm install
	```

2. Start the dev server:

	```bash
	npm run dev
	```

Frontend URL (default Vite): http://localhost:5173

Notes:

- In development, API/WebSocket traffic is proxied to `http://localhost:8000` (see `frontend/vite.config.js`), so you can usually leave `VITE_BACKEND_URL` empty.

## Environment variables

Create a `.env` file in the repo root (the backend loads it via `python-dotenv`, and Vite will also read it).

### Required for local development

- (Usually optional in dev) `VITE_BACKEND_URL`
	- If unset, the frontend uses the Vite dev proxy for `/api` and `/ws`.
	- If set, it should be the full backend origin (example: `VITE_BACKEND_URL=http://localhost:8000`).

### Supabase (optional, but many flows expect it)

Frontend (Vite):

- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`

Backend (server-side; recommended):

- `SUPABASE_URL` (or reuse `VITE_SUPABASE_URL`)
- `SUPABASE_SERVICE_KEY` (recommended) or `SUPABASE_ANON_KEY`

Notes:

- The backend will *write* dispatches to Supabase when configured.
- The endpoint `GET /api/dispatch/log` is auth-protected and will read from Supabase if available.
- Run `supabase_sql/dispatches.sql` in the Supabase SQL editor to create/migrate the `public.dispatches` table.
	- The SQL includes optional columns `local_id` and `user_id` (safe to re-run).

### AI provider keys (optional)

The backend supports multiple AI providers (configured via `AI_PROVIDER`). If you don’t set keys, endpoints that call the provider may return errors or use limited fallbacks.

- `AI_PROVIDER` (default: `gemini`)

Gemini:

- `GEMINI_API_KEY`
- `GEMINI_MODEL` (default: `gemini-1.5-flash`)

NVIDIA:

- `NVIDIA_API_KEY`
- `NVIDIA_MODEL` (default: `nvidia/llama-3.1-nemotron-nano-8b-v1`)
- `NVIDIA_BASE_URL` (default: `https://integrate.api.nvidia.com/v1`)
- `NVIDIA_MODEL_FALLBACKS` (comma-separated)

OpenRouter (report generation):

- `OPENROUTER_API_KEY`
- `OPENROUTER_REPORT_MODEL` (default: `openrouter/auto`)
- `OPENROUTER_BASE_URL` (default: `https://openrouter.ai/api/v1`)

### CORS (optional)

- `CORS_ORIGINS` (comma-separated list)

## Common commands

- `npm run backend` — start FastAPI (reload) on port 8000
- `npm run dev` — start Vite dev server (frontend)

## Generate a 30s report explainer video (local)

The backend can generate a short flat 2D cartoon `.mp4` (with narration) from an existing report analysis text.

- Endpoint: `POST http://127.0.0.1:8000/api/ai/report-video`
- Body (JSON): `{"analysis_text":"...","duration_seconds":30}`

Example (PowerShell + curl):

```powershell
curl.exe -o report_explainer.mp4 -X POST http://127.0.0.1:8000/api/ai/report-video \
	-H "Content-Type: application/json" \
	-d '{"analysis_text":"<paste the OpenRouter analysis here>","duration_seconds":30}'
```

## Status (April 2026)

Currently experimenting with a dynamic rerouting concept: rerouting ambulances in real-time based on traffic, road blockages, and hospital availability.
