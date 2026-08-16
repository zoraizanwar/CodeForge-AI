import { API_BASE_URL, getAuthHeaders } from './api';

export interface ImplementationPlan {
  task_summary: string;
  architecture_understanding: string;
  relevant_files: string[];
  relevant_symbols: string[];
  proposed_changes: string[];
  dependencies_affected: string[];
  tests: string[];
  implementation_order: string[];
  risks: string[];
}

export interface FileChange {
  file_path: string;
  operation: 'create' | 'modify' | 'delete';
  original_content?: string;
  proposed_content: string;
  explanation: string;
  confidence: number;
  diff: string;
}

export interface AgentTask {
  id: string;
  user_id: string;
  repository_id: string;
  task_description: string;
  status: 'pending' | 'analyzing' | 'planning' | 'generating' | 'ready_for_review' | 'approved' | 'executing' | 'execution_failed' | 'repairing' | 'repair_ready' | 'execution_passed' | 'pr_ready' | 'pr_created' | 'failed' | 'human_review_required';
  is_approved?: boolean;
  approved_patch_hash?: string;
  approved_at?: string;
  plan?: ImplementationPlan;
  files_analyzed?: string[];
  files_to_modify?: string[];
  error_message?: string;
  created_at: string;
  updated_at: string;
  completed_at?: string;
}

export interface AgentTaskChangesResponse {
  task_id: string;
  status: string;
  changes: FileChange[];
  files_to_modify: string[];
}

export interface CommandResult {
  command: string;
  exit_code: number;
  stdout: string;
  stderr: string;
  duration_seconds: number;
}

export interface TestSummary {
  passed: boolean;
  tests_run: number;
  tests_passed: number;
  tests_failed: number;
  tests_skipped: number;
  duration_seconds: number;
  commands: string[];
  failures: string[];
}

export interface AgentExecution {
  id: string;
  task_id: string;
  status: 'pending' | 'preparing' | 'applying' | 'testing' | 'passed' | 'failed' | 'cancelled';
  workspace_path: string;
  command_results?: CommandResult[];
  test_summary?: TestSummary;
  stdout: string;
  stderr: string;
  exit_code?: number;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

export interface GitOperation {
  id: string;
  repository_id: string;
  task_id: string;
  execution_id?: string;
  user_id: string;
  operation_type: string;
  status: 'pending' | 'preparing' | 'applying' | 'committing' | 'pushing' | 'creating_pr' | 'completed' | 'failed' | 'cancelled';
  branch_name: string;
  commit_sha?: string;
  remote_branch?: string;
  pull_request_number?: number;
  pull_request_url?: string;
  commit_message?: string;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

export interface AgentIteration {
  id: string;
  task_id: string;
  iteration_number: number;
  trigger_execution_id?: string;
  status: 'analyzing' | 'planning' | 'generating' | 'validating' | 'executing' | 'passed' | 'failed' | 'stopped';
  failure_category?: string;
  failure_summary?: string;
  root_cause?: string;
  plan?: any;
  patch_hash?: string;
  execution_id?: string;
  files_changed?: FileChange[];
  error_message?: string;
  started_at?: string;
  completed_at?: string;
  created_at: string;
}

export const agentApi = {
  createTask: async (repoId: string, task: string): Promise<AgentTask> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/agent/tasks`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify({ task }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to submit agent task.');
    }
    return res.json();
  },

  getTasks: async (repoId: string): Promise<AgentTask[]> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/agent/tasks`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      throw new Error('Failed to fetch agent tasks.');
    }
    return res.json();
  },

  getTask: async (repoId: string, taskId: string): Promise<AgentTask> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/agent/tasks/${taskId}`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      throw new Error('Failed to fetch task status.');
    }
    return res.json();
  },

  getPlan: async (repoId: string, taskId: string): Promise<ImplementationPlan> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/agent/tasks/${taskId}/plan`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      throw new Error('Failed to fetch implementation plan.');
    }
    return res.json();
  },

  getChanges: async (repoId: string, taskId: string): Promise<AgentTaskChangesResponse> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/agent/tasks/${taskId}/changes`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      throw new Error('Failed to fetch generated changes.');
    }
    return res.json();
  },

  executeTask: async (repoId: string, taskId: string): Promise<AgentExecution> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/agent/tasks/${taskId}/execute`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to trigger task execution.');
    }
    return res.json();
  },

  getExecutions: async (repoId: string, taskId: string): Promise<AgentExecution[]> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/agent/tasks/${taskId}/executions`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      throw new Error('Failed to fetch execution history.');
    }
    return res.json();
  },

  getExecution: async (repoId: string, taskId: string, executionId: string): Promise<AgentExecution> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/agent/tasks/${taskId}/executions/${executionId}`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      throw new Error('Failed to fetch execution details.');
    }
    return res.json();
  },

  approveTask: async (repoId: string, taskId: string): Promise<AgentTask> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/agent/tasks/${taskId}/approve`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to approve task.');
    }
    return res.json();
  },

  createPullRequest: async (repoId: string, taskId: string): Promise<GitOperation> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/agent/tasks/${taskId}/pull-request`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to create Pull Request.');
    }
    return res.json();
  },

  getGitOperations: async (repoId: string, taskId: string): Promise<GitOperation[]> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/agent/tasks/${taskId}/git-operations`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      throw new Error('Failed to fetch Git operations.');
    }
    return res.json();
  },

  getPullRequest: async (repoId: string, taskId: string): Promise<GitOperation> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/agent/tasks/${taskId}/pull-request`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      throw new Error('Failed to fetch Pull Request status.');
    }
    return res.json();
  },

  triggerRepair: async (repoId: string, taskId: string): Promise<AgentTask> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/agent/tasks/${taskId}/repair`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to trigger repair loop.');
    }
    return res.json();
  },

  getIterations: async (repoId: string, taskId: string): Promise<AgentIteration[]> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/agent/tasks/${taskId}/iterations`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      throw new Error('Failed to fetch repair iterations.');
    }
    return res.json();
  },

  getIteration: async (repoId: string, taskId: string, iterationId: string): Promise<AgentIteration> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/agent/tasks/${taskId}/iterations/${iterationId}`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      throw new Error('Failed to fetch iteration details.');
    }
    return res.json();
  },

  retryIteration: async (repoId: string, taskId: string, iterationId: string): Promise<AgentTask> => {
    const res = await fetch(`${API_BASE_URL}/api/v1/repositories/${repoId}/agent/tasks/${taskId}/iterations/${iterationId}/retry`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to retry iteration.');
    }
    return res.json();
  }
};
