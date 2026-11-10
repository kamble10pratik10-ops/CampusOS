import { useEffect, useState } from 'react';
import { api } from './api/client';
import { Navbar, type NavTab } from './components/Navbar';
import { DashboardPage } from './pages/DashboardPage';
import { WhatIfSimulatorPage } from './pages/WhatIfSimulatorPage';
import { DecisionDetailPage } from './pages/DecisionDetailPage';
import { AuditLogPage } from './pages/AuditLogPage';
import { ErrorBoundary } from './components/ErrorBoundary';
import type { DashboardData, HealthResponse, User } from './types';
import { KeyRound, AlertCircle, Loader2 } from 'lucide-react';
import './index.css';

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [activeTab, setActiveTab] = useState<NavTab>('dashboard');
  const [selectedDecisionId, setSelectedDecisionId] = useState<string | null>(null);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Login form state
  const [email, setEmail] = useState('principal@campus.os');
  const [password, setPassword] = useState('changeme');
  const [loginLoading, setLoginLoading] = useState(false);

  useEffect(() => {
    initApp();
  }, []);

  const initApp = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const healthData = await api.getHealth();
      setHealth(healthData);

      if (api.getToken()) {
        try {
          const userData = await api.getMe();
          setUser(userData);
          const dashboardData = await api.getDashboard();
          setDashboard(dashboardData);
        } catch {
          // Token expired or invalid
          api.setToken(null);
          setUser(null);
          setDashboard(null);
        }
      }
    } catch (err: any) {
      setError(err.message || 'Failed to connect to backend service');
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogin = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setLoginLoading(true);
    setError(null);
    try {
      await api.login(email, password);
      const userData = await api.getMe();
      setUser(userData);
      const dashboardData = await api.getDashboard();
      setDashboard(dashboardData);
      setActiveTab('dashboard');
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoginLoading(false);
    }
  };

  const handleLogout = () => {
    api.setToken(null);
    setUser(null);
    setDashboard(null);
    setActiveTab('dashboard');
  };

  const handleQuickLogin = (demoEmail: string) => {
    setEmail(demoEmail);
    setPassword('changeme');
    setIsLoading(true);
    api.login(demoEmail, 'changeme')
      .then(() => api.getMe())
      .then((userData) => {
        setUser(userData);
        return api.getDashboard();
      })
      .then((dashboardData) => {
        setDashboard(dashboardData);
        setIsLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setIsLoading(false);
      });
  };

  const handleInspectDecision = (decisionId: string) => {
    setSelectedDecisionId(decisionId);
    setActiveTab('inspector');
  };

  const handleLaunchHeroScenario = () => {
    setActiveTab('simulator');
  };

  return (
    <div className="app-layout">
      <Navbar
        user={user}
        health={health}
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        onLogout={handleLogout}
        onSwitchUser={handleQuickLogin}
      />

      <main className="main-content">
        {isLoading ? (
          <div className="loading-state">
            <Loader2 className="animate-spin text-primary" size={40} />
            <p>Connecting to Campus OS backend...</p>
          </div>
        ) : error && !user ? (
          <div className="error-card">
            <AlertCircle size={24} className="text-danger" />
            <div>
              <h3>Connection Error</h3>
              <p>{error}</p>
              <button onClick={initApp} className="btn-secondary">
                Retry Connection
              </button>
            </div>
          </div>
        ) : !user ? (
          <div className="login-wrapper">
            <div className="login-card">
              <div className="login-header">
                <div className="login-icon">
                  <KeyRound size={24} />
                </div>
                <h2>Sign in to Campus OS</h2>
                <p>ANVIL Multi-Agent Decision Support Platform</p>
              </div>

              {error && <div className="login-error">{error}</div>}

              <form onSubmit={handleLogin} className="login-form">
                <div className="form-group">
                  <label htmlFor="email">Email Address</label>
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="password">Password</label>
                  <input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>

                <button
                  type="submit"
                  disabled={loginLoading}
                  className="btn-submit"
                >
                  {loginLoading ? 'Signing in...' : 'Sign In'}
                </button>
              </form>

              <div className="quick-login">
                <p className="quick-login-title">Quick Demo Sign-in:</p>
                <div className="quick-login-grid">
                  <button
                    type="button"
                    onClick={() => handleQuickLogin('principal@campus.os')}
                    className="btn-demo"
                  >
                    Principal (Full Campus)
                  </button>
                  <button
                    type="button"
                    onClick={() => handleQuickLogin('hod.cs@campus.os')}
                    className="btn-demo"
                  >
                    HOD Computer Science
                  </button>
                  <button
                    type="button"
                    onClick={() => handleQuickLogin('hod.ec@campus.os')}
                    className="btn-demo"
                  >
                    HOD Electronics
                  </button>
                  <button
                    type="button"
                    onClick={() => handleQuickLogin('hod.me@campus.os')}
                    className="btn-demo"
                  >
                    HOD Mechanical
                  </button>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="app-page-wrapper">
            <ErrorBoundary>
              {activeTab === 'dashboard' && dashboard && (
                <DashboardPage
                  data={dashboard}
                  currentUser={user}
                  onRefresh={async () => {
                    setIsLoading(true);
                    try {
                      const refreshed = await api.getDashboard();
                      setDashboard(refreshed);
                    } catch (e: any) {
                      setError(e.message);
                    } finally {
                      setIsLoading(false);
                    }
                  }}
                  onLaunchHeroScenario={handleLaunchHeroScenario}
                  onInspectDecision={handleInspectDecision}
                  onInspectConflicts={() => setActiveTab('simulator')}
                  isLoading={isLoading}
                />
              )}

              {activeTab === 'simulator' && (
                <WhatIfSimulatorPage
                  currentUser={user}
                  onInspectDecision={handleInspectDecision}
                />
              )}

              {activeTab === 'inspector' && (
                <DecisionDetailPage
                  initialDecisionId={selectedDecisionId}
                  currentUser={user}
                  onNavigateToSimulator={() => setActiveTab('simulator')}
                />
              )}

              {activeTab === 'audit' && (
                <AuditLogPage
                  currentUser={user}
                  onInspectDecision={handleInspectDecision}
                />
              )}
            </ErrorBoundary>
          </div>
        )}
      </main>
    </div>
  );
}
