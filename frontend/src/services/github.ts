import { API_BASE_URL, getAuthHeaders } from './api';

export interface GitHubStatusResponse {
  connected: boolean;
  github_login?: string;
  github_account_type?: string;
}

export interface GitHubOwner {
  id: number;
  login: string;
  type: string;
  avatar_url?: string;
}

export interface GitHubRepository {
  id: number;
  name: string;
  full_name: string;
  private: boolean;
  html_url: string;
  default_branch: string;
  owner: GitHubOwner;
}

export interface GitHubRepositoriesResponse {
  total_count: number;
  repositories: GitHubRepository[];
}

export const githubApi = {
  connectGitHub: async (): Promise<{ url: string }> => {
    const response = await fetch(`${API_BASE_URL}/api/v1/github/connect`, {
      headers: {
        ...getAuthHeaders(),
      },
    });
    if (!response.ok) {
      throw new Error(`Failed to generate GitHub connection link: ${response.statusText}`);
    }
    return response.json();
  },

  getGitHubStatus: async (): Promise<GitHubStatusResponse> => {
    const response = await fetch(`${API_BASE_URL}/api/v1/github/status`, {
      headers: {
        ...getAuthHeaders(),
      },
    });
    if (!response.ok) {
      throw new Error(`Failed to retrieve GitHub status: ${response.statusText}`);
    }
    return response.json();
  },

  getRepositories: async (page = 1, perPage = 30): Promise<GitHubRepositoriesResponse> => {
    const response = await fetch(
      `${API_BASE_URL}/api/v1/github/repositories?page=${page}&per_page=${perPage}`,
      {
        headers: {
          ...getAuthHeaders(),
        },
      }
    );
    if (!response.ok) {
      throw new Error(`Failed to retrieve repository listings: ${response.statusText}`);
    }
    return response.json();
  },

  syncGitHub: async (installationId?: number): Promise<GitHubStatusResponse> => {
    const response = await fetch(`${API_BASE_URL}/api/v1/github/sync`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify(installationId ? { installation_id: installationId } : {}),
    });
    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || `Failed to sync GitHub installation: ${response.statusText}`);
    }
    return response.json();
  },

  disconnectGitHub: async (): Promise<{ status: string; message: string }> => {

    const response = await fetch(`${API_BASE_URL}/api/v1/github/disconnect`, {
      method: 'DELETE',
      headers: {
        ...getAuthHeaders(),
      },
    });
    if (!response.ok) {
      throw new Error(`Failed to disconnect GitHub account: ${response.statusText}`);
    }
    return response.json();
  },
};
