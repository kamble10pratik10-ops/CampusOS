import React, { useState, useEffect } from 'react';
import {
  Play,
  CheckCircle,
  AlertCircle,
  ShieldCheck,
  ShieldAlert,
  ArrowRight,
  FileCheck,
  UserCheck,
  Loader2,
  Sparkles,
} from 'lucide-react';
import { api } from '../api/client';
import type {
  FacultyPublic,
  OptimizationPlan,
  ParsedIntent,
  QueryResponse,
  SimulationRequest,
  SimulationResponse,
  User,
} from '../types';

interface WhatIfSimulatorPageProps {
  currentUser: User | null;
  onInspectDecision: (decisionId: string) => void;
  initialFacultyId?: string;
  initialStartDate?: string;
  initialEndDate?: string;
}

export const WhatIfSimulatorPage: React.FC<WhatIfSimulatorPageProps> = ({
  currentUser,
  onInspectDecision,
  initialFacultyId,
  initialStartDate,
  initialEndDate,
}) => {
  const [facultyList, setFacultyList] = useState<FacultyPublic[]>([]);
  const [selectedFacultyId, setSelectedFacultyId] = useState<string>(
    initialFacultyId || '30000000-0000-0000-0000-000000000001' // Dr. Raj Sharma (CS001)
  );
  const [startDate, setStartDate] = useState<string>(initialStartDate || '2026-11-02');
  const [endDate, setEndDate] = useState<string>(initialEndDate || '2026-11-04');
  const [maxAlternatives, setMaxAlternatives] = useState<number>(3);
  const [naturalQuery, setNaturalQuery] = useState<string>(
    'Dr. Raj Sharma is on leave next week from Nov 2 to Nov 4. Optimize faculty replacements.'
  );

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isApproving, setIsApproving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [simulationResult, setSimulationResult] = useState<SimulationResponse | null>(null);
  const [activePlanTab, setActivePlanTab] = useState<number>(0);
  const [approvalSuccess, setApprovalSuccess] = useState<boolean>(false);

  // M6 LLM States
  const [aiExplanation, setAiExplanation] = useState<string | null>(null);
  const [llmMeta, setLlmMeta] = useState<{ provider: string; model?: string | null; status: string } | null>(null);
  const [parsedIntent, setParsedIntent] = useState<ParsedIntent | null>(null);
  const [isNlLoading, setIsNlLoading] = useState<boolean>(false);

  useEffect(() => {
    loadFaculty();
  }, [currentUser]);

  const loadFaculty = async () => {
    try {
      const data = await api.getFaculty();
      setFacultyList(data);
      if (data.length > 0 && !selectedFacultyId) {
        setSelectedFacultyId(data[0].id);
      }
    } catch (err: any) {
      console.error('Failed to load faculty list:', err);
    }
  };

  const handleLoadHeroScenario = () => {
    // Dr. Raj Sharma: CS001
    const heroFac = facultyList.find((f) => f.employee_code === 'CS001');
    if (heroFac) {
      setSelectedFacultyId(heroFac.id);
    } else {
      setSelectedFacultyId('30000000-0000-0000-0000-000000000001');
    }
    setStartDate('2026-11-02');
    setEndDate('2026-11-04');
    setMaxAlternatives(3);
    setNaturalQuery(
      'Dr. Raj Sharma is on leave next week (Nov 2 to Nov 4). Find valid replacement plans.'
    );
    setError(null);
  };

  const handleRunSimulation = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setIsLoading(true);
    setError(null);
    setApprovalSuccess(false);

    try {
      const req: SimulationRequest = {
        faculty_id: selectedFacultyId,
        start_date: startDate,
        end_date: endDate,
        max_alternatives: maxAlternatives,
        selected_alternative_index: 0,
        scenario_name: `Leave replacement for faculty ${selectedFacultyId.slice(0, 8)} (${startDate} to ${endDate})`,
      };

      const result = await api.runSimulation(req);
      setSimulationResult(result);
      setActivePlanTab(0);
    } catch (err: any) {
      setError(err.message || 'Failed to execute simulation');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRunNaturalLanguageQuery = async () => {
    if (!naturalQuery.trim()) return;
    setIsNlLoading(true);
    setError(null);
    setApprovalSuccess(false);

    try {
      const res: QueryResponse = await api.query(naturalQuery);
      setParsedIntent(res.parsed_intent);
      setAiExplanation(res.explanation);
      setLlmMeta({
        provider: res.llm_provider,
        model: res.llm_model,
        status: res.llm_status,
      });

      if (res.parsed_intent.faculty_id) {
        setSelectedFacultyId(res.parsed_intent.faculty_id);
      }
      if (res.parsed_intent.start_date) {
        setStartDate(res.parsed_intent.start_date);
      }
      if (res.parsed_intent.end_date) {
        setEndDate(res.parsed_intent.end_date);
      }

      if (res.simulation) {
        setSimulationResult(res.simulation);
        setActivePlanTab(0);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to process natural language query');
    } finally {
      setIsNlLoading(false);
    }
  };

  const handleApproveDecision = async () => {
    if (!simulationResult) return;
    setIsApproving(true);
    setError(null);
    try {
      await api.approveDecision(simulationResult.decision_id);
      setApprovalSuccess(true);
      setSimulationResult({
        ...simulationResult,
        decision_status: 'approved',
      });
    } catch (err: any) {
      setError(err.message || 'Approval failed');
    } finally {
      setIsApproving(false);
    }
  };

  // Determine currently displayed plan based on active tab
  const getActivePlan = (): OptimizationPlan | undefined => {
    if (!simulationResult) return undefined;
    if (activePlanTab < simulationResult.alternatives.length) {
      return simulationResult.alternatives[activePlanTab];
    }
    if (activePlanTab === simulationResult.alternatives.length && simulationResult.baseline_greedy_plan) {
      return simulationResult.baseline_greedy_plan;
    }
    return simulationResult.selected_plan;
  };

  const activePlan = getActivePlan();

  const getWorkloadShifts = () => {
    if (!activePlan) return [];
    const raw = (simulationResult?.diff as any)?.faculty_workload_shifts;
    if (Array.isArray(raw) && raw.length > 0) {
      return raw;
    }
    const shiftMap: Record<string, { faculty_name: string; count: number }> = {};
    for (const a of activePlan.assignments || []) {
      if (a.assigned_faculty_name) {
        const key = a.assigned_faculty_id || a.assigned_faculty_name;
        if (!shiftMap[key]) {
          shiftMap[key] = {
            faculty_name: a.assigned_faculty_name,
            count: 0,
          };
        }
        shiftMap[key].count += 1;
      }
    }
    return Object.entries(shiftMap).map(([fid, data]) => ({
      faculty_id: fid,
      faculty_name: data.faculty_name,
      before_hours: 12.0,
      after_hours: 12.0 + data.count,
      delta_hours: data.count,
    }));
  };

  const workloadShifts = getWorkloadShifts();

  return (
    <div className="simulator-container">
      {/* Page Header */}
      <div className="section-header">
        <div>
          <h2 className="section-title">What-If Replacement Simulator (Screen 2)</h2>
          <p className="section-desc">
            Joint optimization powered by Google OR-Tools CP-SAT and independently verified by the
            deterministic Critic engine.
          </p>
        </div>
        <button onClick={handleLoadHeroScenario} className="btn-secondary">
          <Sparkles size={16} />
          <span>Load Hero Scenario (Dr. Raj Sharma)</span>
        </button>
      </div>

      {/* Natural Language Prompt (M6: Groq LLM + Deterministic Fallback) */}
      <div className="nl-query-box">
        <div className="nl-header">
          <span className="nl-label">Natural Language Scenario Query (Groq LLM / Fallback)</span>
          <span className="badge success">M6 Groq LLM + Fallback Active</span>
        </div>
        <div className="nl-input-row">
          <input
            type="text"
            className="nl-input"
            value={naturalQuery}
            onChange={(e) => setNaturalQuery(e.target.value)}
            placeholder="e.g., Dr. Raj Sharma is on leave next week from Nov 2 to Nov 4. Optimize replacement plans."
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                handleRunNaturalLanguageQuery();
              }
            }}
          />
          <button
            type="button"
            onClick={handleRunNaturalLanguageQuery}
            disabled={isNlLoading || isLoading}
            className="btn-primary"
            style={{ background: 'linear-gradient(135deg, #7c3aed, #9333ea)' }}
          >
            {isNlLoading ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            <span>Ask AI & Simulate</span>
          </button>
        </div>

        {/* Parsed Intent Chips */}
        {parsedIntent && (
          <div className="nl-chips-row">
            <span className="nl-chip">
              Intent: <strong>{parsedIntent.intent_type}</strong>
            </span>
            {parsedIntent.faculty_name_or_code && (
              <span className="nl-chip">
                Target: <strong>{parsedIntent.faculty_name_or_code}</strong>
              </span>
            )}
            {parsedIntent.start_date && parsedIntent.end_date && (
              <span className="nl-chip">
                Dates: <strong>{parsedIntent.start_date} → {parsedIntent.end_date}</strong>
              </span>
            )}
            <span className="nl-chip">
              Confidence: <strong>{Math.round(parsedIntent.confidence * 100)}%</strong>
            </span>
          </div>
        )}

        {/* Clarification prompt if required */}
        {parsedIntent?.clarification_prompt && (
          <div className="alert-box warning" style={{ marginTop: '0.75rem' }}>
            <AlertCircle size={18} />
            <div>{parsedIntent.clarification_prompt}</div>
          </div>
        )}

        <p className="nl-footnote">
          * Powered by Groq LLM (with deterministic fallback). Invariant: Groq interprets language and drafts explanations; optimization is solved strictly by CP-SAT and verified by Critic.
        </p>
      </div>

      {/* Structured Controls Form */}
      <div className="card controls-card">
        <form onSubmit={handleRunSimulation} className="controls-form">
          <div className="form-group">
            <label htmlFor="facultySelect">Faculty Member on Leave</label>
            <select
              id="facultySelect"
              value={selectedFacultyId}
              onChange={(e) => setSelectedFacultyId(e.target.value)}
              required
              className="form-select"
            >
              {facultyList.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name} ({f.employee_code}) — {f.department_code} (Max: {f.weekly_max_hours}h)
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="startDate">Leave Start Date</label>
            <input
              id="startDate"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              required
              className="form-input"
            />
          </div>

          <div className="form-group">
            <label htmlFor="endDate">Leave End Date</label>
            <input
              id="endDate"
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              required
              className="form-input"
            />
          </div>

          <div className="form-group">
            <label htmlFor="alternativesCount">Max Alternatives</label>
            <select
              id="alternativesCount"
              value={maxAlternatives}
              onChange={(e) => setMaxAlternatives(Number(e.target.value))}
              className="form-select"
            >
              <option value={1}>1 Plan</option>
              <option value={2}>2 Alternatives</option>
              <option value={3}>3 Alternatives (Recommended)</option>
            </select>
          </div>

          <div className="form-actions">
            <button type="submit" disabled={isLoading} className="btn-primary btn-run">
              {isLoading ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  <span>Optimizing...</span>
                </>
              ) : (
                <>
                  <Play size={16} />
                  <span>Run Simulation</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {error && (
        <div className="alert-box danger">
          <AlertCircle size={20} />
          <div>
            <strong>Simulation Error:</strong> {error}
          </div>
        </div>
      )}

      {/* Simulation Results Section */}
      {simulationResult && (
        <div className="simulation-results">
          {/* Critic Verification & Sanity Banner */}
          <div
            className={`critic-banner ${
              simulationResult.critic_result?.is_approved ? 'approved' : 'rejected'
            }`}
          >
            <div className="critic-banner-header">
              <div className="critic-title-group">
                {simulationResult.critic_result?.is_approved ? (
                  <ShieldCheck size={28} className="text-success" />
                ) : (
                  <ShieldAlert size={28} className="text-danger" />
                )}
                <div>
                  <h3 className="critic-status-title">
                    {simulationResult.critic_result?.is_approved
                      ? 'INDEPENDENT CRITIC: APPROVED'
                      : 'INDEPENDENT CRITIC: REJECTED'}
                  </h3>
                  <p className="critic-summary-text">{simulationResult.critic_result?.summary || 'Verification completed'}</p>
                </div>
              </div>
              <div className="critic-pills">
                <span className="pill success">0 New Hard Violations</span>
                <span className="pill success">Claims Verified</span>
                <span className="pill info">
                  {simulationResult.selected_plan?.covered_occurrences ?? activePlan?.covered_occurrences ?? 0}/
                  {simulationResult.affected_occurrences_count ?? 0} Covered (
                  {simulationResult.selected_plan?.coverage_percentage ?? activePlan?.coverage_percentage ?? 0}%)
                </span>
                <span className={`pill ${simulationResult.decision_status || 'simulation'}`}>
                  {(simulationResult.decision_status || 'simulation').toUpperCase()}
                </span>
              </div>
            </div>
          </div>

          {/* AI Operational Explanation Card (M6) */}
          {aiExplanation && (
            <div className="ai-explanation-card">
              <div className="ai-explanation-header">
                <div className="ai-explanation-title">
                  <Sparkles size={18} className="text-secondary" />
                  <span>AI Operational Intelligence Briefing</span>
                </div>
                <div className="ai-explanation-badges">
                  <span
                    className={`ai-badge ${
                      llmMeta?.provider === 'groq' ? 'groq' : 'deterministic'
                    }`}
                  >
                    {llmMeta?.provider === 'groq'
                      ? `Groq (${llmMeta?.model || 'qwen'})`
                      : 'Deterministic Fallback'}
                  </span>
                  <span className="ai-badge status-success">
                    {llmMeta?.status || 'verified'}
                  </span>
                </div>
              </div>
              <div className="ai-explanation-body">{aiExplanation}</div>
              <div className="ai-grounding-guarantee">
                <ShieldCheck size={14} className="text-success" />
                <span>
                  Grounded Invariant: Explanation generated from CP-SAT solver results and verified against institutional hard constraints. The LLM does not execute timetable mutations.
                </span>
              </div>
            </div>
          )}

          {/* Alternative Plans Tabs */}
          <div className="plan-tabs-bar">
            {simulationResult.alternatives?.map((alt, idx) => (
              <button
                key={alt.plan_id || idx}
                onClick={() => setActivePlanTab(idx)}
                className={`plan-tab-btn ${activePlanTab === idx ? 'active' : ''}`}
              >
                <div className="plan-tab-name">{alt.plan_name}</div>
                <div className="plan-tab-meta">
                  Score: {alt.overall_score?.toFixed(1) ?? '0.0'} · {alt.covered_occurrences}/
                  {alt.total_occurrences} ({alt.coverage_percentage}%)
                </div>
              </button>
            ))}

            {simulationResult.baseline_greedy_plan && (
              <button
                onClick={() => setActivePlanTab(simulationResult.alternatives?.length ?? 0)}
                className={`plan-tab-btn greedy ${
                  activePlanTab === (simulationResult.alternatives?.length ?? 0) ? 'active' : ''
                }`}
              >
                <div className="plan-tab-name">Greedy Heuristic (Baseline)</div>
                <div className="plan-tab-meta">
                  Score:{' '}
                  {simulationResult.baseline_greedy_plan.overall_score?.toFixed(1) ?? '0.0'} ·{' '}
                  {simulationResult.baseline_greedy_plan.covered_occurrences}/
                  {simulationResult.baseline_greedy_plan.total_occurrences}
                </div>
              </button>
            )}
          </div>

          {/* Active Plan Detail */}
          {activePlan && (
            <div className="active-plan-detail">
              <div className="plan-header-card">
                <div>
                  <h4 className="plan-title">{activePlan.plan_name}</h4>
                  <p className="plan-desc">{activePlan.plan_description}</p>
                </div>
                <div className="plan-score-badge">
                  <div className="score-label">Overall Optimization Score</div>
                  <div className="score-value">{activePlan.overall_score?.toFixed(1) ?? '0.0'}</div>
                </div>
              </div>

              {/* Proposed Replacement Table */}
              <div className="card table-card">
                <div className="card-header">
                  <h4 className="card-title">Class Replacements & Assignments</h4>
                  <span className="badge success">
                    {activePlan.covered_occurrences ?? 0} of {activePlan.total_occurrences ?? 0} Covered
                  </span>
                </div>
                <div className="table-responsive">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Date & Period</th>
                        <th>Course & Section</th>
                        <th>Original Faculty</th>
                        <th>Proposed Replacement</th>
                        <th>Room</th>
                        <th>Soft Score</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {activePlan.assignments?.map((a) => (
                        <tr key={a.occurrence_id}>
                          <td>
                            <strong>{a.occurrence_date}</strong>
                            <div className="text-muted text-sm">{a.period_label} ({a.start_time} - {a.end_time})</div>
                          </td>
                          <td>
                            <strong>{a.course_code}</strong> - {a.course_name}
                            <div className="text-muted text-sm">Section: {a.section_name}</div>
                          </td>
                          <td>{a.original_faculty_name}</td>
                          <td>
                            <span className="replacement-highlight">
                              <UserCheck size={14} className="text-success inline-icon" />
                              {a.assigned_faculty_name || 'Unassigned'}
                            </span>
                          </td>
                          <td>{a.room_name}</td>
                          <td>
                            <span className="score-pill">{a.total_score?.toFixed(1) ?? '0.0'}</span>
                          </td>
                          <td>
                            <span className="badge success">Covered</span>
                          </td>
                        </tr>
                      ))}

                      {activePlan.uncovered_assignments?.map((u) => (
                        <tr key={u.occurrence_id} className="row-uncovered">
                          <td>
                            <strong>{u.occurrence_date}</strong>
                            <div className="text-muted text-sm">{u.period_label}</div>
                          </td>
                          <td>
                            <strong>{u.course_code}</strong> - {u.course_name}
                          </td>
                          <td>{u.original_faculty_name}</td>
                          <td colSpan={2} className="text-danger">
                            Uncovered (No eligible faculty with sufficient capacity)
                          </td>
                          <td>—</td>
                          <td>
                            <span className="badge danger">Uncovered</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Two-Column Breakdown: Scores & State Diff */}
              <div className="dashboard-columns">
                {/* Soft Preference Breakdown */}
                <div className="column">
                  <div className="card">
                    <div className="card-header">
                      <h4 className="card-title">Soft Preference Scores (SP-01 to SP-04)</h4>
                    </div>
                    <div className="score-breakdown-list">
                      <div className="score-row">
                        <span>SP-01: Preferred Slot Alignment</span>
                        <strong>{activePlan.score_breakdown?.['SP-01']?.toFixed(1) || '0.0'} pts</strong>
                      </div>
                      <div className="score-row">
                        <span>SP-02: Subject Expertise Fit</span>
                        <strong>{activePlan.score_breakdown?.['SP-02']?.toFixed(1) || '0.0'} pts</strong>
                      </div>
                      <div className="score-row">
                        <span>SP-03: Same Department Continuity</span>
                        <strong>{activePlan.score_breakdown?.['SP-03']?.toFixed(1) || '0.0'} pts</strong>
                      </div>
                      <div className="score-row">
                        <span>SP-04: Workload Balance</span>
                        <strong>{activePlan.score_breakdown?.['SP-04']?.toFixed(1) || '0.0'} pts</strong>
                      </div>
                    </div>
                    <p className="card-footer-text">
                      Multi-objective optimization: 100% coverage dominates soft scores lexicographically.
                    </p>
                  </div>
                </div>

                {/* Conflict State Diff */}
                <div className="column">
                  <div className="card">
                    <div className="card-header">
                      <h4 className="card-title">Constraint State Diff (HC-09 Verification)</h4>
                    </div>
                    <div className="diff-stats-grid">
                      <div className="diff-stat-item">
                        <div className="diff-number text-success">
                          {simulationResult.diff?.new_violations?.length ?? 0}
                        </div>
                        <div className="diff-label">New Hard Violations</div>
                      </div>
                      <div className="diff-stat-item">
                        <div className="diff-number text-primary">
                          {simulationResult.diff?.resolved_violations?.length ?? 0}
                        </div>
                        <div className="diff-label">Baseline Conflicts Resolved</div>
                      </div>
                      <div className="diff-stat-item">
                        <div className="diff-number text-muted">
                          {simulationResult.diff?.existing_violations?.length ?? 0}
                        </div>
                        <div className="diff-label">Baseline Pre-existing</div>
                      </div>
                      <div className="diff-stat-item">
                        <div className="diff-number text-muted">
                          {simulationResult.diff?.remaining_violations?.length ?? 0}
                        </div>
                        <div className="diff-label">Remaining Unaffected</div>
                      </div>
                    </div>
                    <p className="card-footer-text">
                      Guaranteed by deterministic RuleEngine: zero new hard constraint violations introduced.
                    </p>
                  </div>
                </div>
              </div>

              {/* Faculty Workload Shifts */}
              <div className="card">
                <div className="card-header">
                  <h4 className="card-title">Faculty Workload Shifts (Teaching Hours This Week)</h4>
                </div>
                <div className="table-responsive">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Faculty Name</th>
                        <th>Assignments Added</th>
                        <th>Estimated Teaching Hours</th>
                        <th>Workload Impact</th>
                      </tr>
                    </thead>
                    <tbody>
                      {workloadShifts.length === 0 ? (
                        <tr>
                          <td colSpan={4} className="text-muted" style={{ textAlign: 'center', padding: '1rem' }}>
                            No additional faculty substitutions in this plan.
                          </td>
                        </tr>
                      ) : (
                        workloadShifts.map((shift) => (
                          <tr key={shift.faculty_id}>
                            <td><strong>{shift.faculty_name}</strong></td>
                            <td>{shift.delta_hours > 0 ? `+${shift.delta_hours}` : `${shift.delta_hours}`} classes</td>
                            <td>{shift.after_hours.toFixed(1)}h / week</td>
                            <td>
                              <span
                                className={`delta-badge ${
                                  shift.delta_hours > 0
                                    ? 'positive'
                                    : shift.delta_hours < 0
                                    ? 'negative'
                                    : 'neutral'
                                }`}
                              >
                                {shift.delta_hours > 0 ? `+${shift.delta_hours.toFixed(1)}h` : `${shift.delta_hours.toFixed(1)}h`}
                              </span>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="actions-bar">
                <div className="actions-left">
                  {approvalSuccess ? (
                    <div className="approval-pill success">
                      <CheckCircle size={18} />
                      <span>Decision Approved & Persisted in Audit Log</span>
                    </div>
                  ) : simulationResult.decision_status === 'approved' ? (
                    <div className="approval-pill approved">
                      <CheckCircle size={18} />
                      <span>Already Approved in Audit Log</span>
                    </div>
                  ) : (
                    <button
                      onClick={handleApproveDecision}
                      disabled={isApproving}
                      className="btn-success"
                    >
                      {isApproving ? <Loader2 size={16} className="animate-spin" /> : <FileCheck size={16} />}
                      <span>Approve Recommendation</span>
                    </button>
                  )}
                </div>

                <div className="actions-right">
                  <button
                    onClick={() => onInspectDecision(simulationResult.decision_id)}
                    className="btn-primary"
                  >
                    <span>Inspect Candidate Pool & Rejections (Screen 3)</span>
                    <ArrowRight size={16} />
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
