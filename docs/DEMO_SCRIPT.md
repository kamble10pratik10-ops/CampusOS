# Campus OS — 5-Minute Live Demonstration Script

> ⚠ **SYNTHETIC DATA DISCLAIMER**  
> All data, faculty names, course codes, timetable entries, and operational records in Campus OS are **100% synthetic**. They do not represent any real educational institution, individual, or schedule.

---

## Overview

This script is an exact, timed, 5-minute walkthrough designed for live technical demonstrations, evaluations, and engineering presentations. It highlights the core capabilities of Campus OS:
1. **Deterministic Rule Engine:** Ground-truth conflict detection with zero hallucinations.
2. **CP-SAT Joint Optimization:** Solving multi-class substitute assignments with 100% coverage.
3. **Independent Critic Engine:** Adversarial validation guaranteeing zero new hard clashes.
4. **Natural Language Interface:** Groq `qwen/qwen3.8-27b` intent parsing with deterministic offline fallback.
5. **Governance & Audit Trail:** Non-mutating simulation (`HC-10`) and immutable PostgreSQL audit logs.

---

## Pre-Flight Setup & Launch

Ensure backend and frontend are running:

```bash
# Terminal 1: Backend
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: Frontend
cd frontend
npm run dev
```

Open your browser to: **`http://localhost:5173`**  
Default demo user: **`Principal` (`principal@campus.os`)** (switchable via the top navigation bar).

---

## Minute-by-Minute Walkthrough

### ⏱ Minute 1: Operations Dashboard (Screen 1)
**Goal:** Establish baseline situational awareness and verify deterministic conflict detection.

1. **Dashboard Overview:**
   - Point out the top navigation bar with the **Role Switcher** (`Principal`, `HOD CS`, `HOD EC`, `HOD ME`). Show that you are currently logged in as the `Principal` with campus-wide visibility.
   - Point to the four primary KPI cards:
     - **Faculty Available:** `29 / 30` (1 on leave)
     - **Active Courses:** `40`
     - **Rooms & Labs:** `15`
     - **Weekly Occurrences:** `336`
2. **Planted Conflicts Audit:**
   - Scroll to the **Operational Conflicts Detected** panel.
   - Explain: *"Campus OS includes a deterministic rule engine enforcing 10 Hard Constraints. Here, it has detected the 5 planted template conflicts:"*
     - `HC-01`: Dr. Arun Kumar double-booked on Mon P1.
     - `HC-02`: Room 301 double-booked on Tue P3.
     - `HC-04`: CS-1A over-enrolled in Room 101.
     - `HC-05`: Mobile Computing lab placed in non-lab room.
     - `HC-06`: Missing subject qualification tag on ML course.
3. **Workload Distribution:**
   - Show the interactive faculty workload chart displaying teaching hours against individual contractual caps (14–18 hrs).
4. **Transition:** Click the blue **"Simulate Hero Leave Scenario"** button (or navigate to *What-If Simulator* in the navbar).

---

### ⏱ Minute 2: What-If Simulator & Natural Language Query (Screen 2)
**Goal:** Demonstrate Groq AI intent parsing grounded strictly by the CP-SAT solver and Critic.

1. **Natural Language Interface:**
   - In the natural language query bar, type (or click the example):
     ```text
     Dr. Raj Sharma is on leave next week Monday to Wednesday
     ```
   - Click **Run Simulation**.
2. **Observe Parsed Intent Chips:**
   - Point out the real-time chips beneath the query bar:
     - **Intent:** `leave_replacement`
     - **Target:** `Dr. Raj Sharma (CS001)`
     - **Date Range:** `2026-11-02 to 2026-11-04` (automatically anchored to `DEMO_TODAY = 2026-10-26`)
     - **Confidence:** `0.95+`
3. **AI Operational Briefing Card:**
   - Point to the generated executive summary card.
   - Highlight the provider tag (`groq (qwen/qwen3.8-27b)` or `deterministic_fallback`).
   - Emphasize the **Decision Invariant**: *"Notice that the briefing accurately reports 6 affected classes and proposed substitutes, but the LLM did not make the assignments. The assignments were computed by Google OR-Tools CP-SAT and verified by our Critic."*
4. **Critic Verification Banner:**
   - Point to the green badge: **`CRITIC APPROVED: 0 New Hard Violations`**.
   - Explain that an independent Critic engine re-evaluated the entire institutional schedule in memory and verified that no new conflicts were introduced.

---

### ⏱ Minute 3: Multi-Alternative Comparison & Workload Shifts (Screen 2)
**Goal:** Show decision-support diversity and mathematical workload balancing.

1. **Alternative Plans:**
   - Point to the alternative plan tabs:
     - **Plan A (Balanced):** Optimizes overall balance across all 4 soft preferences (`Score: 84.2`).
     - **Plan B (Continuity & Department Focus):** Minimizes instructor switching.
     - **Plan C (Workload Focus):** Prioritizes faculty with the lightest current teaching loads.
     - **Greedy Baseline:** Compare against the greedy heuristic baseline to demonstrate why exact CP-SAT optimization is superior.
2. **Proposed Replacement Schedule:**
   - Inspect the 6 resolved classes for Dr. Raj Sharma's leave:
     - All 6 classes assigned to qualified colleagues (e.g., Dr. Priya Nair, Dr. Vikram Rao, Dr. Sneha Patel).
     - Each assigned instructor holds the verified `networking` qualification tag.
3. **Workload Shift Table:**
   - Scroll down to the **Faculty Workload Shifts** section.
   - Show how the added hours shift individual weekly loads (e.g., `Dr. Priya Nair: 12.0h -> 15.0h / max 16.0h`), demonstrating that nobody exceeds their contractual limit (`HC-07`).

---

### ⏱ Minute 4: Reasoning Inspector & Candidate Pool Proofs (Screen 3)
**Goal:** Defend algorithmic decisions and demonstrate transparency.

1. **Navigate to Reasoning Inspector:**
   - Click the **"Inspect Reasoning & Candidate Pools"** link (or select *Decision Details* in the navbar).
2. **Structured Candidate Rejections:**
   - Open the Candidate Eligibility breakdown for one of the affected classes (e.g., *Computer Networks on Monday Period 2*).
   - Point to the rejected faculty table and explain the structured rejection tags:
     - `MISSING_EXPERTISE`: Faculty member lacks the `networking` domain qualification.
     - `ON_LEAVE`: Faculty member is concurrently absent on that date.
     - `OVERLOADED`: Assigning the class would push the instructor past their weekly hour cap.
   - Highlight: *"This transparency eliminates administrative guesswork. Every candidate exclusion is mathematically traceable."*
3. **Evidence Artifacts:**
   - Review the cryptographic-style JSON evidence artifacts generated by the Critic.

---

### 5 ⏱ Minute 5: Approval, Audit Trail & Security Boundary (Screen 4)
**Goal:** Complete the governance loop and verify role-based security.

1. **Administrative Approval:**
   - Return to the simulator and click **"Approve Recommendation"**.
   - Observe the notification confirming the decision has transitioned from `simulated` to `approved`.
2. **Decision Audit Log (Screen 4):**
   - Click **Audit Log** in the navbar.
   - Point to the newly recorded decision in the audit table:
     - Displays timestamp, approving admin (`principal@campus.os`), scenario type, coverage (100%), and Critic status (`approved`).
   - Highlight the **HC-10 Non-Mutation Guarantee** notice:
     - Reiterate: *"The operational master template was never altered during simulation. Only approved substitute overrides are stored."*
3. **Role-Based Access Control (RBAC) Demonstration:**
   - In the top navbar, switch the user role to **`HOD (EC)`**.
   - Notice the dashboard immediately updates to show only Electronics & Communication data.
   - Attempt to simulate a CS faculty replacement (e.g. Dr. Raj Sharma) as HOD EC.
   - Show that the backend strictly returns `HTTP 403 Forbidden`, preventing cross-department tampering.
4. **Conclusion:** Wrap up by summarizing that Campus OS delivers a mathematically safe, explainable, and fully audited operational platform.

---

## Contingency: Offline / No-Groq Demonstration

If demonstrating in an environment without internet access or without a configured `GROQ_API_KEY`:
1. Submit the same query: `"Dr. Raj Sharma is on leave next week Monday to Wednesday"`.
2. The system seamlessly falls back to the **Deterministic Grounded Fallback**.
3. Point to the badge: `provider: "deterministic_fallback"`.
4. Highlight that **100% of the optimization, conflict checks, candidate proofs, and audit logging operate with zero degradation**.

