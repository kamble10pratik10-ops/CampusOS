import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error in component tree:', error, errorInfo);
  }

  public handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="card error-card" style={{ margin: '2rem auto', maxWidth: '800px', padding: '2rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1rem' }}>
            <AlertTriangle size={32} className="text-danger" />
            <div>
              <h3 style={{ margin: 0, fontSize: '1.25rem', color: '#f87171' }}>
                {this.props.fallbackTitle || 'A rendering error occurred'}
              </h3>
              <p style={{ margin: '0.25rem 0 0', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                Campus OS encountered an unexpected UI error.
              </p>
            </div>
          </div>

          <div
            style={{
              backgroundColor: 'rgba(0, 0, 0, 0.4)',
              padding: '1rem',
              borderRadius: '8px',
              fontFamily: 'monospace',
              fontSize: '0.85rem',
              color: '#fca5a5',
              marginBottom: '1.5rem',
              overflowX: 'auto',
            }}
          >
            {this.state.error?.message || 'Unknown error'}
          </div>

          <div style={{ display: 'flex', gap: '1rem' }}>
            <button onClick={this.handleReset} className="btn-primary">
              <RefreshCw size={16} />
              <span>Retry Rendering</span>
            </button>
            <button onClick={() => window.location.reload()} className="btn-secondary">
              <span>Reload Page</span>
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
