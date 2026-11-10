import React from 'react';
import {
  ShieldAlert,
  LogOut,
  User as UserIcon,
  LayoutDashboard,
  PlayCircle,
  Search,
  History,
  Building,
} from 'lucide-react';
import type { User, HealthResponse } from '../types';

export type NavTab = 'dashboard' | 'simulator' | 'inspector' | 'audit';

interface NavbarProps {
  user: User | null;
  health: HealthResponse | null;
  activeTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  onLogout: () => void;
  onSwitchUser?: (email: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  user,
  health,
  activeTab,
  onSelectTab,
  onLogout,
  onSwitchUser,
}) => {
  return (
    <header className="header">
      <div className="header-inner">
        <div className="brand">
          <div className="logo-badge">ANVIL</div>
          <div>
            <h1 className="brand-title">Campus OS</h1>
            <p className="brand-subtitle">Multi-Agent Decision Support for College Operations</p>
          </div>
        </div>

        {user && (
          <nav className="nav-tabs" aria-label="Main Navigation">
            <button
              onClick={() => onSelectTab('dashboard')}
              className={`nav-tab-btn ${activeTab === 'dashboard' ? 'active' : ''}`}
            >
              <LayoutDashboard size={16} />
              <span>1. Operations Dashboard</span>
            </button>
            <button
              onClick={() => onSelectTab('simulator')}
              className={`nav-tab-btn ${activeTab === 'simulator' ? 'active' : ''}`}
            >
              <PlayCircle size={16} />
              <span>2. What-If Simulator</span>
            </button>
            <button
              onClick={() => onSelectTab('inspector')}
              className={`nav-tab-btn ${activeTab === 'inspector' ? 'active' : ''}`}
            >
              <Search size={16} />
              <span>3. Decision Inspector</span>
            </button>
            <button
              onClick={() => onSelectTab('audit')}
              className={`nav-tab-btn ${activeTab === 'audit' ? 'active' : ''}`}
            >
              <History size={16} />
              <span>4. Audit Log</span>
            </button>
          </nav>
        )}

        <div className="header-actions">
          {health && (
            <div className="status-pill">
              <span className="status-indicator"></span>
              <span>Backend: {health.status.toUpperCase()} ({health.milestone})</span>
            </div>
          )}

          {user && (
            <div className="user-profile">
              <div className="user-info">
                <UserIcon size={15} />
                <span className="user-email">{user.email}</span>
                <span className="role-tag">{user.role.toUpperCase()}</span>
                {user.department_id && (
                  <span className="dept-tag">
                    <Building size={12} />
                    <span>HOD Dept</span>
                  </span>
                )}
              </div>

              {onSwitchUser && (
                <div className="role-switcher">
                  <select
                    className="role-select"
                    value={user.email}
                    onChange={(e) => onSwitchUser(e.target.value)}
                    title="Switch user role"
                  >
                    <option value="principal@campus.os">Principal (All Depts)</option>
                    <option value="hod.cs@campus.os">HOD Computer Science</option>
                    <option value="hod.ec@campus.os">HOD Electronics</option>
                    <option value="hod.me@campus.os">HOD Mechanical</option>
                  </select>
                </div>
              )}

              <button onClick={onLogout} className="btn-logout" title="Sign out">
                <LogOut size={15} />
                <span>Sign Out</span>
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="banner-synthetic">
        <ShieldAlert size={14} />
        <span>⚠ SYNTHETIC DATA ONLY — Decisions are simulated decision-support recommendations. Recording decisions does NOT mutate live timetable records.</span>
      </div>
    </header>
  );
};
