# Kinderkreis — Demo (React + FastAPI)

A runnable demo of the Kinderkreis concept: parents search and browse
certified Kindertagespflege / Großtagespflege providers, and providers can
register their own profile.

This is a **sample/demo**, not a production system: data lives in memory in
the backend and resets whenever the container restarts. There is no
authentication — anyone can "register" a profile, matching the brief's
request for a simple self-serve demo.

## Stack

- **Backend**: Python 3.11 + FastAPI, in-memory data store, Pydantic models
  that encode the real regulatory rules (solo Kindertagespflege ≤ 5 children,
  Großtagespflege with 2–3 staff ≤ 10 children, "certified" requires ≥300 QHB
  hours and ≥80 practicum hours).
- **Frontend**: React 18 + Vite, no extra UI framework, styled to match the
  original Kinderkreis palette (forest green / honey, Fraunces + Inter).
- **Orchestration**: Docker Compose, two services (`backend`, `frontend`).

## Run it

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000 (interactive docs at http://localhost:8000/docs)

Stop with `Ctrl+C`, or `docker compose down` to remove the containers.

## What you can do in the demo

- **Für Eltern** (default view): filter the directory by city, child's age,
  care type (individual vs. group), availability, and certification status.
  Click a card to see the full profile in a modal.
- **Für Tagespflegepersonen**: fill out the registration form. The backend
  validates the same regulatory constraints as the real workflow — e.g. it
  rejects a solo Kindertagespflege profile with capacity above 5, or a group
  profile with only 1 staff member — and returns a clear error if a rule is
  broken.

Seed data (5 sample providers across Göttingen, Hannover, and Braunschweig)
is loaded on backend startup so the directory isn't empty on first run.

## API endpoints

| Method | Path                              | Purpose                                   |
|--------|-----------------------------------|--------------------------------------------|
| GET    | `/api/providers`                  | List/filter providers                     |
| GET    | `/api/providers/{id}`             | Get one provider                          |
| POST   | `/api/providers`                  | Register a new provider profile           |
| PATCH  | `/api/providers/{id}/capacity`    | Update how many places are currently used |
| GET    | `/api/meta/cities`                 | Distinct list of cities for the filter    |

## Project layout

```
kinderkreis-demo/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py       # FastAPI routes
│       ├── models.py     # Pydantic models + regulatory validation rules
│       └── data.py       # In-memory seed data
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── api.js
        ├── styles.css
        └── components/
            ├── ParentsView.jsx
            ├── RegisterView.jsx
            ├── ProviderCard.jsx
            └── ProviderDetailModal.jsx
```

## Local development without Docker

Backend:
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

## Next steps for a real product

- Swap the in-memory store for Postgres (SQLAlchemy models can mirror
  `app/models.py` closely).
- Add authentication for providers and parents, plus messaging between them.
- Verify Pflegeerlaubnis and qualification claims against Jugendamt records
  rather than trusting self-reported form data.
- Add file upload for certificates and photos.
