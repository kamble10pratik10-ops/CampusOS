# Campus OS — Data Dictionary & Seed Dataset Specification

> ⚠ **SYNTHETIC DATA DISCLAIMER**  
> All records, faculty names, email addresses, course titles, room numbers, section names, and timetable schedules documented herein are **100% synthetic**. They were programmatically generated to create a realistic, reproducible academic operations benchmark and do not represent any real institution, living individual, or commercial entity.

---

## 1. Database Schema & Data Dictionary

Campus OS utilizes PostgreSQL 14+ with an ACID-compliant relational schema managed via SQLAlchemy ORM and Alembic migrations (`0001_initial_schema.py`). The schema comprises **14 tables** grouped into four domain categories:

```
+----------------------------------------------------------------------------------+
|                            CAMPUS OS RELATIONAL SCHEMA                           |
+----------------------------------------------------------------------------------+
| [Core Academic]         [Facilities]             [Scheduling Core]               |
|  * department            * building               * period_slot                  |
|  * faculty               * room                   * timetable_entry (Template)   |
|  * faculty_expertise                              * class_occurrence (Dated)     |
|  * faculty_leave        [Auth & Security]                                        |
|  * course                * user_account          [Audit & Governance]            |
|  * course_offering                                * decision                     |
|  * section                                        * decision_evidence            |
+----------------------------------------------------------------------------------+
```

---

### Table 1: `department`
Represents academic divisions within the institution (e.g., Computer Science, Electronics, Mechanical Engineering).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | `PRIMARY KEY` | Unique department identifier. |
| `code` | `VARCHAR(16)` | `UNIQUE, NOT NULL` | Short department code (e.g., `CS`, `EC`, `ME`). |
| `name` | `VARCHAR(128)` | `NOT NULL` | Full department name (e.g., `Computer Science & Engineering`). |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL, DEFAULT now()` | Timestamp of record creation. |

---

### Table 2: `user_account`
Administrative accounts for authentication, authorization, and tenant scoping.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | `PRIMARY KEY` | Unique user account identifier. |
| `email` | `VARCHAR(255)` | `UNIQUE, NOT NULL` | Login email address. |
| `hashed_password` | `VARCHAR(255)` | `NOT NULL` | Bcrypt password hash. |
| `role` | `VARCHAR(32)` | `NOT NULL` | Role: `'principal'` or `'hod'`. |
| `department_id` | `UUID` | `NULLABLE, FK -> department.id` | Department isolation boundary (null for Principal). |
| `is_active` | `BOOLEAN` | `NOT NULL, DEFAULT TRUE` | Active account flag. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL, DEFAULT now()` | Timestamp of record creation. |

---

### Table 3: `faculty`
Faculty members, instructional ranks, and contractual weekly teaching load limits.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | `PRIMARY KEY` | Unique faculty identifier. |
| `employee_code` | `VARCHAR(32)` | `UNIQUE, NOT NULL` | Institutional employee ID (e.g., `CS001`, `EC005`). |
| `name` | `VARCHAR(128)` | `NOT NULL` | Full faculty name (e.g., `Dr. Raj Sharma`). |
| `email` | `VARCHAR(255)` | `UNIQUE, NOT NULL` | Official academic email address. |
| `department_id` | `UUID` | `NOT NULL, FK -> department.id` | Home academic department. |
| `designation` | `VARCHAR(64)` | `NOT NULL` | Rank: `Professor`, `Associate Professor`, `Assistant Professor`. |
| `max_weekly_hours` | `INTEGER` | `NOT NULL` | Contractual weekly teaching hours cap (14, 16, or 18 hrs). |
| `is_active` | `BOOLEAN` | `NOT NULL, DEFAULT TRUE` | Employment status. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL, DEFAULT now()` | Timestamp of record creation. |

---

### Table 4: `faculty_expertise`
Maps faculty members to subject-matter expertise tags for qualification enforcement (`HC-06`).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | `PRIMARY KEY` | Unique expertise record identifier. |
| `faculty_id` | `UUID` | `NOT NULL, FK -> faculty.id` | Faculty reference. |
| `tag` | `VARCHAR(64)` | `NOT NULL` | Subject domain tag (e.g., `networking`, `algorithms`, `vlsi`). |
| `proficiency` | `INTEGER` | `NOT NULL, DEFAULT 1` | Proficiency weight (1=Competent, 2=Primary Expert). |

---

### Table 5: `faculty_leave`
Approved faculty leaves for conflict checking (`HC-08`).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | `PRIMARY KEY` | Unique leave record identifier. |
| `faculty_id` | `UUID` | `NOT NULL, FK -> faculty.id` | Faculty member on leave. |
| `start_date` | `DATE` | `NOT NULL` | Start date of leave period (inclusive). |
| `end_date` | `DATE` | `NOT NULL` | End date of leave period (inclusive). |
| `reason` | `VARCHAR(255)` | `NOT NULL` | Administrative leave reason (e.g., `Medical Leave`, `Conference`). |
| `status` | `VARCHAR(32)` | `NOT NULL, DEFAULT 'approved'` | Leave approval status. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL, DEFAULT now()` | Timestamp of leave filing. |

---

### Table 6: `building`
Campus buildings housing classrooms, laboratories, and lecture halls.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | `PRIMARY KEY` | Unique building identifier. |
| `name` | `VARCHAR(128)` | `NOT NULL` | Building name (e.g., `Turing Block`, `Tesla Hall`). |
| `code` | `VARCHAR(16)` | `UNIQUE, NOT NULL` | Short code (e.g., `TB`, `TH`). |

---

### Table 7: `room`
Physical instructional spaces, capacities, and laboratory designations (`HC-04`, `HC-05`).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | `PRIMARY KEY` | Unique room identifier. |
| `building_id` | `UUID` | `NOT NULL, FK -> building.id` | Containing building. |
| `room_number` | `VARCHAR(32)` | `NOT NULL` | Room designation (e.g., `101`, `202`, `Lab 1`). |
| `capacity` | `INTEGER` | `NOT NULL` | Maximum student seating capacity (35 to 70). |
| `is_lab` | `BOOLEAN` | `NOT NULL, DEFAULT FALSE` | Flag indicating specialized laboratory facilities. |

---

### Table 8: `course`
Academic course catalog entries.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | `PRIMARY KEY` | Unique course identifier. |
| `department_id` | `UUID` | `NOT NULL, FK -> department.id` | Offering department. |
| `code` | `VARCHAR(32)` | `UNIQUE, NOT NULL` | Course catalog code (e.g., `CS301`, `EC204`). |
| `title` | `VARCHAR(255)` | `NOT NULL` | Course title (e.g., `Computer Networks`). |
| `semester` | `INTEGER` | `NOT NULL` | Curricular semester (1 through 8). |
| `lecture_hours` | `INTEGER` | `NOT NULL` | Required weekly lecture hours (typically 3 or 4). |
| `lab_hours` | `INTEGER` | `NOT NULL, DEFAULT 0` | Required weekly laboratory hours (0 or 2). |
| `requires_lab` | `BOOLEAN` | `NOT NULL, DEFAULT FALSE` | Flag requiring laboratory room type (`HC-05`). |
| `primary_tag` | `VARCHAR(64)` | `NOT NULL` | Primary required expertise domain tag (`HC-06`). |

---

### Table 9: `course_offering`
Active semester offering linking courses to instructional academic years.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | `PRIMARY KEY` | Unique offering identifier. |
| `course_id` | `UUID` | `NOT NULL, FK -> course.id` | Course reference. |
| `academic_year` | `VARCHAR(16)` | `NOT NULL` | Term identifier (e.g., `2026-2027`). |
| `semester_term` | `VARCHAR(16)` | `NOT NULL` | Term (e.g., `ODD`, `EVEN`). |

---

### Table 10: `section`
Cohort student groups attending classes together (`HC-03`, `HC-04`).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | `PRIMARY KEY` | Unique section identifier. |
| `department_id` | `UUID` | `NOT NULL, FK -> department.id` | Department reference. |
| `name` | `VARCHAR(32)` | `NOT NULL` | Section name (e.g., `CS-3A`, `EC-2B`). |
| `year` | `INTEGER` | `NOT NULL` | Curricular year (1, 2, 3, 4). |
| `enrollment` | `INTEGER` | `NOT NULL` | Enrolled student headcount (50 to 65 students). |

---

### Table 11: `period_slot`
Standard institutional daily instructional time periods.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | `PRIMARY KEY` | Unique period slot identifier. |
| `day_of_week` | `INTEGER` | `NOT NULL` | Day index (0=Monday, 1=Tuesday ... 4=Friday). |
| `period_number` | `INTEGER` | `NOT NULL` | Period index (1 through 6). |
| `start_time` | `TIME` | `NOT NULL` | Period start time (e.g., `09:00:00`). |
| `end_time` | `TIME` | `NOT NULL` | Period end time (e.g., `10:00:00`). |
| `label` | `VARCHAR(32)` | `NOT NULL` | Human-readable label (e.g., `Mon P1 (09:00-10:00)`). |

---

### Table 12: `timetable_entry` (Master Template)
Recurring weekly timetable blueprint. **Never modified during daily operational adjustments.**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | `PRIMARY KEY` | Unique timetable entry identifier. |
| `course_offering_id` | `UUID` | `NOT NULL, FK -> course_offering.id` | Scheduled course offering. |
| `faculty_id` | `UUID` | `NOT NULL, FK -> faculty.id` | Assigned regular instructor. |
| `room_id` | `UUID` | `NOT NULL, FK -> room.id` | Assigned classroom or lab. |
| `section_id` | `UUID` | `NOT NULL, FK -> section.id` | Student cohort section. |
| `period_slot_id` | `UUID` | `NOT NULL, FK -> period_slot.id` | Weekly time period. |
| `day_of_week` | `INTEGER` | `NOT NULL` | Denormalized day index (0..4). |

---

### Table 13: `class_occurrence` (Dated Operational Reality)
Concrete calendar occurrences of classes. Temporary substitutions mutate `override_faculty_id`.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | `PRIMARY KEY` | Unique dated occurrence identifier. |
| `timetable_entry_id` | `UUID` | `NOT NULL, FK -> timetable_entry.id` | Source master template reference. |
| `calendar_date` | `DATE` | `NOT NULL` | Concrete calendar date (e.g., `2026-11-02`). |
| `period_slot_id` | `UUID` | `NOT NULL, FK -> period_slot.id` | Scheduled period slot. |
| `original_faculty_id`| `UUID` | `NOT NULL, FK -> faculty.id` | Regular blueprint instructor. |
| `override_faculty_id`| `UUID` | `NULLABLE, FK -> faculty.id` | Approved substitute instructor (if any). |
| `room_id` | `UUID` | `NOT NULL, FK -> room.id` | Assigned room. |
| `section_id` | `UUID` | `NOT NULL, FK -> section.id` | Attending section. |
| `status` | `VARCHAR(32)` | `NOT NULL, DEFAULT 'SCHEDULED'`| Status: `SCHEDULED`, `COMPLETED`, `CANCELLED`. |

---

### Table 14: `decision` & `decision_evidence` (Immutable Audit Trail)
Historical governance log persisting every what-if simulation, Critic verification, and administrative approval.

#### `decision`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | `PRIMARY KEY` | Unique decision audit identifier. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL, DEFAULT now()` | Timestamp of simulation. |
| `created_by` | `VARCHAR(255)` | `NOT NULL` | User email of initiator. |
| `scenario_type` | `VARCHAR(64)` | `NOT NULL` | Type (e.g., `FACULTY_LEAVE_REPLACEMENT`). |
| `status` | `VARCHAR(32)` | `NOT NULL` | Status: `'simulated'` or `'approved'`. |
| `summary` | `TEXT` | `NOT NULL` | Executive summary of scenario and resolution. |
| `request_payload` | `JSONB` | `NOT NULL` | Exact input parameters (dates, faculty UUID). |
| `result_payload` | `JSONB` | `NOT NULL` | Full simulation response, alternatives, and scores. |
| `critic_status` | `VARCHAR(32)` | `NOT NULL` | Critic verdict: `'approved'` or `'validation_failed'`. |
| `critic_notes` | `TEXT` | `NULLABLE` | Critic verification remarks and warnings. |
| `approved_at` | `TIMESTAMPTZ` | `NULLABLE` | Timestamp of administrative approval. |
| `approved_by` | `VARCHAR(255)` | `NULLABLE` | User email of approving administrator. |

#### `decision_evidence`
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | `PRIMARY KEY` | Unique evidence artifact identifier. |
| `decision_id` | `UUID` | `NOT NULL, FK -> decision.id` | Parent decision reference. |
| `evidence_type` | `VARCHAR(64)` | `NOT NULL` | Type: `'CRITIC_VERIFICATION'`, `'STATE_DIFF'`, `'RULE_AUDIT'`. |
| `title` | `VARCHAR(255)` | `NOT NULL` | Human-readable artifact label. |
| `data` | `JSONB` | `NOT NULL` | Structured payload of evidence data. |

---

## 2. Seed Dataset Summary & Scale

The synthetic seed dataset (`backend/app/db/seed.py`) generates a fully populated operational semester:

| Metric | Quantity | Distribution / Details |
|--------|----------|------------------------|
| **Departments** | 3 | Computer Science (`CS`), Electronics (`EC`), Mechanical Eng (`ME`) |
| **Faculty Members** | 30 | 10 per department; ranks: 3 Professors, 4 Associate, 3 Assistant |
| **Workload Caps** | 30 | Professors (14 hrs/wk), Associate (16 hrs/wk), Assistant (18 hrs/wk) |
| **Courses** | 40 | 14 CS courses, 13 EC courses, 13 ME courses |
| **Lab Requirements** | 10 | 10 courses require specialized laboratory facilities |
| **Sections** | 12 | 4 cohorts per department (Years 1 to 4; 50 to 65 students each) |
| **Rooms** | 15 | 10 standard lecture halls (cap: 60-70), 5 specialized labs (cap: 35-40) |
| **Period Slots** | 30 | 6 periods daily $\times$ 5 weekdays (09:00 to 16:00) |
| **Master Timetable Entries** | 336 | Weekly recurring schedule entries |
| **Dated Class Occurrences** | 336+ | Expanded across active operational semester weeks |
| **Demo User Accounts** | 4 | 1 Principal (`principal@campus.os`) + 3 HODs (`hod.{cs,ec,me}@campus.os`) |

---

## 3. Planted Template Conflicts (M2 Deterministic Rule Engine Testbed)

To empirically verify that the rule engine catches operational violations deterministically, **5 hard conflicts** were intentionally seeded into the recurring master template:

| Violation ID | Conflict Rule | Planted Scenario Description | Traceable Entity IDs |
|--------------|---------------|------------------------------|----------------------|
| **`HC-01`** | Faculty Double-Booking | Dr. Arun Kumar (`CS003`) is assigned to teach two different sections simultaneously on Monday Period 1 (09:00-10:00). | Faculty: `CS003`<br>Slot: Mon P1 |
| **`HC-02`** | Room Double-Booking | Room `301` (Turing Block) is booked simultaneously for `EC-1A` and `ME-1A` on Tuesday Period 3 (11:00-12:00). | Room: `301`<br>Slot: Tue P3 |
| **`HC-04`** | Room Capacity Breach | Section `CS-1A` (65 enrolled students) is scheduled in Room `101` (capacity 60) on Thursday Period 1 (09:00-10:00). | Section: `CS-1A`<br>Room: `101`<br>Overcrowd: +5 |
| **`HC-05`** | Room Type Mismatch | Course `CS402` (Mobile Computing Lab, requiring lab facilities) is scheduled in Room `101` (standard classroom) on Friday Period 5 (14:00-15:00). | Course: `CS402`<br>Room: `101` (is_lab: False) |
| **`HC-06`** | Missing Qualification | Dr. Sanjay Verma (`CS007`, Systems expert) is assigned to teach `CS301` (Machine Learning, requires `machine_learning` tag) on Friday Period 6. | Faculty: `CS007`<br>Course: `CS301`<br>Missing Tag: `machine_learning` |

---

## 4. The Hero Scenario Specification

The Hero Scenario represents the primary demonstration benchmark:

- **Target Faculty:** `Dr. Raj Sharma`
- **Employee Code:** `CS001`
- **Department:** Computer Science & Engineering
- **UUID:** `30000000-0000-0000-0000-000000000001`
- **Leave Duration:** 3 Days — `2026-11-02` (Monday) to `2026-11-04` (Wednesday)
- **Temporal Anchor:** `DEMO_TODAY = 2026-10-26` ("next week Monday to Wednesday")
- **Affected Dated Occurrences (6 Classes):**
  1. Monday Period 2 (10:00-11:00) — *Computer Networks* (`CS301`), Section `CS-3A`, Room `201`
  2. Monday Period 4 (13:00-14:00) — *Computer Networks* (`CS301`), Section `CS-3B`, Room `202`
  3. Tuesday Period 1 (09:00-10:00) — *Advanced Networking* (`CS401`), Section `CS-4A`, Room `203`
  4. Tuesday Period 3 (11:00-12:00) — *Advanced Networking* (`CS401`), Section `CS-4B`, Room `204`
  5. Wednesday Period 1 (09:00-10:00) — *Computer Networks* (`CS301`), Section `CS-3A`, Room `201`
  6. Wednesday Period 2 (10:00-11:00) — *Advanced Networking* (`CS401`), Section `CS-4A`, Room `203`

### Candidate Pool Dynamics & Resolution
- Eligible colleagues with `networking` expertise: Dr. Priya Nair (`CS004`), Dr. Vikram Rao (`CS006`), Dr. Sneha Patel (`CS008`).
- Ineligible candidates are tagged with structured rejection reasons:
  - `ON_LEAVE`: If on concurrent leave.
  - `MISSING_EXPERTISE`: If lacking the required `networking` qualification tag.
  - `OVERLOADED`: If adding the class would breach their weekly hour limit (`HC-07`).
- **CP-SAT Solver Result:** Solves all 6 classes with **100% complete coverage**, zero hard violations, and provides 3 distinct alternative allocations with transparent score breakdowns.

