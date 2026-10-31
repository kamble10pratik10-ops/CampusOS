import React from 'react';
import { ShieldAlert, LogOut, User as UserIcon } from 'lucide-react';
import type { User, HealthResponse } from '../types';

interface NavbarProps {
  user: User | null;
  health: HealthResponse | null;
  onLogout: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ user, health, onLogout }) => {
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
                <UserIcon size={16} />
                <span className="user-email">{user.email}</span>
                <span className="role-tag">{user.role.toUpperCase()}</span>
              </div>
              <button onClick={onLogout} className="btn-logout" title="Sign out">
                <LogOut size={16} />
                <span>Sign Out</span>
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="banner-synthetic">
        <ShieldAlert size={14} />
        <span>⚠ SYNTHETIC DATA ONLY — Prototype system for evaluation purposes. Not real institutional data.</span>
      </div>
    </header>
  );
};
