import type {
  AuditListItem,
  DashboardData,
  DepartmentPublic,
  FacultyPublic,
  HealthResponse,
  OccurrenceEligibility,
  QueryResponse,
  SimulationRequest,
  SimulationResponse,
  User,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

class ApiClient {
  private token: string | null = null;

  constructor() {
    this.token = localStorage.getItem('campus_os_token');
  }

  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem('campus_os_token', token);
    } else {
      localStorage.removeItem('campus_os_token');
    }
  }

  getToken(): string | null {
    return this.token;
  }

  private authHeaders(): HeadersInit {
    const headers: HeadersInit = {};
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    return headers;
  }

  async getHealth(): Promise<HealthResponse> {
    const res = await fetch(`${API_BASE_URL}/health`);
    if (!res.ok) {
      throw new Error(`Health check failed: ${res.statusText}`);
    }
    return res.json();
  }

  async login(email: string, password: string): Promise<string> {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    const res = await fetch(`${API_BASE_URL}/auth/token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData.toString(),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(err.detail || 'Login failed');
    }

    const data = await res.json();
    this.setToken(data.access_token);
    return data.access_token;
  }

  async getMe(): Promise<User> {
    if (!this.token) {
      throw new Error('Not authenticated');
    }
    const res = await fetch(`${API_BASE_URL}/auth/me`, {
      headers: this.authHeaders(),
    });

    if (!res.ok) {
      if (res.status === 401) {
        this.setToken(null);
      }
      throw new Error(`Failed to fetch user profile: ${res.statusText}`);
    }

    return res.json();
  }

  async getDashboard(): Promise<DashboardData> {
    if (!this.token) {
      throw new Error('Not authenticated');
    }
    const res = await fetch(`${API_BASE_URL}/dashboard`, {
      headers: this.authHeaders(),
    });

    if (!res.ok) {
      if (res.status === 401) {
        this.setToken(null);
      }
      throw new Error(`Failed to fetch dashboard: ${res.statusText}`);
    }

    return res.json();
  }

  async getDepartments(): Promise<DepartmentPublic[]> {
    const res = await fetch(`${API_BASE_URL}/departments`, {
      headers: this.authHeaders(),
    });
    if (!res.ok) {
      throw new Error(`Failed to fetch departments: ${res.statusText}`);
    }
    return res.json();
  }

  async getFaculty(departmentId?: string): Promise<FacultyPublic[]> {
    const url = departmentId
      ? `${API_BASE_URL}/faculty?department_id=${encodeURIComponent(departmentId)}`
      : `${API_BASE_URL}/faculty`;
    const res = await fetch(url, {
      headers: this.authHeaders(),
    });
    if (!res.ok) {
      throw new Error(`Failed to fetch faculty: ${res.statusText}`);
    }
    return res.json();
  }

  async runSimulation(req: SimulationRequest): Promise<SimulationResponse> {
    const res = await fetch(`${API_BASE_URL}/simulation/run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...this.authHeaders(),
      },
      body: JSON.stringify(req),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Simulation failed' }));
      throw new Error(err.detail || 'Simulation execution failed');
    }
    return res.json();
  }

  async getSimulationHistory(limit: number = 30): Promise<AuditListItem[]> {
    const res = await fetch(`${API_BASE_URL}/simulation/history?limit=${limit}`, {
      headers: this.authHeaders(),
    });
    if (!res.ok) {
      throw new Error(`Failed to fetch simulation history: ${res.statusText}`);
    }
    return res.json();
  }

  async getDecisionDetail(decisionId: string): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/simulation/${decisionId}`, {
      headers: this.authHeaders(),
    });
    if (!res.ok) {
      throw new Error(`Failed to fetch decision details: ${res.statusText}`);
    }
    return res.json();
  }

  async approveDecision(decisionId: string): Promise<{ decision_id: string; decision_status: string; message: string }> {
    const res = await fetch(`${API_BASE_URL}/simulation/${decisionId}/approve`, {
      method: 'POST',
      headers: this.authHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Approval failed' }));
      throw new Error(err.detail || 'Failed to approve decision');
    }
    return res.json();
  }

  async getOccurrenceEligibility(occurrenceId: string): Promise<OccurrenceEligibility> {
    const res = await fetch(`${API_BASE_URL}/planner/eligibility/${occurrenceId}`, {
      headers: this.authHeaders(),
    });
    if (!res.ok) {
      throw new Error(`Failed to fetch candidate eligibility: ${res.statusText}`);
    }
    return res.json();
  }

  async getConflicts(targetDate?: string, departmentId?: string): Promise<any> {
    const params = new URLSearchParams();
    if (targetDate) params.append('date', targetDate);
    if (departmentId) params.append('department_id', departmentId);

    const query = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE_URL}/conflicts${query}`, {
      headers: this.authHeaders(),
    });
    if (!res.ok) {
      throw new Error(`Failed to fetch conflicts: ${res.statusText}`);
    }
    return res.json();
  }

  async getWorkload(weekDate?: string, departmentId?: string): Promise<any> {
    const params = new URLSearchParams();
    if (weekDate) params.append('week_date', weekDate);
    if (departmentId) params.append('department_id', departmentId);

    const query = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE_URL}/workload${query}`, {
      headers: this.authHeaders(),
    });
    if (!res.ok) {
      throw new Error(`Failed to fetch workload: ${res.statusText}`);
    }
    return res.json();
  }

  async query(queryText: string, context?: Record<string, any>): Promise<QueryResponse> {
    const res = await fetch(`${API_BASE_URL}/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...this.authHeaders(),
      },
      body: JSON.stringify({ query: queryText, context: context || null }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Query failed' }));
      throw new Error(err.detail || 'Natural language query execution failed');
    }
    return res.json();
  }
}

export const api = new ApiClient();
