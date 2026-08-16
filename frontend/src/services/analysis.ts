/**
 * Frontend API client for repository intelligence (Step 6).
 */

import { API_BASE_URL, getAuthHeaders } from './api';

// ─── Types ────────────────────────────────────────────────────────────────

export interface AnalysisStatus {
  id: string;
  repository_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  architecture_summary: string | null;
  entry_points: string[] | null;
  dependencies_parsed: Record<string, string> | null;
  frameworks: string[] | null;
  last_analyzed_at: string | null;
  error_message: string | null;
}

export interface SymbolItem {
  id: string;
  name: string;
  type: 'class' | 'function' | 'method' | 'route' | 'import';
  file_path: string;
  line_number: number;
  end_line_number: number | null;
  metadata: Record<string, unknown> | null;
}

export interface DependenciesData {
  repository_id: string;
  dependencies: Record<string, string>;
  frameworks: string[];
}

export interface SearchResultItem {
  chunk_id: string;
  file_path: string;
  language: string;
  start_line: number;
  end_line: number;
  content: string;
  symbol_name: string | null;
  score: number | null;
}

export interface SearchResponse {
  query: string;
  results: SearchResultItem[];
  total: number;
}

// ─── Helper ───────────────────────────────────────────────────────────────

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      message = err.detail || err.message || message;
    } catch (_) {}
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

// ─── API Functions ────────────────────────────────────────────────────────

export const analysisApi = {
  /** GET /api/v1/repositories/{repo_id}/analysis */
  getAnalysis: async (repoId: string): Promise<AnalysisStatus> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/analysis`, {
      headers: {
        ...getAuthHeaders(),
      },
    });
    return handleResponse<AnalysisStatus>(res);
  },

  /** GET /api/v1/repositories/{repo_id}/symbols */
  getSymbols: async (
    repoId: string,
    options?: { symbolType?: string; limit?: number; offset?: number }
  ): Promise<SymbolItem[]> => {
    const params = new URLSearchParams();
    if (options?.symbolType) params.set('symbol_type', options.symbolType);
    if (options?.limit != null) params.set('limit', String(options.limit));
    if (options?.offset != null) params.set('offset', String(options.offset));

    const url = `${API_BASE_URL}/api/v1/repositories/${repoId}/symbols${params.size > 0 ? '?' + params : ''}`;
    const res = await fetch(url, {
      headers: {
        ...getAuthHeaders(),
      },
    });
    return handleResponse<SymbolItem[]>(res);
  },

  /** GET /api/v1/repositories/{repo_id}/dependencies */
  getDependencies: async (repoId: string): Promise<DependenciesData> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/dependencies`, {
      headers: {
        ...getAuthHeaders(),
      },
    });
    return handleResponse<DependenciesData>(res);
  },

  /** POST /api/v1/repositories/{repo_id}/analyze */
  triggerAnalysis: async (repoId: string): Promise<{ message: string; status: string }> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/analyze`, {
      method: 'POST',
      headers: {
        ...getAuthHeaders(),
      },
    });
    return handleResponse<{ message: string; status: string }>(res);
  },

  /** POST /api/v1/repositories/{repo_id}/search */
  searchCode: async (
    repoId: string,
    query: string,
    topK: number = 10
  ): Promise<SearchResponse> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify({ query, top_k: topK }),
    });
    return handleResponse<SearchResponse>(res);
  },
};
