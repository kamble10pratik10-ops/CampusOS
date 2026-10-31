import { useEffect, useState } from 'react';
import { api } from './api/client';
import { Navbar } from './components/Navbar';
import { DashboardPage } from './pages/DashboardPage';
import type { DashboardData, HealthResponse, User } from './types';
import { KeyRound, AlertCircle, Loader2 } from 'lucide-react';
import './index.css';

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
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
  };

  const handleQuickLogin = (demoEmail: string) => {
    setEmail(demoEmail);
    setPassword('changeme');
    setTimeout(() => {
      api.login(demoEmail, 'changeme')
        .then(() => api.getMe())
        .then(userData => {
          setUser(userData);
          return api.getDashboard();
        })
        .then(dashboardData => {
          setDashboard(dashboardData);
        })
        .catch(err => setError(err.message));
    }, 50);
  };

  return (
    <div className="app-layout">
      <Navbar user={user} health={health} onLogout={handleLogout} />

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
                <p>ANVIL Decision Support Platform</p>
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
                    Principal
                  </button>
                  <button
                    type="button"
                    onClick={() => handleQuickLogin('hod.cs@campus.os')}
                    className="btn-demo"
                  >
                    HOD (CS)
                  </button>
                  <button
                    type="button"
                    onClick={() => handleQuickLogin('hod.ec@campus.os')}
                    className="btn-demo"
                  >
                    HOD (EC)
                  </button>
                  <button
                    type="button"
                    onClick={() => handleQuickLogin('hod.me@campus.os')}
                    className="btn-demo"
                  >
                    HOD (ME)
                  </button>
                </div>
              </div>
            </div>
          </div>
        ) : dashboard ? (
          <DashboardPage
            data={dashboard}
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
            isLoading={isLoading}
          />
        ) : null}
      </main>
    </div>
  );
}
