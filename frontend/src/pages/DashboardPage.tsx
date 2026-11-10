import React from 'react';
import {
  Users,
  BookOpen,
  Building2,
  Clock,
  AlertTriangle,
  CheckCircle2,
  TrendingUp,
  FileText,
  Zap,
  ArrowRight,
} from 'lucide-react';
import type { DashboardData, User } from '../types';

interface DashboardPageProps {
  data: DashboardData;
  currentUser: User | null;
  onRefresh: () => void;
  onLaunchHeroScenario: () => void;
  onInspectDecision: (decisionId: string) => void;
  onInspectConflicts: () => void;
  isLoading: boolean;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  data,
  currentUser,
  onRefresh,
  onLaunchHeroScenario,
  onInspectDecision,
  onInspectConflicts,
  isLoading,
}) => {
  const isHod = currentUser?.role === 'hod';

  return (
    <div className="dashboard-container">
      {/* Hero Scenario Trigger Banner */}
      <div className="hero-callout-card">
        <div className="hero-callout-content">
          <div className="hero-badge">
            <Zap size={16} />
            <span>HERO SCENARIO</span>
          </div>
          <h3 className="hero-title">Faculty Leave Replacement: Dr. Raj Sharma (CS001)</h3>
          <p className="hero-desc">
            Dr. Raj Sharma is scheduled on leave from <strong>2026-11-02 (Mon)</strong> to{' '}
            <strong>2026-11-04 (Wed)</strong>. 6 class occurrences are affected across CS sections.
            Run joint OR-Tools CP-SAT optimization with deterministic Critic validation.
          </p>
        </div>
        <button onClick={onLaunchHeroScenario} className="btn-hero-action">
          <span>Simulate Replacement Plans</span>
          <ArrowRight size={18} />
        </button>
      </div>

      {/* Section Header */}
      <div className="section-header">
        <div>
          <div className="scope-indicator">
            <span className="badge info">
              {isHod ? 'Department Scoped (HOD View)' : 'Institution-Wide (Principal View)'}
            </span>
          </div>
          <h2 className="section-title">Operations Dashboard (Screen 1)</h2>
          <p className="section-desc">
            Authoritative operational statistics from PostgreSQL. Reference Date:{' '}
            <strong>{data.demo_today}</strong>
          </p>
        </div>
        <button onClick={onRefresh} disabled={isLoading} className="btn-primary">
          {isLoading ? 'Refreshing...' : 'Refresh Stats'}
        </button>
      </div>

      {/* Metric Cards Grid */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon-wrapper blue">
            <Users size={20} />
          </div>
          <div>
            <div className="stat-label">Total Faculty</div>
            <div className="stat-value">{data.total_faculty}</div>
            <div className="stat-subtext">
              <span className="text-success">{data.faculty_available_today} Available</span> ·{' '}
              <span className="text-warning">{data.faculty_on_leave_today} on Leave</span>
            </div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon-wrapper purple">
            <BookOpen size={20} />
          </div>
          <div>
            <div className="stat-label">Active Courses</div>
            <div className="stat-value">{data.total_courses}</div>
            <div className="stat-subtext">
              {isHod ? 'Department Courses' : 'Across 3 Departments (CS, EC, ME)'}
            </div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon-wrapper amber">
            <Building2 size={20} />
          </div>
          <div>
            <div className="stat-label">Rooms & Labs</div>
            <div className="stat-value">{data.total_rooms}</div>
            <div className="stat-subtext">10 Classrooms · 5 Specialized Labs</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon-wrapper green">
            <Clock size={20} />
          </div>
          <div>
            <div className="stat-label">Weekly Occurrences</div>
            <div className="stat-value">{data.occurrences_this_week}</div>
            <div className="stat-subtext">
              {data.occurrences_today} scheduled today ({data.demo_today})
            </div>
          </div>
        </div>
      </div>

      {/* Main Two-Column Layout */}
      <div className="dashboard-columns">
        {/* Left Column: Conflicts & Violations */}
        <div className="column">
          <div className="card">
            <div className="card-header">
              <div className="card-title-group">
                <AlertTriangle className="text-danger" size={20} />
                <h3 className="card-title">Detected Operational Conflicts</h3>
              </div>
              <span className="badge danger">{data.conflict_count} Hard Conflicts</span>
            </div>
            <p className="card-description">
              Planted baseline constraint violations detected in the synthetic schedule by the
              deterministic Rule Engine (HC-01 through HC-08).
            </p>
            <div className="conflict-list">
              {data.conflicts_summary.map((conflict) => (
                <div key={conflict.rule_id} className="conflict-item">
                  <div className="conflict-header">
                    <span className="rule-badge">{conflict.rule_id}</span>
                    <span className="conflict-count">{conflict.count} occurrence(s)</span>
                  </div>
                  <div className="conflict-desc">{conflict.description}</div>
                  <div className="conflict-note">{conflict.note}</div>
                </div>
              ))}
            </div>
            <div className="card-footer">
              <button onClick={onInspectConflicts} className="btn-secondary full-width">
                Inspect Conflicts in Simulator
              </button>
            </div>
          </div>
        </div>

        {/* Right Column: Workload & Audit Trail */}
        <div className="column">
          {/* Workload Summary */}
          <div className="card">
            <div className="card-header">
              <div className="card-title-group">
                <TrendingUp className="text-primary" size={20} />
                <h3 className="card-title">Faculty Workload Distribution</h3>
              </div>
            </div>
            <div className="workload-stats">
              <div className="workload-item">
                <div className="workload-value">{data.workload_summary.avg_hours_this_week}h</div>
                <div className="workload-label">Average Weekly Hours</div>
              </div>
              <div className="workload-item">
                <div className="workload-value">{data.workload_summary.max_hours_this_week}h</div>
                <div className="workload-label">Max Assigned Hours</div>
              </div>
              <div className="workload-item">
                <div className="workload-value">{data.workload_summary.min_hours_this_week}h</div>
                <div className="workload-label">Min Assigned Hours</div>
              </div>
              <div className="workload-item">
                <div className="workload-value text-danger">
                  {data.workload_summary.overloaded_count}
                </div>
                <div className="workload-label">Overloaded Faculty</div>
              </div>
            </div>
            <p className="card-footer-text">
              Calculated from actual period durations (enforcing HC-07 weekly workload caps).
            </p>
          </div>

          {/* Decisions Audit Trail Preview */}
          <div className="card">
            <div className="card-header">
              <div className="card-title-group">
                <FileText className="text-secondary" size={20} />
                <h3 className="card-title">Recent Audit Log & Decisions</h3>
              </div>
            </div>
            {data.recent_decisions.length === 0 ? (
              <div className="empty-state">
                <CheckCircle2 size={32} className="text-muted" />
                <p>No recorded decisions yet.</p>
                <span>Run a What-If simulation to record decisions into the audit trail.</span>
              </div>
            ) : (
              <div className="decision-list">
                {data.recent_decisions.map((decision) => (
                  <div key={decision.id} className="decision-item">
                    <div className="decision-info">
                      <div className="decision-title">{decision.scenario_summary}</div>
                      <div className="decision-meta">
                        By {decision.created_by_email} on{' '}
                        {new Date(decision.created_at).toLocaleString()}
                      </div>
                    </div>
                    <div className="decision-actions">
                      <span className={`status-tag ${decision.decision_status}`}>
                        {decision.decision_status.toUpperCase()}
                      </span>
                      <button
                        onClick={() => onInspectDecision(decision.id)}
                        className="btn-sm btn-outline"
                      >
                        Inspect
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
