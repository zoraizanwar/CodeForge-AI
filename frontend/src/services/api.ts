export const API_BASE_URL = import.meta.env.VITE_API_URL || '';

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export interface ReadyResponse {
  status: string;
  services: {
    database: string;
  };
}

export interface InfoResponse {
  version: string;
  name: string;
  description: string;
}

export interface UserResponse {
  id: string;
  email: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export const getAuthToken = (): string | null => {
  return localStorage.getItem('cf_token') || sessionStorage.getItem('access_token');
};


export const getAuthHeaders = (): HeadersInit => {
  const token = getAuthToken();
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

export const api = {
  getHealth: async (): Promise<HealthResponse> => {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.statusText}`);
    }
    return response.json();
  },

  getReady: async (): Promise<ReadyResponse> => {
    const response = await fetch(`${API_BASE_URL}/ready`);
    if (!response.ok) {
      throw new Error(`Readiness check failed: ${response.statusText}`);
    }
    return response.json();
  },

  getV1Info: async (): Promise<InfoResponse> => {
    const response = await fetch(`${API_BASE_URL}/api/v1/info`, {
      headers: {
        ...getAuthHeaders(),
      },
    });
    if (!response.ok) {
      throw new Error(`API V1 Info fetch failed: ${response.statusText}`);
    }
    return response.json();
  }
};
