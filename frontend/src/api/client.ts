import type { DashboardData, HealthResponse, User } from '../types';

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
      headers: {
        Authorization: `Bearer ${this.token}`,
      },
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
      headers: {
        Authorization: `Bearer ${this.token}`,
      },
    });

    if (!res.ok) {
      if (res.status === 401) {
        this.setToken(null);
      }
      throw new Error(`Failed to fetch dashboard: ${res.statusText}`);
    }

    return res.json();
  }
}

export const api = new ApiClient();

