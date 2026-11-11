# Campus OS — System Architecture

> ⚠ **SYNTHETIC DATA DISCLAIMER**  
> All data, faculty names, course codes, timetable entries, and operational records in Campus OS are **100% synthetic** and generated strictly for research, benchmark evaluation, and demonstration purposes. They do not represent any real educational institution, individual, or schedule.

---

## 1. System Overview

Campus OS (ANVIL) is an operational decision-support platform engineered for higher education institutions. Academic scheduling during disruptions (e.g., sudden faculty medical leaves, equipment outages, emergency room reallocations) requires solving highly constrained discrete combinatorial optimization problems under tight time pressure.

Traditional timetable management systems suffer from two fatal extremes:
1. **Manual Ad-Hoc Adjustments:** Administrators manually shuffle instructors via spreadsheets or phone calls, routinely introducing hard timetable clashes, violating university workload policies, or assigning faculty without subject-matter expertise.
2. **Naive Autonomous Agents / "LLM Schedulers":** Unconstrained generative AI agents attempt to generate or reschedule classes directly. Because language models lack formal constraint solvers, they hallucinate assignments, violate physical room limits, exceed workload caps, and cannot guarantee operational safety.

Campus OS bridges this gap with a **hybrid neuro-symbolic architecture**:
- **Interface Tier:** Natural language parsing and human-readable briefing generation via Large Language Models (Groq `qwen/qwen3.8-27b`) or a deterministic grounded fallback.
- **Decision Invariant:** The LLM is strictly an interface component. It **never** computes timetable feasibility, assigns faculty, calculates workload hours, or modifies operational records.
- **Optimization Tier:** A deterministic constraint-satisfaction solver powered by **Google OR-Tools CP-SAT**, formulating scheduling as an exact Integer Linear Program / Constraint Programming problem.
- **Verification Tier:** An independent, multi-angle **Critic Engine** that revalidates all proposed assignments against formal hard constraints before any recommendation is presented to administrators.
- **Audit & Governance Tier:** Immutable PostgreSQL audit persistence and human-in-the-loop administrative approval.

---

## 2. High-Level Architecture Diagram

```
+---------------------------------------------------------------------------------------+
|                                    PRESENTATION TIER                                  |
|                                                                                       |
|   React 19 + TypeScript + Vite + Tailwind CSS SPA                                     |
|   ├── Screen 1: Operations Dashboard (KPIs, Planted Conflicts, Workload Distribution) |
|   ├── Screen 2: What-If Simulator (NL Query, 1-Click Hero, Multi-Plan Comparison)     |
|   ├── Screen 3: Decision Detail & Reasoning Inspector (Candidate Rejection Proofs)    |
|   └── Screen 4: Decision Audit Log (Immutable Records, Approval Lifecycle, HC-10)     |
+-------------------------------------------+-------------------------------------------+
                                            | HTTP / REST (JSON)
                                            v
+---------------------------------------------------------------------------------------+
|                               FASTAPI APPLICATION GATEWAY                             |
|                                                                                       |
|   OAuth2 Password Flow + JWT (HS256) | Role-Based Access Control (RBAC)               |
|   ├── Principal: Unrestricted institution-wide visibility                             |
|   └── HOD (CS, EC, ME): Strictly isolated to own department (HTTP 403 enforcement)   |
|                                                                                       |
|   API Routers:                                                                        |
|   ├── /auth          -> Authentication & Profile                                      |
|   ├── /dashboard     -> Institutional KPI Metrics & Summaries                         |
|   ├── /conflicts     -> Deterministic Rule Engine Conflict Scans                      |
|   ├── /workload      -> Faculty Capacity & Workload Saturation                        |
|   ├── /planner       -> Candidate Eligibility & CP-SAT Optimization                   |
|   ├── /simulation    -> Non-Mutating What-If Pipeline & Critic Verification           |
|   ├── /decisions     -> Audit Trail & Administrative Approval Lifecycle               |
|   ├── /academic      -> Departments & Faculty Metadata                                |
|   └── /query         -> Natural Language Interface (Groq / Deterministic Fallback)    |
+---------------------+-------------------------------------------+---------------------+
                      |                                           |
                      v                                           v
+-------------------------------------+   +---------------------------------------------+
|        LLM INTERFACE SUBSYSTEM      |   |        DETERMINISTIC DECISION ENGINE        |
|                                     |   |                                             |
|  Abstract Provider Interface        |   |  1. Candidate Pool Generator                |
|  ├── Groq API Client                |   |     - Evaluates HC-01, HC-03, HC-06, HC-07  |
|  │   (qwen/qwen3.8-27b, JSON mode)  |   |     - Emits structured CandidateRejections  |
|  └── Deterministic Grounded Fallback|   |  2. Google OR-Tools CP-SAT Planner          |
|      (Regex + Template Reports)     |   |     - Lexicographic: Coverage >> Soft Score |
|                                     |   |     - Generates up to 3 distinct plans      |
|  Entity & Temporal Resolver         |   |  3. Greedy Baseline Comparator              |
|  ├── Faculty Names & Codes -> UUIDs |   |     - Benchmarks speed vs. quality          |
|  └── "next week Mon-Wed" -> Dates   |   |  4. Independent Critic Engine               |
|                                     |   |     - Multi-angle validation suite          |
|  * Strictly interface-only;         |   |     - Rejects any plan with new hard clash  |
|    cannot mutate database or plans  |   |  5. Non-Mutating Simulation Pipeline        |
+-------------------------------------+   +---------------------+-----------------------+
                                                                |
                                                                v
+---------------------------------------------------------------------------------------+
|                                    PERSISTENCE TIER                                   |
|                                                                                       |
|   PostgreSQL 14+ Relational Database (14 Tables via SQLAlchemy ORM & Alembic)         |
|   ├── Master Template:  timetable_entry (weekly blueprint, day_of_week + slot)        |
|   ├── Operational Data: class_occurrence (dated instances, override_faculty_id)      |
|   ├── Constraints Data: faculty, department, course, room, section, faculty_leave     |
|   └── Governance Audit: decision, decision_evidence (immutable snapshot & diffs)      |
+---------------------------------------------------------------------------------------+
```

---

## 3. Core Architectural Subsystems

### 3.1. Temporal Modeling: Master Template vs. Dated Occurrences

A foundational flaw in naive academic schedulers is treating timetables as static, day-agnostic grids. In actual campus operations, schedules operate across two distinct temporal planes:

1. **Master Weekly Template (`timetable_entry`):**
   - Represents the recurring semester blueprint (e.g., *Computer Networks is taught every Monday at 10:00 in Room 201 by Dr. Raj Sharma*).
   - Indexed by `day_of_week` (0=Monday ... 4=Friday) and `period_slot_id`.
   - Never modified during day-to-day operational adjustments.
2. **Dated Class Occurrences (`class_occurrence`):**
   - Represents concrete calendar instances (e.g., *Computer Networks on Monday, November 2, 2026, Period 2*).
   - Stores `calendar_date`, `status` (`SCHEDULED`, `COMPLETED`, `CANCELLED`), and `override_faculty_id`.
   - During substitute assignments or temporary reallocations, **only** `override_faculty_id` on the dated occurrence is updated. The master recurring template remains completely untouched.

```
       Semester Blueprint                         Operational Reality
  +--------------------------+               +--------------------------+
  |     timetable_entry      |               |     class_occurrence     |
  +--------------------------+               +--------------------------+
  | id: UUID                 |               | id: UUID                 |
  | course_id: CS301         |  expanded     | date: 2026-11-02         |
  | faculty_id: Dr. Raj (CS) | ------------> | period: Mon P2           |
  | day_of_week: Monday      |  into dated   | original_faculty_id: Raj |
  | period_slot: P2 (10:00)  |  occurrences  | override_faculty_id: NULL|
  | room_id: Room 201        |               | status: SCHEDULED        |
  +--------------------------+               +-------------+------------+
                                                           |
                                           Simulation /    | Approved
                                           Approval        v Substitution
                                             +--------------------------+
                                             | override_faculty_id:     |
                                             |   Dr. Priya Nair (CS004) |
                                             +--------------------------+
```

### 3.2. Deterministic Rule Engine (`RuleEngine`)

The rule engine acts as the ground-truth authority on timetable validity. It evaluates 10 Hard Constraints (`HC-01` to `HC-10`) and 4 Soft Preferences (`SP-01` to `SP-04`).

#### Hard Constraints (Zero Tolerance):
- **`HC-01` Faculty Double-Booking:** A faculty member cannot teach more than one class in the same period.
- **`HC-02` Room Double-Booking:** A room cannot host more than one class in the same period.
- **`HC-03` Section Double-Booking:** A student section cannot attend more than one class in the same period.
- **`HC-04` Room Capacity Violation:** Room student capacity must be $\ge$ section enrollment.
- **`HC-05` Room Type Mismatch:** Courses requiring specialized laboratories cannot be scheduled in standard classrooms.
- **`HC-06` Faculty Qualification / Expertise:** Faculty must hold approved subject expertise tags matching the course.
- **`HC-07` Maximum Weekly Workload:** Assigned teaching hours must not exceed faculty contract caps (14–18 hours/week).
- **`HC-08` Faculty Leave Conflict:** Faculty on approved leave cannot be assigned to teach on those dates.
- **`HC-09` Consecutive Hours Cap:** Faculty cannot teach more than 3 consecutive periods without a break.
- **`HC-10` Operational Invariance:** Non-mutating simulations must never write to operational timetable tables.

#### Soft Preferences (Weighted Optimization):
- **`SP-01` Department Affinity (Weight: 30):** Assigning faculty from the same department as the course.
- **`SP-02` Workload Balancing (Weight: 25):** Distributing assignments evenly to avoid overloading faculty near their cap.
- **`SP-03` Schedule Continuity (Weight: 25):** Minimizing schedule fragmentation (isolated gaps / single-period days).
- **`SP-04` Subject Specialization Match (Weight: 20):** Preferring primary domain experts over secondary cross-disciplinary backups.

---

### 3.3. Google OR-Tools CP-SAT Planner

The optimization engine models substitute planning as a Constraint Programming / Integer Linear Programming problem:

- **Decision Variables:**
  $$x_{ij} \in \{0, 1\} \quad \forall \text{ affected class occurrence } i \in I, \text{ eligible candidate faculty } j \in J_i$$
  where $x_{ij} = 1$ if faculty $j$ is assigned to class $i$, and $0$ otherwise.

- **Constraints:**
  1. *At Most One Instructor per Class:*
     $$\sum_{j \in J_i} x_{ij} \le 1 \quad \forall i \in I$$
  2. *No Concurrent Overlaps across Occurrences in the Same Slot:*
     $$\sum_{i \in I_t} x_{ij} \le 1 \quad \forall j, \forall \text{ period slot } t$$
  3. *Weekly Workload Bounds:*
     $$\text{current\_workload}_j + \sum_{i \in I} \text{duration}_i \cdot x_{ij} \le \text{max\_hours}_j \quad \forall j$$

- **Lexicographic Objective Function:**
  The CP-SAT model strictly prioritizes complete coverage over soft preferences:
  $$\text{Maximize } \quad 10{,}000 \cdot \sum_{i \in I} \sum_{j \in J_i} x_{ij} + \sum_{i \in I} \sum_{j \in J_i} \text{Score}_{ij} \cdot x_{ij}$$
  This ensures that the solver will **never** leave a class uncovered merely to achieve a marginally higher soft preference score on another class.

- **Multi-Alternative Diversity:**
  To provide decision-makers with meaningful operational choices, the solver generates up to 3 distinct alternatives:
  1. **Plan A (Balanced):** Standard balanced objective (SP-01 through SP-04).
  2. **Plan B (Continuity & Department Focus):** Heavy weighting on department affinity and minimizing instructor switching.
  3. **Plan C (Workload Relief Focus):** Heavy weighting on assigning faculty with the lowest existing workload.

---

### 3.4. Independent Critic Engine

To guard against solver formulation bugs, unexpected edge cases, or stale session state, the **Critic Engine** (`backend/app/engine/critic.py`) acts as an independent adversarial auditor:
1. **Zero-Knowledge Re-Evaluation:** The Critic accepts the proposed assignment delta and reconstructs the full calendar state in memory.
2. **RuleEngine Execution:** Runs `RuleEngine.compare_states(...)` over the baseline state vs. proposed state.
3. **Hard Constraint Audit:** Checks for newly introduced violations:
   $$\text{New Hard Violations} = \text{Violations}_{\text{proposed}} \setminus \text{Violations}_{\text{baseline}}$$
   If $\text{Count}(\text{New Hard Violations}) > 0$, the Critic immediately flags the plan as **`REJECTED`** (`critic_status: validation_failed`).
4. **Internal Assignment Overlap Check:** Verifies that no two proposed assignments in the same plan allocate the same faculty member to the same period.
5. **Workload Near-Capacity Warnings:** Computes whether any faculty member is pushed to $\ge 90\%$ of their weekly teaching cap, attaching explanatory warnings to the audit record.

---

### 3.5. Non-Mutating What-If Simulation Pipeline

The simulation pipeline executes in 12 strictly controlled steps:

```
[1. Request Ingestion] -> [2. Snapshot DB Row Counts] -> [3. Date & Occurrence Resolution]
         |
         v
[4. Eligible Candidate Generation (with Rejections)] -> [5. Soft Preference Scoring]
         |
         v
[6. CP-SAT Joint Optimization (3 Alternatives)] + [7. Greedy Baseline Benchmark]
         |
         v
[8. Independent Critic Verification] -> [9. Before/After State Diffing]
         |
         v
[10. Verify Zero DB Row Mutations (HC-10)] -> [11. Immutable Audit Trail Persistence]
         |
         v
[12. Structured SimulationResponse Delivery]
```

At step 10, the pipeline queries PostgreSQL table row counts. If any operational table (`timetable_entry`, `class_occurrence`, `faculty`, `faculty_leave`) has experienced an insert, update, or delete during simulation, the transaction is aborted with a critical safety fault.

---

### 3.6. LLM Interface & Fallback Subsystem

The LLM subsystem translates conversational user queries into structured operational parameters and converts optimization results into readable executive briefings.

- **Non-Negotiable Boundary:** The LLM cannot call database write functions, cannot generate assignments, and cannot override constraint checks.
- **Provider Interface:** `LLMProvider` abstract base class defining `parse_intent(...)` and `generate_explanation(...)`.
- **Primary Provider:** Groq Cloud API querying `qwen/qwen3.8-27b` with bounded 10s timeout, exponential backoff retries, and strict JSON output schema.
- **Deterministic Grounded Fallback:** When the Groq API key is omitted, offline, rate-limited, or fails schema validation, the system transparently falls back to a deterministic rule-based parser and template briefing generator. This guarantees **100% platform uptime and operational resilience**.

---

## 4. Security & Role-Based Access Control (RBAC)

Campus OS implements strict role-based data partitioning:

| Role | Tenant / Department Boundary | Permitted Actions |
|------|------------------------------|-------------------|
| **Principal** | Global (All Departments: CS, EC, ME) | View institutional KPIs, run simulations across all departments, inspect all candidate pools, approve any substitution. |
| **HOD (CS)** | Strictly isolated to Computer Science | View CS dashboard, run simulations for CS faculty, view CS faculty workloads. Cross-department queries return `HTTP 403 Forbidden`. |
| **HOD (EC)** | Strictly isolated to Electronics | View EC dashboard, run simulations for EC faculty. Cannot view or simulate CS/ME operations (`HTTP 403 Forbidden`). |
| **HOD (ME)** | Strictly isolated to Mechanical Eng | View ME dashboard, run simulations for ME faculty. Cannot view or simulate CS/EC operations (`HTTP 403 Forbidden`). |

Enforcement occurs at the FastAPI gateway level via `app/core/permissions.py`:
- `get_current_user` validates JWT bearer tokens (HS256).
- `verify_department_access(user, department_id)` validates that HODs never query or mutate resources outside their assigned department UUID.

