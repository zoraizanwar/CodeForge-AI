"""
Centralized Thread-Safe Metrics Collector for CodeForge AI Step 14 Observability.
Collects operational, performance, agent, execution, Git/PR, AI Provider, and WebSocket metrics safely.
"""
import threading
import time
from typing import Dict, Any, List, Optional


class MetricsCollector:
    """
    In-memory thread-safe operational metrics tracker.
    Provides aggregated statistics for GET /metrics and system monitoring endpoints.
    """
    def __init__(self):
        self._lock = threading.Lock()
        
        # HTTP Metrics
        self.http_requests_total = 0
        self.http_duration_total_ms = 0.0
        self.http_status_codes: Dict[int, int] = {}
        self.http_4xx_count = 0
        self.http_5xx_count = 0

        # Job Metrics
        self.jobs_queued = 0
        self.jobs_running = 0
        self.jobs_completed = 0
        self.jobs_failed = 0
        self.jobs_cancelled = 0
        self.jobs_retry_count = 0
        self.jobs_stale_recovered = 0
        self.jobs_total_duration_ms = 0.0
        self.jobs_total_wait_ms = 0.0

        # Agent Metrics
        self.agent_runs_total = 0
        self.agent_runs_successful = 0
        self.agent_runs_failed = 0
        self.agent_runs_human_review = 0
        self.agent_durations_ms: Dict[str, float] = {
            "planner": 0.0,
            "engineer": 0.0,
            "reviewer": 0.0,
            "security": 0.0,
            "tester": 0.0,
            "repair": 0.0,
        }
        self.agent_repair_iterations = 0

        # Repository Metrics
        self.repositories_imported = 0
        self.indexing_success_count = 0
        self.indexing_failure_count = 0
        self.files_indexed_total = 0
        self.symbols_extracted_total = 0
        self.chunks_generated_total = 0
        self.embedding_ops_total = 0
        self.semantic_searches_total = 0

        # Execution Metrics
        self.executions_started = 0
        self.executions_passed = 0
        self.executions_failed = 0
        self.execution_timeouts = 0
        self.command_failures = 0
        self.execution_duration_total_ms = 0.0

        # Git/PR Metrics
        self.git_branches_created = 0
        self.git_commits_created = 0
        self.git_pushes_completed = 0
        self.github_prs_created = 0
        self.github_pr_failures = 0

        # AI Provider Metrics
        self.ai_requests_total = 0
        self.ai_success_total = 0
        self.ai_failures_total = 0
        self.ai_latency_total_ms = 0.0
        self.ai_model_usage: Dict[str, int] = {}

        # WebSocket Metrics
        self.ws_connections_total = 0
        self.ws_authenticated_total = 0
        self.ws_rejected_total = 0
        self.ws_disconnects_total = 0

    def record_http_request(self, status_code: int, duration_ms: float):
        with self._lock:
            self.http_requests_total += 1
            self.http_duration_total_ms += duration_ms
            self.http_status_codes[status_code] = self.http_status_codes.get(status_code, 0) + 1
            if 400 <= status_code < 500:
                self.http_4xx_count += 1
            elif status_code >= 500:
                self.http_5xx_count += 1

    def record_job_enqueue(self):
        with self._lock:
            self.jobs_queued += 1

    def record_job_start(self, wait_time_ms: float = 0.0):
        with self._lock:
            if self.jobs_queued > 0:
                self.jobs_queued -= 1
            self.jobs_running += 1
            self.jobs_total_wait_ms += wait_time_ms

    def record_job_finish(self, status: str, duration_ms: float = 0.0):
        with self._lock:
            if self.jobs_running > 0:
                self.jobs_running -= 1
            if status == "completed":
                self.jobs_completed += 1
            elif status == "failed":
                self.jobs_failed += 1
            elif status == "cancelled":
                self.jobs_cancelled += 1
            self.jobs_total_duration_ms += duration_ms

    def record_job_retry(self):
        with self._lock:
            self.jobs_retry_count += 1

    def record_stale_job_recovery(self, count: int = 1):
        with self._lock:
            self.jobs_stale_recovered += count

    def record_agent_run(self, final_status: str):
        with self._lock:
            self.agent_runs_total += 1
            if final_status == "completed" or final_status == "passed":
                self.agent_runs_successful += 1
            elif final_status == "failed":
                self.agent_runs_failed += 1
            elif final_status == "human_review_required":
                self.agent_runs_human_review += 1

    def record_agent_stage_duration(self, agent_name: str, duration_ms: float):
        with self._lock:
            clean_name = agent_name.lower().replace("_agent", "")
            self.agent_durations_ms[clean_name] = self.agent_durations_ms.get(clean_name, 0.0) + duration_ms

    def record_repair_iteration(self):
        with self._lock:
            self.agent_repair_iterations += 1

    def record_repo_imported(self):
        with self._lock:
            self.repositories_imported += 1

    def record_indexing_result(self, success: bool, files: int, symbols: int, chunks: int):
        with self._lock:
            if success:
                self.indexing_success_count += 1
            else:
                self.indexing_failure_count += 1
            self.files_indexed_total += files
            self.symbols_extracted_total += symbols
            self.chunks_generated_total += chunks

    def record_embedding_op(self, count: int = 1):
        with self._lock:
            self.embedding_ops_total += count

    def record_semantic_search(self):
        with self._lock:
            self.semantic_searches_total += 1

    def record_execution(self, status: str, duration_ms: float = 0.0, is_timeout: bool = False, command_failed: bool = False):
        with self._lock:
            self.executions_started += 1
            if status == "passed":
                self.executions_passed += 1
            elif status == "failed":
                self.executions_failed += 1
            if is_timeout:
                self.execution_timeouts += 1
            if command_failed:
                self.command_failures += 1
            self.execution_duration_total_ms += duration_ms

    def record_git_operation(self, op_type: str, success: bool = True):
        with self._lock:
            if op_type == "branch":
                self.git_branches_created += 1
            elif op_type == "commit":
                self.git_commits_created += 1
            elif op_type == "push":
                self.git_pushes_completed += 1
            elif op_type == "pull_request":
                if success:
                    self.github_prs_created += 1
                else:
                    self.github_pr_failures += 1

    def record_ai_provider_call(self, model: str, success: bool, latency_ms: float):
        with self._lock:
            self.ai_requests_total += 1
            if success:
                self.ai_success_total += 1
            else:
                self.ai_failures_total += 1
            self.ai_latency_total_ms += latency_ms
            self.ai_model_usage[model] = self.ai_model_usage.get(model, 0) + 1

    def record_websocket_connection(self, authenticated: bool, rejected: bool = False):
        with self._lock:
            self.ws_connections_total += 1
            if authenticated:
                self.ws_authenticated_total += 1
            if rejected:
                self.ws_rejected_total += 1

    def record_websocket_disconnect(self):
        with self._lock:
            self.ws_disconnects_total += 1

    def get_metrics_snapshot(self) -> Dict[str, Any]:
        """Returns safe, aggregated metrics snapshot dictionary."""
        with self._lock:
            avg_http_latency = (self.http_duration_total_ms / self.http_requests_total) if self.http_requests_total > 0 else 0.0
            avg_job_duration = (self.jobs_total_duration_ms / (self.jobs_completed + self.jobs_failed)) if (self.jobs_completed + self.jobs_failed) > 0 else 0.0
            avg_ai_latency = (self.ai_latency_total_ms / self.ai_requests_total) if self.ai_requests_total > 0 else 0.0

            return {
                "http": {
                    "request_count": self.http_requests_total,
                    "avg_latency_ms": round(avg_http_latency, 2),
                    "status_4xx_count": self.http_4xx_count,
                    "status_5xx_count": self.http_5xx_count,
                    "status_distribution": dict(self.http_status_codes),
                },
                "jobs": {
                    "queued": self.jobs_queued,
                    "running": self.jobs_running,
                    "completed": self.jobs_completed,
                    "failed": self.jobs_failed,
                    "cancelled": self.jobs_cancelled,
                    "retries": self.jobs_retry_count,
                    "stale_recovered": self.jobs_stale_recovered,
                    "avg_duration_ms": round(avg_job_duration, 2),
                },
                "agents": {
                    "runs_total": self.agent_runs_total,
                    "runs_successful": self.agent_runs_successful,
                    "runs_failed": self.agent_runs_failed,
                    "runs_human_review_required": self.agent_runs_human_review,
                    "durations_by_agent_ms": {k: round(v, 2) for k, v in self.agent_durations_ms.items()},
                    "repair_iterations_total": self.agent_repair_iterations,
                },
                "repositories": {
                    "imported_count": self.repositories_imported,
                    "indexing_success": self.indexing_success_count,
                    "indexing_failure": self.indexing_failure_count,
                    "files_indexed": self.files_indexed_total,
                    "symbols_extracted": self.symbols_extracted_total,
                    "chunks_generated": self.chunks_generated_total,
                    "embedding_operations": self.embedding_ops_total,
                    "semantic_searches": self.semantic_searches_total,
                },
                "executions": {
                    "started": self.executions_started,
                    "passed": self.executions_passed,
                    "failed": self.executions_failed,
                    "timeouts": self.execution_timeouts,
                    "command_failures": self.command_failures,
                    "total_duration_ms": round(self.execution_duration_total_ms, 2),
                },
                "git_and_pr": {
                    "branches_created": self.git_branches_created,
                    "commits_created": self.git_commits_created,
                    "pushes_completed": self.git_pushes_completed,
                    "prs_created": self.github_prs_created,
                    "pr_failures": self.github_pr_failures,
                },
                "ai_provider": {
                    "requests_total": self.ai_requests_total,
                    "success_total": self.ai_success_total,
                    "failures_total": self.ai_failures_total,
                    "avg_latency_ms": round(avg_ai_latency, 2),
                    "model_usage": dict(self.ai_model_usage),
                },
                "websockets": {
                    "connections_total": self.ws_connections_total,
                    "authenticated_total": self.ws_authenticated_total,
                    "rejected_total": self.ws_rejected_total,
                    "disconnects_total": self.ws_disconnects_total,
                }
            }


# Global singleton metrics collector instance
metrics_collector = MetricsCollector()
