# F1-Engineering-Suite

The Virtual Garage is an F1 engineering web suite combining data science, physics modeling, and hardware telemetry.

## Architecture

- **`backend/`** — FastAPI service exposing the strategy, suspension, and telemetry engines as JSON endpoints and serving the frontend.
- **`frontend/`** — static HTML/CSS/JS single-page app (Plotly.js) that consumes the API.

## Run locally

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

Then open http://localhost:8000.

## API

| Endpoint | Params | Description |
| --- | --- | --- |
| `GET /api/health` | — | Liveness check. |
| `GET /api/strategy` | `session_key` (≥1), `driver_number` (1–99) | Lap times + theoretical-grip model. |
| `GET /api/suspension` | `roll_angle` (−5..5), `wishbone_length` (300..500) | Wishbone geometry + camber curve. |
| `GET /api/telemetry` | `session_key` (≥1), `driver_number` (1–99) | Merged car + location samples. |

Live data comes from the public [OpenF1](https://openf1.org) API; the service falls back to built-in mock data when the API is unavailable.

## Configuration

- `ALLOWED_ORIGINS` — comma-separated CORS allowlist (default `http://localhost:8000,http://127.0.0.1:8000`).
