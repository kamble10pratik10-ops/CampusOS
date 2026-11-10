import React, { useState, useEffect } from 'react';
import {
  History,
  Search,
  Filter,
  ShieldCheck,
  ArrowRight,
  RefreshCw,
  Loader2,
} from 'lucide-react';
import { api } from '../api/client';
import type { AuditListItem, User } from '../types';

interface AuditLogPageProps {
  currentUser: User | null;
  onInspectDecision: (decisionId: string) => void;
}

export const AuditLogPage: React.FC<AuditLogPageProps> = ({
  currentUser,
  onInspectDecision,
}) => {
  const [auditList, setAuditList] = useState<AuditListItem[]>([]);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'simulation' | 'approved'>('all');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAuditLogs();
  }, [currentUser]);

  const loadAuditLogs = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getSimulationHistory(50);
      setAuditList(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch audit log history');
    } finally {
      setIsLoading(false);
    }
  };

  const filteredLogs = auditList.filter((item) => {
    const matchesSearch =
      item.scenario_summary.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.created_by_email.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || item.decision_status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="audit-container">
      {/* Notice Banner */}
      <div className="audit-notice-banner">
        <ShieldCheck size={20} className="text-success" />
        <div>
          <strong>Immutable Audit Trail & Non-Mutation Guarantee (HC-10):</strong>
          <span>
            {' '}
            All simulation runs and human decisions are persisted append-only in PostgreSQL (
            <code>decision</code> and <code>decision_evidence</code> tables). Marking a decision as
            approved records administrative verification without mutating operational timetable
            templates or active class schedules.
          </span>
        </div>
      </div>

      {/* Header & Filter Bar */}
      <div className="section-header">
        <div>
          <h2 className="section-title">Decision Audit Log (Screen 4)</h2>
          <p className="section-desc">
            Historical trace of operational simulations, solver outcomes, and human administrative approvals.
          </p>
        </div>

        <div className="filter-actions">
          <button onClick={loadAuditLogs} disabled={isLoading} className="btn-secondary">
            {isLoading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            <span>Refresh Audit Log</span>
          </button>
        </div>
      </div>

      {/* Search & Filter Controls */}
      <div className="card filter-card">
        <div className="filter-bar">
          <div className="search-input-wrapper">
            <Search size={18} className="search-icon" />
            <input
              type="text"
              className="search-input"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by scenario name or user email..."
            />
          </div>

          <div className="filter-group">
            <Filter size={16} className="filter-icon" />
            <span className="filter-label">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as any)}
              className="form-select filter-select"
            >
              <option value="all">All Records ({auditList.length})</option>
              <option value="simulation">
                Simulated ({auditList.filter((a) => a.decision_status === 'simulation').length})
              </option>
              <option value="approved">
                Approved ({auditList.filter((a) => a.decision_status === 'approved').length})
              </option>
            </select>
          </div>
        </div>
      </div>

      {/* Audit Table */}
      <div className="card table-card">
        {isLoading ? (
          <div className="loading-state">
            <Loader2 size={32} className="animate-spin text-primary" />
            <p>Loading historical audit records...</p>
          </div>
        ) : error ? (
          <div className="alert-box danger">
            <p>{error}</p>
          </div>
        ) : filteredLogs.length === 0 ? (
          <div className="empty-state">
            <History size={40} className="text-muted" />
            <p>No audit records found matching your filters.</p>
          </div>
        ) : (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Scenario & Intent</th>
                  <th>User & Role</th>
                  <th>Decision Status</th>
                  <th>Coverage</th>
                  <th>Critic Status</th>
                  <th>Runtime</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredLogs.map((item) => (
                  <tr key={item.id} className="audit-row">
                    <td>
                      <div className="text-bold">
                        {new Date(item.created_at).toLocaleDateString()}
                      </div>
                      <div className="text-muted text-xs">
                        {new Date(item.created_at).toLocaleTimeString()}
                      </div>
                    </td>
                    <td>
                      <div className="text-bold">{item.scenario_summary}</div>
                      <div className="text-muted text-xs text-mono">ID: {item.id}</div>
                    </td>
                    <td>
                      <div>{item.created_by_email}</div>
                    </td>
                    <td>
                      <span className={`status-tag ${item.decision_status}`}>
                        {item.decision_status.toUpperCase()}
                      </span>
                    </td>
                    <td>
                      <span className="badge success">
                        {item.coverage_percentage?.toFixed(1) || 100}% ({item.total_affected} classes)
                      </span>
                    </td>
                    <td>
                      <span
                        className={`badge ${
                          item.critic_status === 'feasible_complete' ? 'success' : 'warning'
                        }`}
                      >
                        {item.critic_status}
                      </span>
                    </td>
                    <td className="text-mono text-sm">{item.runtime_ms} ms</td>
                    <td>
                      <button
                        onClick={() => onInspectDecision(item.id)}
                        className="btn-sm btn-primary"
                        title="View reasoning trace & evidence"
                      >
                        <span>Inspect</span>
                        <ArrowRight size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
