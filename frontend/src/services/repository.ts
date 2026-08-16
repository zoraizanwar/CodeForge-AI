import { API_BASE_URL, getAuthHeaders } from './api';
export { API_BASE_URL };

export interface RepositoryResponse {
  id: string;
  github_repo_id: number;
  name: string;
  full_name: string;
  owner: string;
  default_branch: string;
  status: 'importing' | 'indexed' | 'failed';
  error_message?: string;
  languages?: Record<string, number>;
  frameworks?: string[];
  dependency_files?: string[];
  last_indexed_at?: string;
  created_at: string;
  updated_at: string;
}

export interface FileTreeItem {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
  children?: FileTreeItem[];
}

export interface FileContentResponse {
  name: string;
  path: string;
  size: number;
  content: string;
}

export const repositoryApi = {
  listRepositories: async (): Promise<RepositoryResponse[]> => {
    const response = await fetch(`${API_BASE_URL}/api/v1/repositories/`, {
      headers: {
        ...getAuthHeaders(),
      },
    });
    if (!response.ok) {
      throw new Error(`Failed to fetch connected repositories list: ${response.statusText}`);
    }
    return response.json();
  },

  importRepository: async (githubRepoId: number): Promise<RepositoryResponse> => {
    const response = await fetch(`${API_BASE_URL}/api/v1/repositories/import`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify({ github_repo_id: githubRepoId }),
    });
    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || `Failed to initiate repository import: ${response.statusText}`);
    }
    return response.json();
  },

  getRepository: async (repoId: string): Promise<RepositoryResponse> => {
    const response = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}`, {
      headers: {
        ...getAuthHeaders(),
      },
    });
    if (!response.ok) {
      throw new Error(`Failed to fetch repository metadata: ${response.statusText}`);
    }
    return response.json();
  },

  getRepositoryTree: async (repoId: string): Promise<FileTreeItem[]> => {
    const response = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/tree`, {
      headers: {
        ...getAuthHeaders(),
      },
    });
    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || `Failed to fetch file tree list: ${response.statusText}`);
    }
    return response.json();
  },

  readRepositoryFile: async (repoId: string, path: string): Promise<FileContentResponse> => {
    const encodedPath = encodeURIComponent(path);
    const response = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/file?path=${encodedPath}`, {
      headers: {
        ...getAuthHeaders(),
      },
    });
    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || `Failed to read file contents: ${response.statusText}`);
    }
    return response.json();
  },

  reindexRepository: async (repoId: string): Promise<RepositoryResponse> => {
    const response = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/index`, {
      method: 'POST',
      headers: {
        ...getAuthHeaders(),
      },
    });
    if (!response.ok) {
      throw new Error(`Failed to trigger codebase reindexing: ${response.statusText}`);
    }
    return response.json();
  },

  deleteRepository: async (repoId: string): Promise<{ status: string; message: string }> => {
    const response = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}`, {
      method: 'DELETE',
      headers: {
        ...getAuthHeaders(),
      },
    });
    if (!response.ok) {
      throw new Error(`Failed to delete repository workspace: ${response.statusText}`);
    }
    return response.json();
  },
};
