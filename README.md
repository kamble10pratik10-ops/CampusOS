# Campus OS — ANVIL

**Multi-agent decision-support platform for college operations.**

> ⚠ **SYNTHETIC DATA ONLY** — All seeded data is generated for demonstration purposes. It does not represent any real institution, faculty member, student, or operational record.

---

## Milestone Status

| Milestone | Status | Description |
|-----------|--------|-------------|
| M0 | ✅ Complete | Repository inspection and design approval |
| **M1** | ✅ **Complete** | Foundation and data |
| **M2** | ✅ **Complete** | Deterministic rule engine |
| **M3** | ✅ **Complete** | Candidate generation and optimization |
| **M4** | ✅ **Complete** | Simulation, Critic, and audit |
| **M5** | ✅ **Complete** | API, authentication, and frontend |
| **M6** | ✅ **Complete** | Groq integration |
| M7 | 🔲 Pending | Evaluation and hardening |
| M8 | 🔲 Pending | Final delivery and demonstration |

---

## M1 Acceptance Criteria

✅ A fresh local setup starts successfully  
✅ PostgreSQL contains reproducible synthetic operational data  
✅ Seeded data is exposed through the backend (`GET /dashboard`)  
✅ Health check endpoint (`GET /health`) returns 200 without authentication  
✅ Authentication works (`POST /auth/token`, `GET /auth/me`)  
✅ Seed data verification tests passing  

---

## M2 Acceptance Criteria

✅ Deterministic rule engine with typed structured outputs (`Violation`, `RuleValidationResult`)  
✅ Authoritative hard constraint checks implemented and verified (HC-01 through HC-10)  
✅ Transparent soft preference scoring (SP-01 to SP-04) with configurable weights  
✅ All 5 planted template conflicts detected with traceable evidence refs  
✅ Hero leave scenario (Dr. Raj Sharma) dated occurrence conflicts detected  
✅ New API endpoints: `GET /conflicts` and `GET /workload`  
✅ Upgraded `GET /dashboard` to report authoritative rule engine conflict counts  
✅ 65 tests passing in pytest suite  

---

## M3 Acceptance Criteria

✅ Candidate eligibility evaluation checking hard constraints (`HC-01`, `HC-03`, `HC-06`, `HC-07`, `HC-08`)  
✅ Structured rejection reasons (`CandidateRejection`) explaining why candidates are ineligible  
✅ Soft preference score calculation (SP-01 to SP-04) for all eligible candidates  
✅ Google OR-Tools CP-SAT joint optimization planner:
  - Formulates boolean decision variables \(x_{ij} \in \{0, 1\}\)
  - Enforces single-assignment constraints, overlap prevention, and cumulative weekly workload caps
  - Lexicographic multi-objective: coverage strictly dominates soft preference scores
  - Solves the Hero scenario (Dr. Raj Sharma leave: 6 affected classes) with 100% coverage
✅ Multi-alternative plan generation returning up to 3 distinct feasible plans (Balanced, Continuity & Dept focus, Workload focus)  
✅ Greedy heuristic baseline solver for comparative evaluation and benchmarking  
✅ Independent validation of every generated plan using `RuleEngine` (guarantees zero new hard violations)  
✅ Distinction of feasible (100% coverage), partial (< 100% coverage with explicit uncovered explanations), and infeasible scenarios  
✅ New API endpoints: `POST /planner/optimize` and `GET /planner/eligibility/{occurrence_id}`  
✅ 77 tests passing 100% in pytest suite (`test_health.py`, `test_seed.py`, `test_rules.py`, `test_planner.py`)  

---

## M4 Acceptance Criteria

✅ Non-mutating what-if simulation pipeline (`backend/app/engine/simulation.py`):
  - 12-step structured simulation workflow
  - Strictly non-destructive: zero writes to `timetable_entry`, `class_occurrence`, `faculty`, or `faculty_leave`
  - Table row snapshot verification before and after simulation guarantees HC-10 compliance
✅ Independent Critic (`backend/app/engine/critic.py`):
  - Multi-angle deterministic revalidation (not an LLM)
  - Re-evaluates all hard constraints via `RuleEngine.compare_states(...)`
  - Rejects plans introducing any new hard violations (`critic_status: validation_failed`)
  - Cross-checks internal assignment overlaps, near-capacity faculty workloads, and solver claim veracity
✅ Before-and-after state diffing:
  - Exact count of affected, preserved, and overridden occurrences
  - Identification of resolved vs. remaining pre-existing violations
  - Faculty workload shift breakdown (before vs. proposed teaching hours)
✅ Immutable audit persistence in PostgreSQL:
  - Persists full recommendation snapshot in `decision` table (`status: simulated`)
  - Persists detailed structured evidence artifacts in `decision_evidence` table
  - Human administrative approval workflow (`POST /simulation/{id}/approve` transitions status to `approved`)
✅ New API endpoints: `POST /simulation/run`, `GET /simulation/history`, `GET /simulation/{id}`, `POST /simulation/{id}/approve`  
✅ Cutline A satisfied: fully deterministic decision-support pipeline operating without LLM dependency  
✅ 84 tests passing 100% in pytest suite across 5 test suites (`test_health.py`, `test_seed.py`, `test_rules.py`, `test_planner.py`, `test_simulation.py`)  

---

## M5 Acceptance Criteria

✅ Supported API Contracts (SPEC Section 13):
  - Direct endpoints and aliases: `POST /whatif`, `GET /decisions`, `GET /decisions/{id}`, `POST /decisions/{id}/approve`
  - Academic lookup endpoints: `GET /departments`, `GET /faculty` (with department and capacity details)
✅ Backend Role-Based Authorization & Cross-Department Security:
  - Principal: unrestricted institution-wide visibility across all departments
  - HOD: strictly isolated to own department (CS, EC, or ME); cross-department access attempts return `HTTP 403 Forbidden`
  - Department-scoped dashboard statistics for HODs (e.g. 10 CS faculty vs 30 campus-wide)
  - Dedicated security test suite (`tests/test_security.py`) verifying cross-department access rejection
✅ Four Core Operational Frontend Screens:
  - **Screen 1: Operations Dashboard**: Live KPI metric cards (Faculty Available/on leave, Active Courses, Rooms/Labs, Weekly Occurrences), detected operational conflicts (HC-01..HC-06), workload distribution, recent audit log preview, and 1-click Hero Scenario trigger.
  - **Screen 2: What-If Simulator**: Natural language query bar with deterministic solver notice, 1-click Hero Scenario pre-fill, structured form controls, Critic verification banner (`CRITIC APPROVED: 0 New Hard Violations`), multi-alternative comparison tabs (Plan A Balanced, Plan B Continuity/Dept, Plan C Workload, plus Greedy Baseline comparator), proposed replacement schedule table, soft score breakdown (SP-01..SP-04), state diffing, workload shift metrics, and 1-click administrative approval.
  - **Screen 3: Decision Detail & Reasoning Inspector**: Deep-dive reasoning trace, metadata, constraints enforced check, interactive candidate pool & structured rejections inspector (`ON_LEAVE`, `MISSING_EXPERTISE`, `OVERLOADED`), and traceable evidence artifacts table.
  - **Screen 4: Decision Audit Log**: Searchable, filterable history of simulated and approved decisions, timestamp, creator, coverage %, Critic status, runtime ms, and link to inspect reasoning. Transparent HC-10 non-mutation banner.
✅ Cutline B satisfied: complete demonstrable decision-support platform operating without Groq LLM dependency  
✅ 91 tests passing 100% in pytest suite across 6 test suites (`test_health.py`, `test_seed.py`, `test_rules.py`, `test_planner.py`, `test_simulation.py`, `test_security.py`)  

---

## M6 Acceptance Criteria

✅ Provider-Independent LLM Interface (`backend/app/llm/interface.py`):
  - Abstract base class `LLMProvider` defining `parse_intent(query, context)` and `generate_explanation(request)`
  - Clean factory `get_llm_provider(settings)` dynamically selecting between Groq and Deterministic fallback
✅ Official Groq API Integration (`backend/app/llm/groq_client.py`):
  - Async HTTP client querying official Groq OpenAI-compatible endpoint (`https://api.groq.com/openai/v1/chat/completions`)
  - Configured with `qwen/qwen3.8-27b` model with strict JSON schema mode for structured intent parsing
  - Strict operational resilience: 10-second timeout, bounded exponential-backoff retries (max 2), and transparent automatic fallback to deterministic provider upon network failure, rate limiting, or malformed outputs
✅ Deterministic Grounded Fallback Provider (`backend/app/llm/fallback.py`):
  - Zero-dependency rule-based intent parser recognizing leave replacement, operational conflict, and faculty workload queries
  - Template-based grounded explanation generator turning optimization results, coverage %, Critic checks, and workload deltas into readable Markdown reports
  - Guarantees 100% system uptime and complete feature parity even without an active Groq API key
✅ Grounded Entity & Temporal Resolver (`backend/app/llm/resolver.py`):
  - Resolves natural language faculty names (e.g. "Dr. Raj Sharma", "Raj Sharma") and employee codes ("CS001") to database UUIDs
  - Grounded temporal resolver parsing ISO dates, month expressions, and relative references ("next week Mon to Wed", "this week", "today") anchored to `DEMO_TODAY = 2026-10-26`
✅ Natural Language Query API Endpoint (`POST /query` in `backend/app/api/query.py`):
  - Interprets user input, executes corresponding operational workflow (CP-SAT simulation, conflict scan, or workload report), generates grounded explanation, and returns unified `QueryResponse`
  - Strict role authorization enforced: HOD queries are scoped to their department; cross-department queries return `HTTP 403 Forbidden`
✅ Non-Negotiable Decision Invariant Maintained:
  - The LLM never computes feasibility, assigns faculty, calculates workload hours, or overrides constraints
  - All timetable replacements are solved by the deterministic Google OR-Tools CP-SAT solver and independently verified by the Critic engine
✅ Frontend Screen 2 Enhancement:
  - Natural language query bar wired directly to `POST /query`
  - Real-time display of parsed intent chips (Intent type, Target faculty, Date range, Confidence score)
  - Dedicated "AI Operational Intelligence Briefing" card displaying readable markdown explanations, LLM provider tags (`groq (qwen/qwen3.8-27b)` vs `deterministic_fallback`), execution status, and constraint grounding guarantee
✅ 101 tests passing 100% in pytest suite across 7 test suites (including 10 new comprehensive tests in `test_llm.py`)  

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

## API Endpoints (M1 through M6)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | None | Health check & current milestone status (`0.6.0-M6`) |
| `POST` | `/auth/token` | None | Login (OAuth2 password flow) |
| `GET` | `/auth/me` | Bearer | Current user profile |
| `GET` | `/dashboard` | Bearer (HOD/Principal) | Operational stats (department-scoped for HOD) |
| `GET` | `/conflicts` | Bearer (HOD/Principal) | Rule engine conflict detection (`scope=template\|dated`, `date`, `department_id`) |
| `GET` | `/workload` | Bearer (HOD/Principal) | Faculty capacity utilization & HC-07 workload caps (`week_date`, `department_id`) |
| `POST` | `/planner/optimize` | Bearer (HOD/Principal) | Joint optimization planner (CP-SAT multi-alternative plans + greedy baseline) |
| `GET` | `/planner/eligibility/{occurrence_id}` | Bearer (HOD/Principal) | Candidate eligibility & structured rejection reasons for a specific class |
| `POST` | `/simulation/run` / `/whatif` | Bearer (HOD/Principal) | Run non-mutating What-If simulation, Critic verification, and audit recording |
| `GET` | `/simulation/history` / `/decisions` | Bearer (HOD/Principal) | List recorded simulation & decision audit records (paginated) |
| `GET` | `/simulation/{id}` / `/decisions/{id}` | Bearer (HOD/Principal) | Retrieve full decision snapshot, alternatives, before/after diffs, and Critic evidence |
| `POST` | `/simulation/{id}/approve` / `/decisions/{id}/approve` | Bearer (HOD/Principal) | Record explicit administrative approval of a simulated recommendation |
| `GET` | `/departments` | Bearer (HOD/Principal) | List academic departments (CS, EC, ME) |
| `GET` | `/faculty` | Bearer (HOD/Principal) | List faculty members with department, employee code, and workload capacity |
| `POST` | `/query` | Bearer (HOD/Principal) | Natural language query interpretation (Groq / Fallback), scenario execution, and grounded explanation |

Interactive docs: http://localhost:8000/docs

### Example: Login

```bash
curl -X POST http://localhost:8000/auth/token \
  -F "username=principal@campus.os" \
  -F "password=changeme"
```

### Example: Joint Optimization (Hero Scenario)

```bash
TOKEN="<access_token from login>"

# Solve replacement for Dr. Raj Sharma on leave (2026-11-02 to 2026-11-04)
curl -X POST "http://localhost:8000/planner/optimize" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "faculty_id": "30000000-0000-0000-0000-000000000001",
    "start_date": "2026-11-02",
    "end_date": "2026-11-04",
    "max_alternatives": 3
  }'
```

### Example: Run What-If Simulation & Independent Critic (Hero Scenario)

```bash
TOKEN="<access_token from login>"

# Run non-mutating simulation with CP-SAT optimization & Critic verification
curl -X POST "http://localhost:8000/simulation/run" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "faculty_id": "30000000-0000-0000-0000-000000000001",
    "start_date": "2026-11-02",
    "end_date": "2026-11-04",
    "max_alternatives": 3,
    "selected_alternative_index": 0
  }'
```

### Example: View Audit History & Decision Details

```bash
# List historical simulation records
curl "http://localhost:8000/simulation/history" \
  -H "Authorization: Bearer $TOKEN"

# Inspect specific decision, alternatives, state diffs, and evidence
curl "http://localhost:8000/simulation/<DECISION_UUID>" \
  -H "Authorization: Bearer $TOKEN"
```

### Example: Approve Simulated Recommendation

```bash
curl -X POST "http://localhost:8000/simulation/<DECISION_UUID>/approve" \
  -H "Authorization: Bearer $TOKEN"
```

### Example: Dashboard

```bash
TOKEN="<access_token from login>"
curl http://localhost:8000/dashboard \
  -H "Authorization: Bearer $TOKEN"
```

### Example: Detect Conflicts (Rule Engine)

```bash
curl "http://localhost:8000/conflicts" \
  -H "Authorization: Bearer $TOKEN"

# For dated occurrences (e.g. hero leave on 2026-11-02):
curl "http://localhost:8000/conflicts?date=2026-11-02" \
  -H "Authorization: Bearer $TOKEN"
```

### Example: Faculty Workload

```bash
curl "http://localhost:8000/workload?week_date=2026-11-02" \
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

## Known Limitations (M5)

- Candidate generation, CP-SAT optimization, what-if simulation, independent Critic verification, immutable audit persistence, backend role enforcement, and the Four Core Frontend screens are complete (M1–M5).
- Groq LLM natural language intent parsing planned for M6.
- Cutline B verified: complete demonstrable prototype operates without Groq API dependency.
- JWT tokens are HS256 with no revocation — demo-only security.
- `DEMO_TODAY = 2026-10-26` is fixed for reproducible tests.

---

## Security Notes (Demo Only)

- JWT HS256 symmetric signing — not suitable for production.
- Backend role-based authorization enforced on all protected endpoints (`Principal` unrestricted, `HOD` strictly departmental).
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
├── frontend/                  # React 19 + TypeScript + Vite + Tailwind
│   ├── src/
│   │   ├── api/client.ts      # API client & auth handling (M1-M5 endpoints)
│   │   ├── components/
│   │   │   └── Navbar.tsx     # Header, 4-Screen navigation, Role Switcher
│   │   ├── pages/
│   │   │   ├── DashboardPage.tsx       # Screen 1: Operations Dashboard
│   │   │   ├── WhatIfSimulatorPage.tsx # Screen 2: What-If Simulator & Multi-Alternative Comparison
│   │   │   ├── DecisionDetailPage.tsx  # Screen 3: Decision Detail & Reasoning Inspector
│   │   │   └── AuditLogPage.tsx        # Screen 4: Decision Audit Log
│   │   ├── App.tsx            # App container & screen routing
│   │   ├── types/index.ts     # Complete TypeScript domain interfaces
│   │   └── main.tsx
│   └── vite.config.ts         # Reverse proxy to backend
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       └── 0001_initial_schema.py
│   ├── app/
│   │   ├── main.py            # FastAPI entry point (v0.6.0-M6)
│   │   ├── api/
│   │   │   ├── auth.py        # POST /auth/token, GET /auth/me
│   │   │   ├── dashboard.py   # GET /dashboard (department-scoped for HOD)
│   │   │   ├── conflicts.py   # GET /conflicts (HC-01..HC-08 checks)
│   │   │   ├── workload.py    # GET /workload (HC-07 capacity metrics)
│   │   │   ├── planner.py     # POST /planner/optimize, GET /planner/eligibility (M3)
│   │   │   ├── simulation.py  # POST /simulation/run, GET /history, GET /{id}, POST /{id}/approve (M4)
│   │   │   ├── decisions.py   # POST /whatif, GET /decisions, GET /decisions/{id} (M5 aliases)
│   │   │   ├── academic.py    # GET /departments, GET /faculty (M5)
│   │   │   └── query.py       # POST /query: NL intent parsing & grounded explanation (M6)
│   │   ├── core/
│   │   │   ├── config.py      # Settings (pydantic-settings)
│   │   │   ├── security.py    # JWT helpers
│   │   │   └── permissions.py # Role enforcement (Principal vs HOD)
│   │   ├── db/
│   │   │   ├── models.py      # SQLAlchemy ORM models (14 tables including decision & decision_evidence)
│   │   │   ├── session.py     # Engine + SessionLocal
│   │   │   └── seed.py        # Reproducible synthetic data
│   │   ├── engine/            # Deterministic Rule Engine, Solver, Critic & Simulation
│   │   │   ├── __init__.py
│   │   │   ├── rules.py       # HC-01..HC-10, SP-01..SP-04, validation suites
│   │   │   ├── eligibility.py # Candidate pool evaluation & rejection generator (M3)
│   │   │   ├── solver.py      # OR-Tools CP-SAT joint solver & Greedy baseline (M3)
│   │   │   ├── planner.py     # JointOptimizationPlanner coordinator & validation (M3)
│   │   │   ├── critic.py      # Independent Critic: multi-angle verification & sanity checks (M4)
│   │   │   └── simulation.py  # Non-mutating What-If simulation pipeline & audit persistence (M4)
│   │   ├── llm/               # Provider-independent LLM subsystem (M6)
│   │   │   ├── __init__.py
│   │   │   ├── interface.py   # LLMProvider abstract base class & provider factory
│   │   │   ├── groq_client.py # Official Groq API client (qwen/qwen3.8-27b) with bounded retries & fallback
│   │   │   ├── fallback.py    # Deterministic rule-based intent parsing & explanation generation
│   │   │   └── resolver.py    # Entity & temporal resolver (faculty names/codes, dates)
│   │   ├── schemas/
│   │   │   ├── auth.py        # TokenResponse, UserPublic
│   │   │   ├── dashboard.py   # DashboardResponse
│   │   │   ├── rules.py       # Violation, RuleValidationResult, ComparisonResult, etc.
│   │   │   ├── planner.py     # OptimizationPlan, AssignmentProposal, CandidateEligibility (M3)
│   │   │   ├── simulation.py  # SimulationRequest, SimulationResponse, CriticResult, AuditListItem (M4)
│   │   │   └── llm.py         # ParsedIntent, ExplanationRequest, QueryRequest, QueryResponse (M6)
│   │   └── services/
│   │       └── timetable.py   # Query helpers
│   └── tests/
│       ├── conftest.py        # Shared fixtures (DB transaction isolation)
│       ├── test_health.py     # Health, auth, dashboard API tests (11 tests)
│       ├── test_seed.py       # Seed data verification tests (26 tests)
│       ├── test_rules.py      # M2 Rule Engine comprehensive test suite (28 tests)
│       ├── test_planner.py    # M3 Candidate generation & optimization test suite (12 tests)
│       ├── test_simulation.py # M4 Simulation, Critic & audit persistence test suite (7 tests)
│       ├── test_security.py   # M5 Authorization & cross-department access tests (7 tests)
│       └── test_llm.py        # M6 Groq & deterministic fallback test suite (10 tests)
```
```

