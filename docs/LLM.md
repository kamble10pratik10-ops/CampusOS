# Campus OS — LLM Integration & Non-Mutation Guarantees

> ⚠ **SYNTHETIC DATA DISCLAIMER**  
> All data and scenarios handled by the LLM subsystem are **100% synthetic**. The LLM operates exclusively on mock institutional schemas and does not process, store, or output real personal identifiable information (PII).

---

## 1. Architectural Philosophy: The Non-Negotiable Decision Invariant

Campus OS employs Large Language Models exclusively as **interface translators** and **executive summarizers**, never as decision-makers or autonomous schedulers.

### The Decision Invariant Rule
> **"The LLM must never compute timetable feasibility, assign instructors to classes, calculate faculty workload hours, override institutional constraints, or mutate database state."**

```
+-----------------------------------------------------------------------------------+
|                           THE DECISION INVARIANT BOUNDARY                         |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  [User Natural Language Input]                                                    |
|              |                                                                    |
|              v                                                                    |
|  +-----------------------------------------------------------------------------+  |
|  |  LLM SUBSYSTEM (Groq qwen/qwen3.8-27b / Deterministic Fallback)             |  |
|  |  - Extracts intent: leave_replacement / check_conflicts / workload_report   |  |
|  |  - Resolves entities: "Dr. Raj Sharma" -> UUID 30000000-...                 |  |
|  |  - Resolves dates: "next week Mon to Wed" -> 2026-11-02 to 2026-11-04       |  |
|  +-----------------------------------------------------------------------------+  |
|              |                                                                    |
|              | Passes structured JSON parameters only                             |
|              v                                                                    |
|  +-----------------------------------------------------------------------------+  |
|  |  DETERMINISTIC OPTIMIZATION & VERIFICATION (OR-Tools CP-SAT + Critic)       |  |
|  |  * Solves combinatorial assignment with mathematical exactness              |  |
|  |  * Enforces HC-01 through HC-10 with zero tolerance                        |  |
|  |  * Calculates exact workload shift hours and balance metrics                |  |
|  +-----------------------------------------------------------------------------+  |
|              |                                                                    |
|              | Passes verified mathematical metrics and diffs                     |
|              v                                                                    |
|  +-----------------------------------------------------------------------------+  |
|  |  LLM EXPLANATION GENERATOR                                                  |  |
|  |  - Translates verified solver outputs into human-readable Markdown briefing  |  |
|  |  - Cannot hallucinate coverage; grounded strictly in solver facts           |  |
|  +-----------------------------------------------------------------------------+  |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

---

## 2. Groq Cloud API Integration

The primary LLM provider uses the official Groq OpenAI-compatible Chat Completions API.

- **Endpoint:** `https://api.groq.com/openai/v1/chat/completions`
- **Model:** `qwen/qwen3.8-27b`
- **Structured Output:** Strictly enforced using `response_format={"type": "json_object"}`.
- **Operational Timeouts & Retries:**
  - Client timeout: `10.0 seconds`
  - Max retries: `2 attempts` with exponential backoff (`0.5s` and `1.0s`).
  - Upon network failure, timeout, or rate limiting (`HTTP 429`), the system instantly and transparently falls back to the deterministic provider without interrupting the user.

---

## 3. Intent Parsing & Entity Resolution

### 3.1. Supported Intents
The system classifies natural language inputs into three operational workflows:
1. `leave_replacement`: Temporary instructor substitution due to faculty leave or emergency.
2. `check_conflicts`: Audit of timetable conflicts across template or dated schedules.
3. `workload_report`: Inspection of weekly faculty teaching hours and capacity limits.
4. `unknown`: Unrecognized queries routed to informative usage instructions.

### 3.2. Structured Intent Schema
The model returns a validated JSON object conforming to Pydantic schemas (`ParsedIntent`):

```json
{
  "intent": "leave_replacement",
  "faculty_name": "Dr. Raj Sharma",
  "employee_code": "CS001",
  "start_date": "2026-11-02",
  "end_date": "2026-11-04",
  "department_code": "CS",
  "confidence": 0.95
}
```

### 3.3. Grounded Entity & Temporal Resolver (`backend/app/llm/resolver.py`)
To prevent LLM hallucination of database primary keys:
1. **Entity Resolution:** The LLM extracts the plain-text name (`"Raj Sharma"`) or employee code (`"CS001"`). The resolver queries the local database to find the exact matching `faculty.id` UUID. If no match is found, the query is rejected before calling the solver.
2. **Temporal Grounding:** All date calculations are anchored to the fixed benchmark date `DEMO_TODAY = 2026-10-26`. The resolver deterministically parses:
   - Relative phrases: `"next week Mon to Wed"` $\rightarrow$ `2026-11-02` to `2026-11-04`.
   - ISO dates: `"2026-11-02 to 2026-11-04"`.
   - Explicit weekday references: `"this Monday"`, `"next Tuesday"`.

---

## 4. Grounded Explanation Generation

When generating the natural-language operational briefing, the LLM receives the **independently verified results** from OR-Tools CP-SAT and the Critic:

### Grounding Inputs Provided to LLM:
- Solver status (`OPTIMAL`, `FEASIBLE`, `INFEASIBLE`)
- Coverage percentage (e.g., `100.0%` or `66.7%`)
- Number of affected classes and number of resolved classes
- Exact proposed faculty substitutions with section names and period slots
- Critic verification verdict (`approved` with 0 new hard violations)
- Workload shifts (e.g., `Dr. Priya Nair: +3.0 hrs (current: 12.0/16.0)`)
- Structured candidate rejection counts (e.g., `4 rejected: ON_LEAVE, MISSING_EXPERTISE`)

### Hallucination Prevention
Because the prompt injects these verified facts as strict ground-truth constraints, the LLM cannot hallucinate:
- It cannot claim an uncovered class was covered.
- It cannot invent substitute instructors not present in the CP-SAT plan.
- It cannot claim Critic approval if the Critic rejected the plan.

---

## 5. Deterministic Grounded Fallback Provider

Campus OS guarantees full functional capability even when internet access is unavailable or no Groq API key is configured.

### 5.1. Deterministic Intent Parser (`DeterministicFallbackProvider.parse_intent`)
- Employs regex pattern matching to extract faculty names, employee codes (`CS\d{3}`, `EC\d{3}`, `ME\d{3}`), and date ranges.
- Correctly resolves Hero Scenario queries like:
  - `"Dr. Raj Sharma is on leave next week Monday to Wednesday"`
  - `"Find replacement for CS001 from 2026-11-02 to 2026-11-04"`
  - `"Show conflicts in CS department"`

### 5.2. Deterministic Explanation Generator (`DeterministicFallbackProvider.generate_explanation`)
- Formats structured solver statistics into a clean, professional Markdown report.
- Includes Critic verification badges, replacement schedules, workload deltas, and candidate rejection breakdowns.
- Tags output with `provider: "deterministic_fallback"` for complete administrative transparency.

---

## 6. Security & Departmental Authorization

Natural language queries sent to `POST /query` strictly adhere to the system's role-based security boundaries:
- **Principal:** Can query any faculty member across Computer Science, Electronics, and Mechanical Engineering.
- **HOD:** Queries are restricted to faculty in the HOD's own department.
- **Cross-Department Enforcement:** If an HOD for Electronics submits:  
  `"Dr. Raj Sharma is on leave next week Mon to Wed"` (CS faculty),  
  the endpoint halts execution and returns `HTTP 403 Forbidden` (`HOD can only access faculty in their own department`).

