import { getAuthHeaders, getAuthToken, API_BASE_URL } from './api';

export interface AgentRunStep {
  id: string;
  run_id: string;
  agent_type: 'planner' | 'engineer' | 'reviewer' | 'tester' | 'security' | 'repair' | 'orchestrator';
  status: 'pending' | 'running' | 'passed' | 'failed' | 'review_needed' | 'cancelled';
  input_context?: Record<string, any>;
  output?: Record<string, any>;
  confidence?: number;
  job_id?: string;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

export interface AgentRun {
  id: string;
  user_id: string;
  repository_id: string;
  task_id?: string;
  parent_job_id?: string;
  status: 'pending' | 'running' | 'reviewing' | 'testing' | 'repairing' | 'approved' | 'rejected' | 'failed' | 'completed' | 'human_review_required' | 'cancelled';
  current_agent?: string;
  workflow_stage: string;
  overall_progress: number;
  final_decision?: Record<string, any>;
  error_message?: string;
  started_at?: string;
  completed_at?: string;
  created_at: string;
  updated_at: string;
  steps: AgentRunStep[];
}

export const agentRunsApi = {
  startRun: async (repoId: string, taskDescription: string, taskId?: string): Promise<AgentRun> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/agent/runs`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify({ task_description: taskDescription, task_id: taskId }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to start multi-agent run.');
    }
    return res.json();
  },

  listRuns: async (repoId: string): Promise<AgentRun[]> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/agent/runs`, {
      headers: { ...getAuthHeaders() },
    });
    if (!res.ok) {
      throw new Error('Failed to list agent runs.');
    }
    return res.json();
  },

  getRun: async (repoId: string, runId: string): Promise<AgentRun> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/agent/runs/${runId}`, {
      headers: { ...getAuthHeaders() },
    });
    if (!res.ok) {
      throw new Error('Failed to get agent run details.');
    }
    return res.json();
  },

  getRunSteps: async (repoId: string, runId: string): Promise<AgentRunStep[]> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/agent/runs/${runId}/steps`, {
      headers: { ...getAuthHeaders() },
    });
    if (!res.ok) {
      throw new Error('Failed to list agent run steps.');
    }
    return res.json();
  },

  cancelRun: async (repoId: string, runId: string): Promise<AgentRun> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/agent/runs/${runId}/cancel`, {
      method: 'POST',
      headers: { ...getAuthHeaders() },
    });
    if (!res.ok) {
      throw new Error('Failed to cancel agent run.');
    }
    return res.json();
  },

  retryRun: async (repoId: string, runId: string): Promise<AgentRun> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/agent/runs/${runId}/retry`, {
      method: 'POST',
      headers: { ...getAuthHeaders() },
    });
    if (!res.ok) {
      throw new Error('Failed to retry agent run.');
    }
    return res.json();
  },

  connectRunStream: (repoId: string, runId: string, onUpdate: (data: any) => void): (() => void) => {
    const token = getAuthToken();
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = API_BASE_URL.replace(/^https?:\/\//, '');
    const url = `${wsProtocol}//${host}/api/v1/repositories/${repoId}/agent/runs/${runId}/stream?token=${encodeURIComponent(token || '')}`;

    const ws = new WebSocket(url);

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        onUpdate(payload);
      } catch (err) {
        console.error('Failed to parse run WebSocket message:', err);
      }
    };

    return () => {
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
    };
  },
};
