import { API_BASE_URL, getAuthHeaders, getAuthToken } from './api';

export interface AgentJob {
  id: string;
  user_id: string;
  repository_id: string;
  task_id?: string;
  job_type: 'analysis' | 'agent_task' | 'execution' | 'repair' | 'pull_request';
  status: 'queued' | 'running' | 'cancelling' | 'cancelled' | 'completed' | 'failed' | 'retrying';
  progress: number;
  current_stage: string;
  attempt_count: number;
  max_attempts: number;
  priority: number;
  payload?: any;
  result?: any;
  error_message?: string;
  started_at?: string;
  completed_at?: string;
  created_at: string;
  updated_at: string;
}

export interface JobCancelResponse {
  job_id: string;
  status: string;
  message: string;
}

export const jobsApi = {
  listJobs: async (repositoryId?: string, jobType?: string, status?: string): Promise<AgentJob[]> => {
    const params = new URLSearchParams();
    if (repositoryId) params.append('repository_id', repositoryId);
    if (jobType) params.append('job_type', jobType);
    if (status) params.append('status', status);

    const res = await fetch(`${API_BASE_URL}/api/v1/jobs?${params.toString()}`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      throw new Error('Failed to fetch jobs.');
    }
    return res.json();
  },

  getJob: async (jobId: string): Promise<AgentJob> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/jobs/${jobId}`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      throw new Error('Failed to fetch job details.');
    }
    return res.json();
  },

  cancelJob: async (jobId: string): Promise<JobCancelResponse> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/jobs/${jobId}/cancel`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to cancel job.');
    }
    return res.json();
  },

  retryJob: async (jobId: string): Promise<AgentJob> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/jobs/${jobId}/retry`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to retry job.');
    }
    return res.json();
  },

  connectJobStream: (
    jobId: string,
    onUpdate: (job: AgentJob, message?: string) => void,
    onError?: (err: any) => void,
    onClose?: () => void
  ): () => void => {
    const token = getAuthToken();
    if (!token) {
      if (onError) onError(new Error('Unauthenticated WebSocket connection attempt.'));
      return () => {};
    }

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = API_BASE_URL.replace(/^https?:\/\//, '');
    const wsUrl = `${wsProtocol}//${host}/api/v1/jobs/${jobId}/stream?token=${encodeURIComponent(token)}`;

    let ws: WebSocket | null = null;
    let isDisposed = false;

    const connect = () => {
      if (isDisposed) return;
      ws = new WebSocket(wsUrl);

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'job_initial_state' || data.type === 'job_update') {
            if (data.job) {
              onUpdate(data.job, data.message);
            }
          } else if (data.type === 'error') {
            if (onError) onError(new Error(data.message));
          }
        } catch (err) {
          console.error('Failed to parse WebSocket job message:', err);
        }
      };

      ws.onerror = (err) => {
        if (onError) onError(err);
      };

      ws.onclose = () => {
        if (onClose) onClose();
        if (!isDisposed) {
          // Automatic reconnect retry after 3 seconds if not completed
          setTimeout(connect, 3000);
        }
      };
    };

    connect();

    return () => {
      isDisposed = true;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }
};
