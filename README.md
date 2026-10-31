# Campus OS — ANVIL

**Multi-agent decision-support platform for college operations.**

> ⚠ **SYNTHETIC DATA ONLY** — All seeded data is generated for demonstration purposes. It does not represent any real institution, faculty member, student, or operational record.

---

## Milestone Status

| Milestone | Status | Description |
|-----------|--------|-------------|
| M0 | ✅ Complete | Repository inspection and design approval |
| **M1** | ✅ **Complete** | Foundation and data |
| M2 | 🔲 Pending | Deterministic rule engine |
| M3 | 🔲 Pending | Candidate generation and optimization |
| M4 | 🔲 Pending | Simulation, Critic, and audit |
| M5 | 🔲 Pending | API, authentication, and frontend |
| M6 | 🔲 Pending | Groq integration |
| M7 | 🔲 Pending | Evaluation and hardening |
| M8 | 🔲 Pending | Final delivery and demonstration |

---

## M1 Acceptance Criteria

✅ A fresh local setup starts successfully  
✅ PostgreSQL contains reproducible synthetic operational data  
✅ Seeded data is exposed through the backend (`GET /dashboard`)  
✅ Health check endpoint (`GET /health`) returns 200 without authentication  
✅ Authentication works (`POST /auth/token`, `GET /auth/me`)  
✅ 37 tests collected; runnable once database is configured  

---

## Prerequisites

- Python 3.11 or 3.12
- PostgreSQL 14+ running locally (or via Docker)
- All dependencies installed (see below)

---

## Quick Start

### 1. Install Python dependencies

```bash
cd backend
pip install -e ".[dev]"
```

### 2. Set up PostgreSQL

You need a `campus_os` user and two databases. Run the setup script with your PostgreSQL superuser password:

```bash
python scripts/setup_db.py --pg-password YOUR_POSTGRES_SUPERUSER_PASSWORD
```

This creates:
- User: `campus_os` / password: `campus_os`
- Database: `campus_os` (main)
- Database: `campus_os_test` (for tests)

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env if your PostgreSQL credentials differ from defaults
```

Default `.env` values (already set in `.env.example`):
```
DATABASE_URL=postgresql://campus_os:campus_os@localhost:5432/campus_os
TEST_DATABASE_URL=postgresql://campus_os:campus_os@localhost:5432/campus_os_test
SECRET_KEY=INSECURE-dev-key-replace-before-any-real-use
DEMO_PASSWORD=changeme
DEMO_TODAY=2026-10-26
```

### 4. Run database migrations

```bash
cd backend
alembic upgrade head
```

### 5. Seed synthetic data

```bash
cd backend
python -m app.db.seed
```

To reset and re-seed from scratch:
```bash
python -m app.db.seed --reset
```

### 6. Start the backend

```bash
cd backend
uvicorn app.main:app --reload
```

API is now at http://localhost:8000  
Interactive docs: http://localhost:8000/docs

---

## Docker Compose (Alternative)

If Docker is available:

```bash
# Copy and edit .env first
cp .env.example .env

docker compose up
```

Docker Compose automatically runs migrations and seed on startup.

---

## Demo Users

| Role | Email | Password |
|------|-------|----------|
| Principal | `principal@campus.os` | `changeme` |
| HOD (CS) | `hod.cs@campus.os` | `changeme` |
| HOD (EC) | `hod.ec@campus.os` | `changeme` |
| HOD (ME) | `hod.me@campus.os` | `changeme` |

Change `DEMO_PASSWORD` in `.env` before any live demonstration.

---

## API Endpoints (M1)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | None | Health check |
| `POST` | `/auth/token` | None | Login (OAuth2 password flow) |
| `GET` | `/auth/me` | Bearer | Current user profile |
| `GET` | `/dashboard` | Bearer (HOD/Principal) | Operational statistics |

Interactive docs: http://localhost:8000/docs

### Example: Login

```bash
curl -X POST http://localhost:8000/auth/token \
  -F "username=principal@campus.os" \
  -F "password=changeme"
```

### Example: Dashboard

```bash
TOKEN="<access_token from login>"
curl http://localhost:8000/dashboard \
  -H "Authorization: Bearer $TOKEN"
```

---

## Running Tests

```bash
cd backend
pytest tests/ -v
```

Tests require a running PostgreSQL and the `campus_os_test` database (created by `setup_db.py`).

### Test isolation

Each test function runs inside a transaction that is rolled back after the test. Tests do not persist data between runs.

---

## Synthetic Data Summary

| Entity | Count |
|--------|-------|
| Departments | 3 (CS, EC, ME) |
| Faculty | 30 (10 per dept) |
| Courses | 40 (14 CS, 13 EC, 13 ME) |
| Sections | 12 (4 per dept, years 1–4) |
| Rooms | 15 (10 classrooms + 5 labs) |
| Periods | 30 (6 slots × 5 weekdays) |
| Demo users | 4 (1 principal + 3 HODs) |

### Hero Scenario

Dr. Raj Sharma (CS001) is on leave 2026-11-02 (Mon) to 2026-11-04 (Wed).  
`DEMO_TODAY = 2026-10-26` — so this is "next week Mon–Wed".

Affected class occurrences: **Mon P2, Mon P4, Tue P1, Tue P3, Wed P1, Wed P2** (6 classes).

### Planted Conflicts (for M2 rule engine)

| ID | Conflict |
|----|---------|
| HC-01 | Dr. Arun Kumar double-booked on Mon P1 (two sections) |
| HC-02 | Room 301 double-booked on Tue P3 (EC-1A and ME-1A) |
| HC-04 | CS-1A (enrollment=65) in Room 101 (capacity=60) on Thu P1 |
| HC-05 | CS402 Mobile Computing (lab required) in Room 101 (not a lab) on Fri P5 |
| HC-06 | Dr. Sanjay Verma (no ML expertise) assigned CS301 Machine Learning on Fri P6 |

---

## Architecture

```
Frontend (React/TS/Vite) → FastAPI → PostgreSQL
                                   ↓
                          Auth / Authz (JWT HS256)
                                   ↓
                         Dashboard / Query Services
                                   ↓
                          Rule Engine (M2+)
                          CP-SAT Planner (M3+)
                          Simulation / Critic (M4+)
                          Groq LLM Interface (M6+)
```

### Temporal Model

- **`timetable_entry`** — recurring weekly template (e.g., "every Monday 09:00")
- **`class_occurrence`** — specific dated instance (e.g., "2026-11-02 09:00")
- Replacements are recorded on `class_occurrence.override_faculty_id`, **never** on `timetable_entry`
- A simulation result must never write to `class_occurrence` for proposed plans

---

## Known Limitations (M1)

- Conflict counts on the dashboard are SQL approximations. The deterministic rule engine (M2) will replace these with structured violations.
- No frontend yet (added in M5).
- No Groq/LLM integration (added in M6).
- No what-if simulation, candidate generation, or CP-SAT planner (M3–M4).
- JWT tokens are HS256 with no revocation — demo-only security.
- `DEMO_TODAY = 2026-10-26` is fixed for reproducible tests.

---

## Security Notes (Demo Only)

- JWT HS256 symmetric signing — not suitable for production.
- No token revocation or refresh tokens.
- Default `SECRET_KEY` in `.env.example` is public — replace it before any real use.
- Default demo password is `changeme` — change before any live demonstration.
- Never commit `.env` to version control.

---

## Project Structure

```
campus-os/
├── SPEC.md                    # Master specification
├── README.md
├── docker-compose.yml
├── .env.example               # Placeholder config (safe to commit)
├── .gitignore
├── scripts/
│   └── setup_db.py            # One-time DB setup
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       └── 0001_initial_schema.py
│   ├── app/
│   │   ├── main.py            # FastAPI entry point
│   │   ├── api/
│   │   │   ├── auth.py        # POST /auth/token, GET /auth/me
│   │   │   └── dashboard.py   # GET /dashboard
│   │   ├── core/
│   │   │   ├── config.py      # Settings (pydantic-settings)
│   │   │   ├── security.py    # JWT helpers
│   │   │   └── permissions.py # Role enforcement
│   │   ├── db/
│   │   │   ├── models.py      # SQLAlchemy ORM models (14 tables)
│   │   │   ├── session.py     # Engine + SessionLocal
│   │   │   └── seed.py        # Reproducible synthetic data
│   │   ├── schemas/
│   │   │   ├── auth.py        # TokenResponse, UserPublic
│   │   │   └── dashboard.py   # DashboardResponse
│   │   └── services/
│   │       └── timetable.py   # Query helpers
│   └── tests/
│       ├── conftest.py        # Shared fixtures
│       ├── test_health.py     # Health, auth, dashboard API tests
│       └── test_seed.py       # Seed data verification tests
```

