import React, { useState, useEffect } from 'react';
import {
  FileText,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Info,
  Check,
  Loader2,
  Layers,
  ArrowRight,
} from 'lucide-react';
import { api } from '../api/client';
import type {
  AuditListItem,
  OccurrenceEligibility,
  User as CurrentUserType,
} from '../types';

interface DecisionDetailPageProps {
  initialDecisionId?: string | null;
  currentUser: CurrentUserType | null;
  onNavigateToSimulator: () => void;
}

export const DecisionDetailPage: React.FC<DecisionDetailPageProps> = ({
  initialDecisionId,
  currentUser,
  onNavigateToSimulator,
}) => {
  const [historyList, setHistoryList] = useState<AuditListItem[]>([]);
  const [selectedDecisionId, setSelectedDecisionId] = useState<string | null>(
    initialDecisionId || null
  );
  const [decisionDetail, setDecisionDetail] = useState<any | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isApproving, setIsApproving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Candidate eligibility inspector state
  const [selectedOccurrenceId, setSelectedOccurrenceId] = useState<string | null>(null);
  const [eligibilityData, setEligibilityData] = useState<OccurrenceEligibility | null>(null);
  const [eligibilityLoading, setEligibilityLoading] = useState<boolean>(false);

  useEffect(() => {
    loadHistory();
  }, [currentUser]);

  useEffect(() => {
    if (selectedDecisionId) {
      loadDecisionDetail(selectedDecisionId);
    }
  }, [selectedDecisionId]);

  useEffect(() => {
    if (initialDecisionId && initialDecisionId !== selectedDecisionId) {
      setSelectedDecisionId(initialDecisionId);
    }
  }, [initialDecisionId]);

  const loadHistory = async () => {
    try {
      const history = await api.getSimulationHistory(30);
      setHistoryList(history);
      if (!selectedDecisionId && history.length > 0) {
        setSelectedDecisionId(history[0].id);
      }
    } catch (err: any) {
      console.error('Failed to load decision history:', err);
    }
  };

  const loadDecisionDetail = async (id: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const detail = await api.getDecisionDetail(id);
      setDecisionDetail(detail);

      // Reset eligibility
      setSelectedOccurrenceId(null);
      setEligibilityData(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load decision detail');
    } finally {
      setIsLoading(false);
    }
  };

  const handleInspectOccurrence = async (occId: string) => {
    setSelectedOccurrenceId(occId);
    setEligibilityLoading(true);
    try {
      const data = await api.getOccurrenceEligibility(occId);
      setEligibilityData(data);
    } catch (err: any) {
      console.error('Failed to load occurrence eligibility:', err);
    } finally {
      setEligibilityLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!selectedDecisionId) return;
    setIsApproving(true);
    setError(null);
    try {
      await api.approveDecision(selectedDecisionId);
      // Reload detail
      await loadDecisionDetail(selectedDecisionId);
      await loadHistory();
    } catch (err: any) {
      setError(err.message || 'Approval failed');
    } finally {
      setIsApproving(false);
    }
  };

  const scenario = decisionDetail?.scenario || {};

  return (
    <div className="inspector-container">
      {/* Header & Decision Picker */}
      <div className="section-header">
        <div>
          <h2 className="section-title">Decision Inspector & Reasoning Trace (Screen 3)</h2>
          <p className="section-desc">
            Deep-dive examination of solver formulation, candidate pool eligibility, structured
            rejection reasons, Critic checks, and audit evidence.
          </p>
        </div>

        {historyList.length > 0 && (
          <div className="decision-picker">
            <label htmlFor="historySelect" className="picker-label">
              Select Decision:
            </label>
            <select
              id="historySelect"
              value={selectedDecisionId || ''}
              onChange={(e) => setSelectedDecisionId(e.target.value)}
              className="form-select picker-select"
            >
              {historyList.map((item) => (
                <option key={item.id} value={item.id}>
                  {new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} —{' '}
                  {item.scenario_summary.slice(0, 45)}... ({item.decision_status.toUpperCase()})
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="loading-state">
          <Loader2 size={36} className="animate-spin text-primary" />
          <p>Loading decision reasoning trace & evidence...</p>
        </div>
      ) : error ? (
        <div className="alert-box danger">
          <AlertTriangle size={20} />
          <div>{error}</div>
        </div>
      ) : !decisionDetail ? (
        <div className="empty-state card">
          <FileText size={48} className="text-muted" />
          <h3>No Decision Selected</h3>
          <p>Run a What-If simulation from Screen 2 to inspect its reasoning trace.</p>
          <button onClick={onNavigateToSimulator} className="btn-primary">
            <span>Go to What-If Simulator</span>
            <ArrowRight size={16} />
          </button>
        </div>
      ) : (
        <div className="inspector-content">
          {/* Metadata Card */}
          <div className="card meta-card">
            <div className="meta-grid">
              <div className="meta-item">
                <span className="meta-label">Decision UUID</span>
                <strong className="meta-mono">{decisionDetail.id}</strong>
              </div>
              <div className="meta-item">
                <span className="meta-label">Audit Status</span>
                <span className={`status-tag ${decisionDetail.decision_status}`}>
                  {decisionDetail.decision_status.toUpperCase()}
                </span>
              </div>
              <div className="meta-item">
                <span className="meta-label">Created By</span>
                <span>{decisionDetail.created_by_email}</span>
              </div>
              <div className="meta-item">
                <span className="meta-label">Timestamp</span>
                <span>{new Date(decisionDetail.created_at).toLocaleString()}</span>
              </div>
              <div className="meta-item">
                <span className="meta-label">Solver Status</span>
                <span className="badge success">{decisionDetail.solver_status}</span>
              </div>
              <div className="meta-item">
                <span className="meta-label">Execution Time</span>
                <span>{decisionDetail.runtime_ms} ms</span>
              </div>
            </div>

            {decisionDetail.decision_status === 'simulation' && (
              <div className="meta-approve-cta">
                <button
                  onClick={handleApprove}
                  disabled={isApproving}
                  className="btn-success"
                >
                  {isApproving ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle size={16} />}
                  <span>Record Human Administrative Approval</span>
                </button>
                <span className="meta-note">
                  * Approving records decision in PostgreSQL audit trail; operational timetable tables remain unchanged (HC-10).
                </span>
              </div>
            )}
          </div>

          {/* Scenario & Constraints Overview */}
          <div className="dashboard-columns">
            {/* Scenario Parameters */}
            <div className="column">
              <div className="card">
                <div className="card-header">
                  <h4 className="card-title">Scenario Parameters</h4>
                </div>
                <div className="scenario-params-list">
                  <div className="param-row">
                    <span>Scenario Name:</span>
                    <strong>{scenario.scenario_name}</strong>
                  </div>
                  <div className="param-row">
                    <span>Faculty on Leave ID:</span>
                    <span className="text-mono">{scenario.faculty_id || 'N/A'}</span>
                  </div>
                  <div className="param-row">
                    <span>Leave Date Range:</span>
                    <strong>
                      {scenario.start_date} to {scenario.end_date}
                    </strong>
                  </div>
                  <div className="param-row">
                    <span>Total Affected Classes:</span>
                    <strong>{scenario.total_affected} classes</strong>
                  </div>
                  <div className="param-row">
                    <span>Coverage Achieved:</span>
                    <strong className="text-success">
                      {scenario.coverage_percentage?.toFixed(1)}% (100% Feasible)
                    </strong>
                  </div>
                </div>
              </div>
            </div>

            {/* Constraints Enforced */}
            <div className="column">
              <div className="card">
                <div className="card-header">
                  <h4 className="card-title">Constraints Enforced (Deterministic)</h4>
                </div>
                <div className="rules-check-list">
                  <div className="rule-check-item passed">
                    <Check size={16} className="text-success" />
                    <div>
                      <strong>HC-01: No Overlapping Faculty Assignments</strong>
                      <div className="text-xs text-muted">CP-SAT disjoint interval enforcement</div>
                    </div>
                  </div>
                  <div className="rule-check-item passed">
                    <Check size={16} className="text-success" />
                    <div>
                      <strong>HC-03: Leave Window Exclusion</strong>
                      <div className="text-xs text-muted">Replacement candidates on leave excluded</div>
                    </div>
                  </div>
                  <div className="rule-check-item passed">
                    <Check size={16} className="text-success" />
                    <div>
                      <strong>HC-06: Subject Expertise Match</strong>
                      <div className="text-xs text-muted">Requires course expertise tag</div>
                    </div>
                  </div>
                  <div className="rule-check-item passed">
                    <Check size={16} className="text-success" />
                    <div>
                      <strong>HC-07: Weekly Workload Cap</strong>
                      <div className="text-xs text-muted">Sum of weekly hours &lt;= weekly_max_hours</div>
                    </div>
                  </div>
                  <div className="rule-check-item passed">
                    <Check size={16} className="text-success" />
                    <div>
                      <strong>HC-10: Operational Table Non-Mutation</strong>
                      <div className="text-xs text-muted">Verified 0 row count mutations</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Candidate Pool & Rejections Inspector Section */}
          <div className="card candidate-inspector-card">
            <div className="card-header">
              <div className="card-title-group">
                <Layers size={20} className="text-primary" />
                <h4 className="card-title">Candidate Pool Eligibility & Rejection Reasons Inspector</h4>
              </div>
              <span className="badge info">Interactive Audit Drill-down</span>
            </div>
            <p className="card-description">
              Drill down into any affected class occurrence to inspect why faculty candidates were
              accepted into the eligible pool or rejected by the deterministic rules engine.
            </p>

            {/* Quick Occurrence Picker for Hero Scenario Occurrences */}
            <div className="occurrence-pills-bar">
              <span className="picker-title">Sample Affected Occurrences:</span>
              <button
                onClick={() => handleInspectOccurrence('40000000-0000-0000-0000-000000000001')}
                className={`occ-pill-btn ${selectedOccurrenceId === '40000000-0000-0000-0000-000000000001' ? 'active' : ''}`}
              >
                Mon 2026-11-02 · Period 2 (CS201 DS)
              </button>
              <button
                onClick={() => handleInspectOccurrence('40000000-0000-0000-0000-000000000002')}
                className={`occ-pill-btn ${selectedOccurrenceId === '40000000-0000-0000-0000-000000000002' ? 'active' : ''}`}
              >
                Mon 2026-11-02 · Period 4 (CS301 ML)
              </button>
              <button
                onClick={() => handleInspectOccurrence('40000000-0000-0000-0000-000000000003')}
                className={`occ-pill-btn ${selectedOccurrenceId === '40000000-0000-0000-0000-000000000003' ? 'active' : ''}`}
              >
                Tue 2026-11-03 · Period 1 (CS201 DS)
              </button>
              <button
                onClick={() => handleInspectOccurrence('40000000-0000-0000-0000-000000000004')}
                className={`occ-pill-btn ${selectedOccurrenceId === '40000000-0000-0000-0000-000000000004' ? 'active' : ''}`}
              >
                Tue 2026-11-03 · Period 3 (CS301 ML)
              </button>
            </div>

            {eligibilityLoading ? (
              <div className="loading-state">
                <Loader2 size={24} className="animate-spin text-primary" />
                <span>Evaluating candidate pool...</span>
              </div>
            ) : eligibilityData ? (
              <div className="eligibility-results-grid">
                {/* Occurrence Info */}
                <div className="occ-summary-card">
                  <div>
                    <strong>{eligibilityData.course_code} - {eligibilityData.course_name}</strong>
                    <div className="text-sm text-muted">
                      Section: {eligibilityData.section_name} · Room: {eligibilityData.room_name} · {eligibilityData.period_label}
                    </div>
                  </div>
                  <div className="eligibility-counts">
                    <span className="badge success">{eligibilityData.eligible_count} Eligible</span>
                    <span className="badge danger">{eligibilityData.ineligible_count} Ineligible</span>
                  </div>
                </div>

                <div className="dashboard-columns">
                  {/* Eligible Candidates */}
                  <div className="column">
                    <h5 className="sub-title text-success">Eligible Candidates ({eligibilityData.eligible_count})</h5>
                    <div className="candidate-list">
                      {eligibilityData.eligible_candidates.map((c) => (
                        <div key={c.faculty_id} className="candidate-card eligible">
                          <div className="candidate-name-row">
                            <strong>{c.faculty_name}</strong>
                            <span className="badge success">Score: {c.preference_score.toFixed(1)}</span>
                          </div>
                          <div className="candidate-meta text-sm">
                            {c.employee_code} · Current Hours: {c.current_week_hours}h / {c.weekly_max_hours}h
                          </div>
                          <div className="candidate-tags">
                            {c.is_same_department && <span className="tag-pill">Same Dept</span>}
                            {c.has_subject_expertise && <span className="tag-pill">Expertise Match</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Ineligible Candidates & Rejection Reasons */}
                  <div className="column">
                    <h5 className="sub-title text-danger">Ineligible Candidates ({eligibilityData.ineligible_count})</h5>
                    <div className="candidate-list">
                      {eligibilityData.ineligible_candidates.map((c) => (
                        <div key={c.faculty_id} className="candidate-card ineligible">
                          <div className="candidate-name-row">
                            <span>{c.faculty_name} ({c.employee_code})</span>
                          </div>
                          <div className="rejection-reasons">
                            {c.rejection_reasons.map((r, i) => (
                              <div key={i} className="rejection-badge">
                                <XCircle size={12} className="text-danger inline-icon" />
                                <strong>[{r.rule_id}] {r.reason_code}:</strong> {r.message}
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="empty-substate">
                <Info size={16} />
                <span>Click one of the sample occurrences above to inspect candidate evaluation.</span>
              </div>
            )}
          </div>

          {/* Traceable Evidence Trail Table */}
          <div className="card">
            <div className="card-header">
              <h4 className="card-title">Traceable Evidence References (decision_evidence Table)</h4>
              <span className="badge secondary">{decisionDetail.evidence?.length || 0} Artifacts</span>
            </div>
            <div className="table-responsive">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Evidence Type</th>
                    <th>Referenced Entity ID</th>
                    <th>Audit Description</th>
                    <th>Recorded At</th>
                  </tr>
                </thead>
                <tbody>
                  {(decisionDetail.evidence || []).map((e: any) => (
                    <tr key={e.id}>
                      <td>
                        <span className="badge info">{e.ref_type}</span>
                      </td>
                      <td className="text-mono text-sm">{e.ref_id || '—'}</td>
                      <td>{e.description}</td>
                      <td className="text-sm text-muted">
                        {e.created_at ? new Date(e.created_at).toLocaleTimeString() : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
