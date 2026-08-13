# Architecture

## Project Structure

```
jeevan/
├── backend/          # FastAPI Python backend
│   ├── main.py       # API entry point, dispatch pipeline
│   ├── models.py     # Pydantic request/response models
│   ├── data.py       # Ambulance & hospital seed data
│   ├── routing.py    # OSMnx + NetworkX route computation
│   ├── ml_engine.py  # Random Forest ETA + severity adjustment
│   └── simulator.py  # Background ambulance movement simulator
├── frontend/         # SvelteKit frontend
│   ├── index.html    # Landing / emergency request form
│   ├── dashboard.html
│   ├── hospitals.html
│   ├── navigation.html
│   ├── notifications.html
│   └── app.js
├── requirements.txt
└── package.json
```

## Tech Stack

- Backend: FastAPI + Uvicorn, OSMnx, NetworkX, scikit-learn
- Frontend: SvelteKit + Vite
- Real-time: WebSocket (`/ws`) for live ambulance position updates

---

## Setup

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Node dependencies (for frontend dev server)

```bash
npm install
```

### 3. Configure AI provider

Copy `.env.example` to `.env`, then choose one backend AI provider:

```env
AI_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_key
```

or:

```env
AI_PROVIDER=nvidia
NVIDIA_API_KEY=your_nvidia_key
NVIDIA_MODEL=nvidia/llama-3.1-nemotron-nano-8b-v1
NVIDIA_MODEL_FALLBACKS=
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
```

Report analysis prefers OpenRouter. If `OPENROUTER_API_KEY` is missing, it falls back to Gemini (`GEMINI_API_KEY`), and then NVIDIA for text-only uploads:

```env
OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_REPORT_MODEL=openrouter/free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

With `openrouter/free`, OpenRouter routes image/text report requests to available free models. In this app, PDFs should be uploaded as screenshots/images or extracted text.

---

## Running the Backend

```bash
uvicorn backend.main:app --reload --port 8000
```

---

## Running the Frontend

```bash
npm run dev
```

- Frontend: `http://localhost:5173`
- Vite proxies `/api` and `/ws` to the backend on port 8000 automatically.

---

## Running Everything

Open two terminals:

Terminal 1 — backend:
```bash
uvicorn backend.main:app --reload --port 8000
```

Terminal 2 — frontend:
```bash
npm run dev
```

Then open `http://localhost:5173`.

---

## Key API Endpoints

| Method | Endpoint        | Description                        |
|--------|-----------------|------------------------------------|
| GET    | `/`             | Health check                       |
| POST   | `/dispatch`     | Trigger full dispatch pipeline     |
| GET    | `/ambulances`   | Live ambulance fleet status        |
| GET    | `/hospitals`    | Hospital capacity + specializations|
| GET    | `/queue`        | Current dispatch priority queue    |
| GET    | `/stats`        | Dashboard summary stats            |
| GET    | `/dispatch/log` | Full dispatch history              |
| POST   | `/reset`        | Reset demo state                   |
| GET    | `/triage-test`  | Test triage + ML pipeline          |
| WS     | `/ws`           | Real-time position updates         |

---

## Dispatch Pipeline

```
Symptoms (5 yes/no)
  → Rule-based triage       → base trauma level (1–5)
  → ML severity adjustment  → final trauma level
  → Priority queue          → ordered by severity
  → Nearest ambulance       → find available unit
  → ETA prediction          → Random Forest model
  → Golden hour check       → may override hospital selection
  → Two-stage hospital pick → time-based → service-based
  → OSMnx route compute     → real Bangalore road network
  → WebSocket broadcast     → push to all connected clients
```
