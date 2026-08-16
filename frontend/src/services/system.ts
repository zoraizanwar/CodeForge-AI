/**
 * System Monitoring & Metrics API Client Service for CodeForge AI Step 14 Observability.
 */
import { API_BASE_URL, getAuthHeaders } from './api';

export interface SystemStatsResponse {
  timestamp: string;
  metrics: {
    http: {
      request_count: number;
      avg_latency_ms: number;
      status_4xx_count: number;
      status_5xx_count: number;
      status_distribution: Record<string, number>;
    };
    jobs: {
      queued: number;
      running: number;
      completed: number;
      failed: number;
      cancelled: number;
      retries: number;
      stale_recovered: number;
      avg_duration_ms: number;
    };
    agents: {
      runs_total: number;
      runs_successful: number;
      runs_failed: number;
      runs_human_review_required: number;
      durations_by_agent_ms: Record<string, number>;
      repair_iterations_total: number;
    };
    repositories: {
      imported_count: number;
      indexing_success: number;
      indexing_failure: number;
      files_indexed: number;
      symbols_extracted: number;
      chunks_generated: number;
      embedding_operations: number;
      semantic_searches: number;
    };
    executions: {
      started: number;
      passed: number;
      failed: number;
      timeouts: number;
      command_failures: number;
      total_duration_ms: number;
    };
    git_and_pr: {
      branches_created: number;
      commits_created: number;
      pushes_completed: number;
      prs_created: number;
      pr_failures: number;
    };
    ai_provider: {
      requests_total: number;
      success_total: number;
      failures_total: number;
      avg_latency_ms: number;
      model_usage: Record<string, number>;
    };
    websockets: {
      connections_total: number;
      authenticated_total: number;
      rejected_total: number;
      disconnects_total: number;
    };
  };
  user_stats: {
    repositories: number;
    tasks: number;
    jobs: number;
    multi_agent_runs: number;
    execution_success_rate: number;
    security_events: Array<{
      id: string;
      event_type: string;
      severity: string;
      request_id: string | null;
      created_at: string;
      metadata: Record<string, any> | null;
    }>;
  };
}

export async function fetchSystemStats(): Promise<SystemStatsResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/system/stats`, {
    headers: getAuthHeaders(),
  });

  if (!res.ok) {
    throw new Error('Failed to fetch system stats');
  }

  return res.json();
}
