# ANVIL — FINAL MASTER BUILD PROMPT
## Multi-Agent Decision Support System for College Operations

You are a senior software architect, backend engineer, optimization engineer, AI engineer, security reviewer, and frontend developer working together to build **ANVIL**, a reliable, explainable, multi-agent decision-support platform for college operations.

Your goal is to build a technically credible, fully working prototype that demonstrates genuine engineering depth. This is not a chatbot wrapper, a collection of dashboards, or an AI-generated recommendation demo. Its core capability is to understand operational changes, simulate their effects, generate feasible alternatives, detect conflicts, validate recommendations independently, and explain decisions using traceable evidence.

**Priorities, in order: correctness, feasibility, implementability, engineering depth, explainability, security, demonstrability, and visual polish.** Do not sacrifice correctness to make the system appear more intelligent.

---

# 1. NON-NEGOTIABLE DEVELOPMENT RULES

1. Inspect the existing repository, environment, and project instructions before making changes.
2. Treat `SPEC.md`, if present, as the primary project specification. Identify contradictions between it and this prompt rather than silently replacing important decisions.
3. Work in small, verifiable milestones. Do not attempt to generate the entire system in one enormous, untested implementation.
4. **Start with Phase M0 only. Do not modify, create, overwrite, or delete project files during M0.** Inspect the repository and report your proposed implementation plan. Wait for explicit approval before proceeding.
5. After approval, implement one milestone at a time. Run the relevant tests and report the actual results before moving forward.
6. Never claim that code, files, tests, APIs, integrations, or features exist or work unless you have verified them.
7. Never silently replace a real implementation with a mock, placeholder, hardcoded result, or fabricated success message.
8. Use deterministic algorithms for authoritative decisions. An LLM must never independently determine timetable feasibility, calculate workload, override hard constraints, or certify a plan as valid.
9. Make the system usable with no LLM API key. LLM-dependent features must have deterministic fallbacks.
10. Do not expose secrets in frontend code, logs, Git history, API responses, or screenshots.
11. Keep the prototype achievable for one student with limited hardware, limited budget, and approximately 10–15 hours of work per week.
12. Prefer a smaller, complete, tested system over a larger system containing unfinished modules.
13. Document assumptions, known limitations, incomplete features, and deferred functionality honestly.
14. Never invent evidence, evaluation metrics, accuracy claims, performance improvements, or real-world deployments.
15. Before any destructive operation, explain the impact and obtain approval.

---

# 2. PRODUCT VISION

Campus OS helps college administrators answer operational questions such as:

- A faculty member is on leave next week. Which scheduled classes are affected?
- Which eligible faculty members could cover those classes?
- Can all affected classes be covered without creating new conflicts?
- Which alternative plan provides the best workload balance?
- What happens if a room, faculty member, or scheduled period becomes unavailable?
- Why was a candidate accepted or rejected?
- What constraints prevent a fully feasible solution?
- Which operational conflicts already exist in the data?
- What changed between the original schedule and a proposed alternative?

The prototype's principal demonstration is:

> "Professor X is on leave from Monday through Wednesday next week. Identify every affected class, generate feasible replacement plans, explain the trade-offs, show what changes and what stays unchanged, and record the decision with its evidence."

This must be a genuine end-to-end workflow powered by real application data, deterministic rules, and an optimization engine—not a scripted response.

## Product boundaries

The first version is a decision-support prototype, not a production college ERP.

It must not automatically modify an institution's real timetable, send real notifications, or claim integration with external college systems.

A proposed plan is a simulation until an authorized user explicitly records a decision. Recording a decision in the audit system must not silently change operational timetable data.

---

# 3. TECHNICAL STACK

Use the following stack unless repository constraints make a change necessary. Explain any proposed deviation before implementation.

## Backend

- Python 3.11 or a compatible supported version
- FastAPI
- Pydantic for request/response validation
- SQLAlchemy 2.x
- Alembic for database migrations
- PostgreSQL
- Google OR-Tools CP-SAT for constrained assignment optimization
- Pytest for automated testing
- HTTPX for API tests

## Frontend

- React
- TypeScript
- Vite
- Tailwind CSS
- A small, maintainable component structure
- A suitable charting library only where visualizations materially improve understanding

## AI

- Groq API as the initial hosted LLM provider
- A provider-independent LLM interface
- A deterministic no-LLM fallback
- Pydantic-validated structured outputs

Use the current official Groq documentation to verify model availability, request format, limits, and configuration at implementation time. Do not hardcode an assumed model as permanently available.

## Infrastructure

- Docker Compose for local development
- PostgreSQL as the primary database
- `.env` for local secrets
- `.env.example` containing placeholders only
- Redis is not required
- pgvector is deferred until document retrieval is implemented

Avoid unnecessary microservices, Kubernetes, cloud infrastructure, paid APIs beyond the selected LLM provider, and heavyweight dependencies.

---

# 4. HIGH-LEVEL ARCHITECTURE

Build a modular monolith with clearly separated responsibilities.

The architecture should follow this logical flow:

**Frontend → FastAPI → Authentication and Authorization → Request Interpretation → Context Builder → Candidate Generator / CP-SAT Planner → Deterministic Rule Validator → Scorer → Independent Critic → Explanation Generator → Audit Recorder**

PostgreSQL stores operational data and audit records. Groq interprets natural-language requests and helps express verified results in readable language. The optimization and validation layers remain deterministic.

## Domain modules

Implement these as Python modules with explicit interfaces, not as independent LLM agents:

- Faculty operations
- Timetable operations
- Infrastructure and room availability
- Examination operations, deferred until the core workflow works
- Placement operations, deferred
- Communication and notices, deferred
- Orchestration and request interpretation

Do not create a separate LLM call for every domain module. Use ordinary Python services and typed functions. Introduce LLM tool selection only where it adds demonstrable value.

## Decision pipeline

Implement these responsibilities separately:

1. **Request Interpreter:** Converts a natural-language question into a validated intent.
2. **Context Builder:** Resolves entity IDs, dates, assignments, constraints, and relevant data.
3. **Candidate Generator:** Produces eligible replacement candidates and records rejection reasons.
4. **Planner:** Finds feasible joint assignments using CP-SAT.
5. **Scorer:** Ranks valid plans using documented soft preferences.
6. **Critic:** Independently reruns hard-constraint validation and checks the consistency of the recommendation.
7. **Simulator:** Computes the proposed before-and-after state without modifying operational records.
8. **Explanation Generator:** Produces an evidence-grounded explanation.
9. **Audit Recorder:** Stores the request, plan, validation results, evidence references, user, timestamp, and decision status.

The Critic must not simply trust the planner's own `valid=true` result. It must independently validate the resulting assignments.

---

# 5. DATA MODEL AND TEMPORAL CORRECTNESS

Design a normalized relational schema with stable IDs, foreign keys, explicit relationships, and migrations.

At minimum, consider these entities:

- Department
- User
- Faculty
- FacultyExpertise
- FacultyLeave
- Course
- CourseTag
- Section
- Room
- Period
- TimetableEntry
- Decision
- DecisionEvidence

Add entities only when required by an implemented feature.

Every important entity should have a stable identifier. Avoid relying on faculty names or course names as unique keys.

## Essential distinction: recurring schedules versus dated occurrences

A weekly timetable template and a specific class occurrence are not interchangeable.

Represent the recurring timetable separately from the dated occurrence being simulated. This can be implemented with a template plus generated occurrences, or another explicit and tested design.

A faculty leave record applies to the relevant dates within its defined inclusive date range. A replacement applies to a particular dated occurrence, not automatically to every future recurrence of that class.

Document the date and timezone assumptions. Use a consistent representation for period start/end times.

## Synthetic dataset

Generate reproducible, realistic synthetic data, including:

- Three departments
- Approximately 30 faculty members
- Approximately 40 courses
- Approximately 12 sections
- Approximately 15 rooms and labs
- A weekly timetable with deliberately planted conflicts
- Faculty expertise, workload limits, availability, and leave records
- Enough dated class occurrences to demonstrate the hero scenario

These counts are targets, not reasons to compromise data integrity.

Create deterministic seed scripts so the same seed data can be reproduced. Clearly label all synthetic data as synthetic.

Seed a small set of demo users representing Principal, HOD, and Exam Cell roles.

Do not put critical demo logic into hardcoded frontend arrays. The application must retrieve operational data through the backend.

---

# 6. DETERMINISTIC RULE ENGINE

Create a central rule engine with typed, structured outputs.

Every rule check must return enough information to identify the rule, severity, affected entities, explanation, and evidence.

For example, a violation should conceptually contain:

- `rule_id`
- `severity`
- `message`
- `affected_entity_ids`
- `evidence_refs`
- `details`

Use appropriate Pydantic models rather than unstructured dictionaries where practical.

## Initial hard constraints

Implement and test:

1. A faculty member cannot be assigned to overlapping classes.
2. A room cannot host overlapping classes.
3. A faculty member cannot be assigned during applicable leave.
4. Room capacity must satisfy class enrollment requirements.
5. Lab sessions must use suitable rooms.
6. Faculty expertise or qualification requirements must be respected where the course has an explicit requirement.
7. Faculty workload must not exceed the configured hard limit.
8. Invalid references, dates, assignments, and entity IDs must be rejected.
9. A proposed plan must not introduce new hard violations.
10. A simulation must not modify operational timetable records.

If a workload or qualification limit is not available in the data, do not invent one silently. Define and document the assumption, or report that validation is incomplete.

## Soft preferences

Use transparent, configurable preferences such as:

- Better subject expertise
- Workload balance
- Continuity of teaching
- Same-department preference

Distinguish hard constraints from soft preferences in both code and UI.

Existing conflicts must be reported. Do not disguise an existing conflict as newly introduced, and do not allow an existing conflict to excuse a new violation.

Compare baseline and proposed states using stable identifiers and explicit violation signatures. Report:

- Existing violations
- Resolved violations
- Newly introduced violations
- Remaining violations

A valid proposed plan must introduce zero new hard violations. If the baseline already contains conflicts, state that explicitly.

---

# 7. JOINT OPTIMIZATION ENGINE

Use Google OR-Tools CP-SAT to solve the faculty replacement problem jointly.

A greedy algorithm may be implemented as a baseline for evaluation, but it must not be the sole planner.

## Candidate eligibility

For every affected class, determine which faculty members are eligible.

Reject candidates who violate relevant hard constraints, such as:

- Being on leave on the relevant date
- Having an overlapping assignment
- Exceeding the applicable workload limit
- Lacking required qualification or expertise
- Being unavailable for the relevant period

Store structured rejection reasons so users can see why candidates were excluded.

Do not silently drop a class for which no candidate exists. Return an explicit uncovered assignment and explain why no feasible candidate was found.

## Optimization variables

For affected occurrence \(i\) and eligible candidate \(j\), define a Boolean assignment variable:

\[
x_{ij} =
\begin{cases}
1 & \text{if candidate }j\text{ covers occurrence }i\\
0 & \text{otherwise}
\end{cases}
\]

For each occurrence:

\[
\sum_j x_{ij} \leq 1
\]

For two overlapping occurrences that would assign the same faculty member, enforce:

\[
x_{ij} + x_{kj} \leq 1
\]

Add constraints for applicable workload, availability, and other modeled hard rules.

Make the exact mathematical model match the implemented business rules. Document any rules that are not yet modeled by CP-SAT and ensure the independent validator still checks them.

## Optimization priorities

Prioritize objectives lexicographically where possible:

1. Maximize the number of affected classes covered.
2. Among plans with equivalent coverage, optimize the documented soft preferences.
3. Prefer plans that introduce no hard violations—any plan that introduces a new hard violation must be rejected regardless of score.

Do not allow a high soft-preference score to compensate for lower coverage if coverage has been defined as the higher-priority objective.

If complete coverage is impossible, return the best feasible partial plan with uncovered occurrences and a clear explanation. Never label a partial plan as complete.

## Scoring

Begin with transparent, configurable demo weights, for example:

- Subject expertise: 35%
- Workload balance: 30%
- Teaching continuity: 25%
- Same department: 10%

These are initial prototype assumptions, not scientifically established weights.

Normalize scores to a documented scale. Explain each criterion and show the contribution of each criterion to the final score.

Ensure that the displayed score matches the objective or ranking logic actually implemented. Do not fabricate numerical scores or describe a score as a probability of success.

## Alternatives

Return up to three genuinely distinct feasible plans when available.

Each alternative must be independently validated. Do not duplicate the same plan under different labels. If only one feasible plan exists, return one. If no feasible plan exists, explain why.

Record solver status, runtime, objective information, and uncovered assignments where relevant.

---

# 8. WHAT-IF SIMULATION

Implement the simulation as a non-mutating operation.

Workflow:

1. Receive a validated scenario.
2. Resolve the affected dated occurrences.
3. Build the baseline state.
4. Calculate baseline conflicts and violations.
5. Apply proposed changes to an isolated in-memory representation.
6. Generate candidate assignments.
7. Solve the joint assignment problem.
8. Independently validate each proposed plan.
9. Calculate before-and-after differences.
10. Generate an explanation based on verified outputs.
11. Return the simulation result.
12. Record the simulation and its evidence in the audit system, without altering operational timetable data.

Test explicitly that simulation does not write proposed assignments into operational timetable records.

The output must include:

- Scenario summary
- Affected classes
- Original faculty assignments
- Proposed assignments
- Uncovered classes
- Baseline conflicts
- Resolved conflicts
- Newly introduced conflicts
- Remaining conflicts
- Score breakdown
- Alternatives
- Critic results
- Evidence references
- Limitations and incomplete data warnings

Do not implement automatic room or class rescheduling in the first version. The first version reassigns faculty to specific dated class occurrences only.

---

# 9. INDEPENDENT CRITIC AND TRUSTWORTHINESS

The Critic is a deterministic validation stage, not an additional LLM that merely agrees with the planner.

It must:

- Revalidate every proposed assignment.
- Detect overlapping assignments.
- Check applicable leave and availability.
- Check workload limits.
- Check relevant qualification and room constraints.
- Compare baseline and proposed violations.
- Verify that claimed improvements are supported by computed results.
- Verify that every recommendation refers to existing entities.
- Detect incomplete coverage.
- Flag missing or contradictory input data.
- Reject any plan that introduces a new hard violation.

The Critic must return structured results and specific issue codes.

The system must distinguish:

- `feasible_complete`
- `feasible_partial`
- `infeasible`
- `validation_failed`
- `insufficient_data`

Use an enum or equivalent validated type. Do not reduce all states to a Boolean.

If the solver times out, errors, or returns an unknown status, do not report a fully validated optimum. Preserve the actual solver status and return only a plan that has passed independent validation.

---

# 10. GROQ API INTEGRATION

Integrate Groq as a language interface, not as the authority for operational decisions.

Keep the provider replaceable through a small interface, such as:

- `parse_intent(text) -> Intent`
- `explain(compact_verified_summary) -> str`

Use typed, validated request and response schemas.

## Allowed LLM responsibilities

- Interpret a natural-language question.
- Identify the requested operation.
- Extract proposed scenario parameters.
- Ask for missing information.
- Help select from explicitly permitted backend tools.
- Explain already-computed recommendations in readable language.

## Prohibited LLM responsibilities

- Determine whether an assignment is feasible.
- Perform authoritative workload calculations.
- Override hard constraints.
- Invent faculty, courses, dates, conflicts, or evidence.
- Decide that the Critic passed.
- Write directly to operational tables.
- Make unauthorized tool calls.
- Claim that an optimization is complete without verified solver results.

The backend must resolve entity references and validate dates, permissions, tool arguments, and scenario parameters independently of the LLM.

## Provider interface and fallback

Implement a provider-independent interface and a deterministic fallback.

The application must remain usable without a Groq API key. In fallback mode, support a documented subset of common commands through simple parsing or structured form inputs. Clearly indicate when fallback interpretation is being used.

If Groq is unavailable, rate-limited, times out, returns malformed structured output, or fails validation:

1. Handle the error safely.
2. Apply bounded retries only where appropriate.
3. Do not trust malformed output.
4. Use the deterministic fallback when possible.
5. Ask the user to clarify when the request cannot be safely interpreted.
6. Never fabricate an answer to hide an LLM failure.

Keep the API key on the backend. Never place it in frontend environment variables that are exposed to the browser.

Use environment variables such as:

`GROQ_API_KEY=your_key_here`

`GROQ_MODEL=your_verified_supported_model`

`LLM_PROVIDER=groq`

`DATABASE_URL=your_local_database_url`

`DEMO_TODAY=2026-10-26`

The `DEMO_TODAY` value is an example for reproducible tests only. Production-like behavior must use a clearly defined current-date strategy, and tests must be able to inject a fixed date.

Do not commit `.env`. Add it to `.gitignore`.

Avoid sending unnecessary personal or institutional data to the LLM. Log provider status and model metadata where appropriate, but never log secrets.

---

# 11. RECOMMENDATION AND AUDIT SCHEMAS

Create explicit schemas for the request, simulation, candidate, plan, critic result, evidence, and audit record.

A recommendation should conceptually contain:

- `decision_id`
- `scenario`
- `affected_occurrences`
- `baseline_violations`
- `alternatives`
- `selected_plan`
- `coverage_summary`
- `score_breakdown`
- `critic_result`
- `evidence_refs`
- `limitations`
- `solver_status`
- `llm_status`
- `created_at`
- `created_by`
- `decision_status`

Each plan should include:

- Proposed assignments
- Uncovered occurrences
- Coverage count
- Score breakdown
- Hard-constraint results
- Independent validation status
- Rejection reasons where applicable

Audit states should distinguish simulation from a human decision. Recording a selected recommendation must not automatically apply it to operational timetable data.

Persist enough information to reproduce or inspect the reasoning behind a past recommendation. Avoid storing secrets or unnecessary sensitive information.

---

# 12. AUTHENTICATION AND AUTHORIZATION

Implement basic but real backend authorization for the demo.

Roles:

- Principal: institution-wide read access to supported operations
- HOD: access restricted to the relevant department
- Exam Cell: access to supported examination functionality

Enforce permissions on the backend for every protected endpoint. Frontend role selection is not an authorization mechanism.

Test cross-department access explicitly.

Use a simple, documented authentication approach suitable for a local prototype. Do not invent a production security guarantee. Never trust a role, department, or user ID supplied by an untrusted client without validating it against the authenticated identity.

Protect document uploads and request bodies with reasonable size and type limits when those features are implemented. Validate inputs, handle errors safely, and avoid returning stack traces or secrets to clients.

---

# 13. API CONTRACT

Implement the following endpoints as appropriate to the completed milestone:

- `GET /health`
- `GET /dashboard`
- `GET /conflicts`
- `GET /workload`
- `POST /query`
- `POST /whatif`
- `GET /decisions`
- `GET /decisions/{decision_id}`

Defer these until the core workflow is stable:

- `POST /exam/invigilation/generate`
- `POST /documents/upload`
- Document retrieval and question answering

Use consistent HTTP status codes, validated request and response models, clear error messages, and pagination where appropriate.

Do not expose database internals or return arbitrary ORM objects directly.

Document the endpoints using FastAPI's OpenAPI support.

---

# 14. FRONTEND EXPERIENCE

Build a polished, professional, responsive dashboard suitable for a college management demonstration.

Prioritize clarity and evidence over decorative complexity. Use real API data and explicit loading, empty, error, and partial-result states.

## Screen 1: Operations Dashboard

Show:

- Total scheduled classes
- Faculty availability
- Current detected conflicts
- Workload distribution
- Recent simulations and decisions
- Alerts with links to supporting details

Metrics must be calculated from actual backend data.

## Screen 2: Ask / What-if Simulator

Allow users to submit natural-language questions and also use structured controls.

For the hero scenario, show:

- Faculty member and leave dates
- Affected classes
- Ranked feasible plans
- Proposed replacement for each class
- Workload changes
- Score breakdown
- Uncovered classes
- Before-and-after conflicts
- Critic validation status
- Evidence and limitations

Let the user compare alternatives. Never display an unvalidated plan as a recommended valid plan.

## Screen 3: Decision Detail

Show the complete reasoning trace:

- Original scenario
- Relevant constraints
- Candidate eligibility and rejection reasons
- Solver result
- Alternatives and scores
- Critic checks
- Evidence
- Before-and-after comparison
- Audit status

## Screen 4: Audit Log

Show previous simulations and recorded decisions, including:

- Timestamp
- User
- Scenario
- Result status
- Coverage
- Critic status
- LLM/provider status

Clearly distinguish a simulation from a human-approved decision. Do not imply that approval changed the live timetable.

---

# 15. EVIDENCE AND DOCUMENT RETRIEVAL — DEFERRED

Do not let document retrieval delay the core decision engine.

After the core workflow is working, add a limited document feature for PDF, CSV, and Excel files.

For PDFs, preserve page numbers where possible. For structured files, preserve sheet names and row/column provenance where possible.

If semantic search is implemented, use pgvector only when justified and keep the embedding model configurable. A local embedding model may be used if it works within available hardware constraints.

Every retrieved statement must include a traceable source reference, such as document name, page, section, sheet, or row.

If the evidence is missing, irrelevant, or insufficient, say so. Do not invent a citation.

Document question answering must not be allowed to modify operational data or override deterministic rules.

OCR, image-heavy documents, external ERP integrations, email, calendars, biometric systems, SMS, and WhatsApp are outside the initial scope.

---

# 16. TESTING STRATEGY

Testing is a core deliverable, not an optional final step.

## Unit tests

Test each hard rule independently, including:

- Overlapping faculty assignments
- Room conflicts
- Leave-date boundaries
- Workload limits
- Room capacity
- Lab suitability
- Required expertise
- Missing and invalid references
- Existing versus newly introduced violations

Include both positive and negative cases.

## Planner tests

Test:

- Complete feasible coverage
- Partial coverage
- No eligible candidates
- Multiple simultaneous affected classes
- Overlapping candidate availability
- Workload constraints
- Solver timeout or non-optimal statuses
- Duplicate plan prevention
- Score calculation
- Independent validation of returned plans

## Simulation tests

Verify that:

- Baseline and proposed states are compared correctly.
- The simulation does not mutate operational timetable data.
- Existing violations are not misclassified as new.
- New hard violations cause rejection.
- Partial plans are clearly marked.
- Evidence refers to valid entities.

## API and security tests

Test:

- Request validation
- Invalid entity IDs
- Unauthorized access
- Cross-department access
- Missing or malformed authentication
- Error handling
- No leakage of secrets
- LLM failures and fallback behavior

## Reproducible evaluation

Create an evaluation script with at least 50 deterministic synthetic leave scenarios where feasible.

Compare the CP-SAT planner with a simple greedy baseline. Report actual measured results, including:

- Number of scenarios evaluated
- Affected classes
- Coverage rate
- Fully covered scenarios
- Uncovered assignments
- New hard violations
- Workload distribution
- Solver runtime
- Number of valid alternatives returned

Do not assume CP-SAT always outperforms greedy on every metric. Report the measured findings, dataset assumptions, and limitations.

A key safety target is **zero newly introduced hard violations among plans that the system labels as independently validated**. Any failure must be investigated and fixed before claiming the target has been met.

---

# 17. IMPLEMENTATION MILESTONES

Implement the system in the following order.

## M0 — Repository inspection and design approval (Completed)

Read the existing project files and instructions. Inspect the environment and available tools.

Do not create, edit, overwrite, or delete files.

Return:

- Your understanding of Campus OS
- Current repository state
- Proposed architecture
- Folder structure
- Database schema
- Temporal data model
- Hard and soft constraints
- CP-SAT formulation
- Independent validation design
- Groq interface and fallback
- Security approach
- Milestone plan
- Main risks and unresolved decisions
- Exact commands and dependencies you expect to use

Identify contradictions or missing requirements. Do not silently decide major unresolved matters.

**Stop after M0 and wait for explicit approval.**

## M1 — Foundation and data (Completed)

After approval:

- Create the backend and frontend scaffolding.
- Set up Docker Compose and PostgreSQL.
- Configure migrations.
- Implement the initial data model.
- Add reproducible synthetic data.
- Implement health checks and dashboard data endpoints.
- Add basic tests.

Acceptance: a fresh local setup starts successfully and exposes seeded data through the backend.

## M2 — Rules engine (Completed)

Implement the deterministic rule engine, structured violations, baseline conflict detection, and tests.

Acceptance: planted conflicts are detected, clean fixtures produce no unexpected violations, and rule results include evidence.

## M3 — Candidate generation and optimization (Completed)

Implement candidate eligibility, rejection reasons, CP-SAT planning, workload balancing, score breakdown, and a greedy baseline for comparison.

Acceptance: feasible, partial, and infeasible scenarios are distinguished correctly, and returned plans pass independent validation.

## M4 — Simulation, Critic, and audit (Completed)

Implement the non-mutating what-if pipeline, independent Critic, before-and-after comparison, recommendation schemas, and audit persistence.

Acceptance: the hero scenario works end to end, no operational timetable mutation occurs, and newly introduced hard violations are rejected.

**Cutline A:** at this point, the deterministic decision engine must work without an LLM.

## M5 — API, authentication, and frontend (Completed)

Implement the supported API contracts, backend role enforcement, the four core screens, and real API integration.

Acceptance: a user can submit a scenario, compare alternatives, inspect validation evidence, and view its audit record.

**Cutline B:** at this point, a demonstrable prototype must work without Groq.

## M6 — Groq integration (Completed)

Implement intent parsing, structured output validation, readable explanations, timeouts, bounded retries, error handling, and deterministic fallback.

Acceptance: the same supported scenario can be submitted in natural language or through structured controls. LLM failure must not compromise decision correctness.

## M7 — Evaluation and hardening (Completed)

Run the test suite and evaluation harness. Fix correctness and security problems. Review frontend/backend consistency, database migrations, and reproducibility.

Acceptance: the evaluation results are generated from actual runs, and known failures are documented.

## M8 — Final delivery and demonstration (Completed)

Prepare:

- Clear README
- Installation instructions
- Environment configuration guide
- Architecture diagram
- Database/data dictionary
- API documentation
- Test instructions
- Evaluation methodology and results
- Known limitations
- Screenshots
- A five-minute demo script
- A list of implemented, incomplete, and deferred features

Do not claim production readiness.

---

# 18. REQUIRED FOLDER STRUCTURE

Use this as the target structure, adapting only where there is a clear technical reason:

```text
campus-os/
├── SPEC.md
├── README.md
├── docker-compose.yml
├── .env.example
├── .gitignore
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── dashboard.py
│   │   │   ├── query.py
│   │   │   ├── whatif.py
│   │   │   └── decisions.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   └── permissions.py
│   │   ├── db/
│   │   │   ├── models.py
│   │   │   ├── session.py
│   │   │   └── seed.py
│   │   ├── schemas/
│   │   ├── services/
│   │   │   ├── faculty.py
│   │   │   ├── timetable.py
│   │   │   └── infrastructure.py
│   │   ├── engine/
│   │   │   ├── context.py
│   │   │   ├── rules.py
│   │   │   ├── candidates.py
│   │   │   ├── planner.py
│   │   │   ├── scoring.py
│   │   │   ├── simulation.py
│   │   │   ├── critic.py
│   │   │   └── recommendation.py
│   │   ├── llm/
│   │   │   ├── interface.py
│   │   │   ├── groq_client.py
│   │   │   └── fallback.py
│   │   └── audit/
│   │       └── recorder.py
│   └── tests/
│       ├── test_rules.py
│       ├── test_planner.py
│       ├── test_simulation.py
│       ├── test_critic.py
│       ├── test_api.py
│       └── test_security.py
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   └── src/
│       ├── components/
│       ├── pages/
│       ├── api/
│       └── types/
├── scripts/
│   └── evaluate.py
└── docs/
    ├── ARCHITECTURE.md
    ├── DATA.md
    ├── LLM.md
    └── EVALUATION.md
```

Do not create empty files merely to match this tree. Add modules when they contain meaningful implementation.

---

# 19. FINAL ACCEPTANCE CRITERIA

The project is considered demonstrable only when all applicable criteria below are verified:

1. A fresh local setup can be started using documented instructions.
2. PostgreSQL contains reproducible synthetic operational data.
3. The dashboard displays backend-derived values.
4. Planted conflicts are detected by deterministic rules.
5. The hero leave scenario identifies the affected dated classes correctly.
6. Candidate eligibility and rejection reasons are inspectable.
7. The CP-SAT planner generates valid joint assignments when feasible.
8. Partial and infeasible scenarios are represented honestly.
9. Returned alternatives are distinct and independently validated.
10. The system distinguishes pre-existing violations from newly introduced ones.
11. No plan labeled independently validated introduces a new hard violation.
12. Simulation does not mutate operational timetable records.
13. The Critic independently verifies proposed plans.
14. Users can inspect the score breakdown and supporting evidence.
15. Audit records distinguish simulation from human decisions.
16. Backend authorization prevents unauthorized cross-department access.
17. Natural-language interpretation works through Groq when configured.
18. The documented deterministic fallback works without Groq.
19. LLM failures do not bypass rules or fabricate successful results.
20. Automated tests and the evaluation script run with documented results.
21. The README explains setup, architecture, assumptions, limitations, and demo steps.
22. The final report explicitly identifies anything incomplete or deferred.

Never mark a criterion complete based only on code inspection if execution is required to verify it.

---

# 20. HOW YOU MUST REPORT PROGRESS

At the end of each milestone, provide:

- **Implemented:** specific functionality completed
- **Files changed:** actual file paths
- **Commands run:** actual commands
- **Tests:** passed, failed, skipped, and not run
- **Evidence:** relevant test output or reproducible verification
- **Known issues:** unresolved problems
- **Security considerations:** any remaining concerns
- **Next milestone:** what you propose to do next

Do not advance to the next milestone without approval when the milestone changes significant architecture, expands scope, or exposes unresolved correctness issues.

If a test fails, diagnose and fix the failure before claiming success. If you cannot run a command or test, say so explicitly.

# FIRST ACTION

**Begin with M0 only.**

Inspect the existing repository and project instructions. Do not modify any files yet. Return a concise but technically detailed implementation plan, including your proposed data model, temporal modeling, constraints, CP-SAT formulation, Critic, Groq integration, security model, milestone acceptance criteria, and risks.

Clearly identify unresolved decisions and explain the trade-offs.

Then stop and wait for my explicit approval before writing or changing any project files.

The goal is not to produce the most code as quickly as possible. The goal is to build a correct, explainable, tested, and technically defensible Campus OS prototype that can withstand a live demonstration and detailed engineering questions.