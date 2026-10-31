import React from 'react';
import { 
  Users, 
  BookOpen, 
  Building2, 
  Clock, 
  AlertTriangle, 
  CheckCircle2, 
  TrendingUp,
  FileText
} from 'lucide-react';
import type { DashboardData } from '../types';

interface DashboardPageProps {
  data: DashboardData;
  onRefresh: () => void;
  isLoading: boolean;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ data, onRefresh, isLoading }) => {
  return (
    <div className="dashboard-container">
      {/* Top Banner & Control */}
      <div className="section-header">
        <div>
          <h2 className="section-title">Operations Dashboard (Screen 1)</h2>
          <p className="section-desc">
            Deterministic operations overview powered by PostgreSQL backend. Reference Date: <strong>{data.demo_today}</strong>
          </p>
        </div>
        <button 
          onClick={onRefresh} 
          disabled={isLoading}
          className="btn-primary"
        >
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
              <span className="text-success">{data.faculty_available_today} Available</span> · {data.faculty_on_leave_today} on Leave
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
            <div className="stat-subtext">Across 3 Departments (CS, EC, ME)</div>
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
            <div className="stat-subtext">{data.occurrences_today} scheduled today ({data.demo_today})</div>
          </div>
        </div>
      </div>

      {/* Main Two-Column Layout */}
      <div className="dashboard-columns">
        {/* Left Column: Conflicts & Warnings */}
        <div className="column">
          <div className="card">
            <div className="card-header">
              <div className="card-title-group">
                <AlertTriangle className="text-danger" size={20} />
                <h3 className="card-title">Detected Operational Conflicts</h3>
              </div>
              <span className="badge danger">{data.conflict_count} Detected</span>
            </div>
            <p className="card-description">
              Planted constraint violations detected in the synthetic schedule. In M2, the deterministic rule engine will provide structured signatures and evidence.
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
          </div>
        </div>

        {/* Right Column: Workload & Decisions */}
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
                <div className="workload-value text-danger">{data.workload_summary.overloaded_count}</div>
                <div className="workload-label">Overloaded Faculty</div>
              </div>
            </div>
            <p className="card-footer-text">
              Hours calculated from real period durations (HC-07 hard constraint).
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
                <span>Simulations and approved replacement plans will appear here in M4.</span>
              </div>
            ) : (
              <div className="decision-list">
                {data.recent_decisions.map((decision) => (
                  <div key={decision.id} className="decision-item">
                    <div>
                      <div className="decision-title">{decision.scenario_summary}</div>
                      <div className="decision-meta">
                        By {decision.created_by_email} on {new Date(decision.created_at).toLocaleDateString()}
                      </div>
                    </div>
                    <span className={`status-tag ${decision.decision_status}`}>
                      {decision.decision_status.toUpperCase()}
                    </span>
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
