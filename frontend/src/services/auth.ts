import { API_BASE_URL } from './api';
import type { UserResponse } from './api';

export interface ActiveSession {
  id: string;
  created_at: string;
  expires_at: string;
  last_used_at: string | null;
}

export interface ExternalIdentity {
  id: string;
  provider: string;
  provider_subject: string;
  provider_email: string | null;
  provider_username: string | null;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  token_type: string;
  session_token?: string;
  refresh_token?: string;
}

export const authApi = {
  getMe: async (token: string): Promise<UserResponse> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!res.ok) throw new Error('Failed to fetch user profile');
    return res.json();
  },
  login: async (creds: { email: string; password?: string }): Promise<AuthTokens> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: creds.email, password: creds.password || '' })
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => null);
      throw new Error(errData?.detail || 'Login failed');
    }
    return res.json();
  },
  register: async (data: { email: string; password?: string }): Promise<UserResponse> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => null);
      throw new Error(errData?.detail || 'Registration failed');
    }
    return res.json();
  }
};


export const logout = async (): Promise<void> => {
  const refresh_token = sessionStorage.getItem('refresh_token');
  if (refresh_token) {
    try {
      await fetch(`${API_BASE_URL}/api/v1/auth/logout`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${sessionStorage.getItem('access_token')}`,
        },
        body: JSON.stringify({ refresh_token }),
      });
    } catch (e) {
      console.error('Logout error', e);
    }
  }
  sessionStorage.removeItem('access_token');
  sessionStorage.removeItem('refresh_token');
  sessionStorage.removeItem('session_token');
};

export const fetchSessions = async (): Promise<ActiveSession[]> => {
  const token = sessionStorage.getItem('access_token') || localStorage.getItem('cf_token');
  const res = await fetch(`${API_BASE_URL}/api/v1/auth/sessions`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Failed to fetch sessions');
  return res.json();
};

export const revokeSession = async (sessionId: string): Promise<void> => {
  const token = sessionStorage.getItem('access_token') || localStorage.getItem('cf_token');
  const res = await fetch(`${API_BASE_URL}/api/v1/auth/sessions/${sessionId}`, {
    method: 'DELETE',
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Failed to revoke session');
};

export const fetchIdentities = async (): Promise<ExternalIdentity[]> => {
  const token = sessionStorage.getItem('access_token') || localStorage.getItem('cf_token');
  const res = await fetch(`${API_BASE_URL}/api/v1/auth/identities`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Failed to fetch identities');
  return res.json();
};

export const unlinkIdentity = async (identityId: string): Promise<void> => {
  const token = sessionStorage.getItem('access_token') || localStorage.getItem('cf_token');
  const res = await fetch(`${API_BASE_URL}/api/v1/auth/identities/${identityId}`, {
    method: 'DELETE',
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Failed to unlink identity');
};
