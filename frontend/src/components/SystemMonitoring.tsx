import React, { useEffect, useState } from 'react';
import { Activity, Server, Cpu, GitPullRequest, ShieldAlert, RefreshCw, Layers, CheckCircle2, Zap } from 'lucide-react';
import { fetchSystemStats, type SystemStatsResponse } from '../services/system';

export const SystemMonitoring: React.FC = () => {
  const [stats, setStats] = useState<SystemStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSystemStats();
      setStats(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load system monitoring stats');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStats();
    const interval = setInterval(loadStats, 15000); // Auto-refresh every 15s
    return () => clearInterval(interval);
  }, []);

  if (loading && !stats) {
    return (
      <div className="p-12 text-center text-gray-400 flex items-center justify-center gap-2">
        <RefreshCw className="w-5 h-5 animate-spin text-indigo-400" /> Loading system metrics & stats...
      </div>
    );
  }

  if (error && !stats) {
    return (
      <div className="p-6 max-w-7xl mx-auto text-center text-red-400 bg-red-950/20 border border-red-900/40 rounded-xl">
        {error}
      </div>
    );
  }

  const m = stats?.metrics;
  const userStats = stats?.user_stats;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6 text-gray-200">
      {/* Header */}
      <div className="flex justify-between items-center border-b border-gray-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2.5">
            <Activity className="w-7 h-7 text-indigo-400" />
            System Monitoring & Operational Statistics
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Real-time telemetry, API request metrics, background job queues, multi-agent performance, and security health.
          </p>
        </div>
        <button
          onClick={loadStats}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 text-sm bg-gray-800 hover:bg-gray-700 text-gray-200 rounded-md border border-gray-700 transition"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh Stats
        </button>
      </div>

      {/* Top Stat Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-gray-900/60 p-4 rounded-xl border border-gray-800/80 flex items-center gap-4">
          <div className="p-3 bg-indigo-950/60 text-indigo-400 rounded-lg border border-indigo-800/40">
            <Server className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs text-gray-400 uppercase font-mono block">HTTP Request Volume</span>
            <span className="text-2xl font-bold text-white">{m?.http.request_count || 0}</span>
            <span className="text-xs text-indigo-400 block font-mono">Avg Latency: {m?.http.avg_latency_ms || 0} ms</span>
          </div>
        </div>

        <div className="bg-gray-900/60 p-4 rounded-xl border border-gray-800/80 flex items-center gap-4">
          <div className="p-3 bg-blue-950/60 text-blue-400 rounded-lg border border-blue-800/40">
            <Cpu className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs text-gray-400 uppercase font-mono block">Active Job Queue</span>
            <span className="text-2xl font-bold text-white">{m?.jobs.running || 0} Running / {m?.jobs.queued || 0} Queued</span>
            <span className="text-xs text-blue-400 block font-mono">Completed: {m?.jobs.completed || 0}</span>
          </div>
        </div>

        <div className="bg-gray-900/60 p-4 rounded-xl border border-gray-800/80 flex items-center gap-4">
          <div className="p-3 bg-emerald-950/60 text-emerald-400 rounded-lg border border-emerald-800/40">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs text-gray-400 uppercase font-mono block">Execution Success Rate</span>
            <span className="text-2xl font-bold text-white">{userStats?.execution_success_rate || 100}%</span>
            <span className="text-xs text-emerald-400 block font-mono">Passed: {m?.executions.passed || 0}</span>
          </div>
        </div>

        <div className="bg-gray-900/60 p-4 rounded-xl border border-gray-800/80 flex items-center gap-4">
          <div className="p-3 bg-purple-950/60 text-purple-400 rounded-lg border border-purple-800/40">
            <GitPullRequest className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs text-gray-400 uppercase font-mono block">PRs & Git Pushes</span>
            <span className="text-2xl font-bold text-white">{m?.git_and_pr.prs_created || 0} PRs Opened</span>
            <span className="text-xs text-purple-400 block font-mono">Commits: {m?.git_and_pr.commits_created || 0}</span>
          </div>
        </div>
      </div>

      {/* Detailed Metrics Sections */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Multi-Agent Performance */}
        <div className="bg-gray-900/60 p-5 rounded-xl border border-gray-800/80 space-y-4">
          <h2 className="text-base font-semibold text-white flex items-center gap-2">
            <Layers className="w-5 h-5 text-indigo-400" /> Multi-Agent Workflow Observability
          </h2>
          <div className="grid grid-cols-3 gap-3 font-mono text-xs">
            <div className="bg-gray-950 p-3 rounded border border-gray-800">
              <span className="text-gray-400 block">TOTAL RUNS</span>
              <span className="text-lg font-bold text-white">{m?.agents.runs_total || 0}</span>
            </div>
            <div className="bg-gray-950 p-3 rounded border border-gray-800">
              <span className="text-gray-400 block">SUCCESSFUL</span>
              <span className="text-lg font-bold text-emerald-400">{m?.agents.runs_successful || 0}</span>
            </div>
            <div className="bg-gray-950 p-3 rounded border border-gray-800">
              <span className="text-gray-400 block">HUMAN REVIEW</span>
              <span className="text-lg font-bold text-amber-400">{m?.agents.runs_human_review_required || 0}</span>
            </div>
          </div>
          <div>
            <span className="text-xs font-mono text-gray-400 mb-2 block">AGENT STAGE DURATIONS (ACCUMULATED MS)</span>
            <div className="space-y-1.5 font-mono text-xs">
              {Object.entries(m?.agents.durations_by_agent_ms || {}).map(([agent, duration]) => (
                <div key={agent} className="flex justify-between items-center bg-gray-950 px-3 py-1.5 rounded border border-gray-800">
                  <span className="text-indigo-300 capitalize">{agent} Agent</span>
                  <span className="text-gray-400">{duration} ms</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Repository & AI Provider Telemetry */}
        <div className="bg-gray-900/60 p-5 rounded-xl border border-gray-800/80 space-y-4">
          <h2 className="text-base font-semibold text-white flex items-center gap-2">
            <Zap className="w-5 h-5 text-indigo-400" /> AI Provider & Repository Intelligence
          </h2>
          <div className="grid grid-cols-2 gap-3 font-mono text-xs">
            <div className="bg-gray-950 p-3 rounded border border-gray-800">
              <span className="text-gray-400 block">AI REQUESTS TOTAL</span>
              <span className="text-lg font-bold text-white">{m?.ai_provider.requests_total || 0}</span>
              <span className="text-gray-500 block mt-1">Avg Latency: {m?.ai_provider.avg_latency_ms || 0}ms</span>
            </div>
            <div className="bg-gray-950 p-3 rounded border border-gray-800">
              <span className="text-gray-400 block">INDEXED REPOSITORIES</span>
              <span className="text-lg font-bold text-white">{userStats?.repositories || 0}</span>
              <span className="text-gray-500 block mt-1">Indexed Files: {m?.repositories.files_indexed || 0}</span>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 font-mono text-xs">
            <div className="bg-gray-950 p-3 rounded border border-gray-800">
              <span className="text-gray-400 block">SYMBOLS EXTRACTED</span>
              <span className="text-md font-bold text-indigo-300">{m?.repositories.symbols_extracted || 0}</span>
            </div>
            <div className="bg-gray-950 p-3 rounded border border-gray-800">
              <span className="text-gray-400 block">SEMANTIC SEARCHES</span>
              <span className="text-md font-bold text-indigo-300">{m?.repositories.semantic_searches || 0}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Security Events */}
      <div className="bg-gray-900/60 p-5 rounded-xl border border-gray-800/80 space-y-3">
        <h2 className="text-base font-semibold text-white flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-amber-400" /> Security Audit Telemetry
        </h2>
        {userStats?.security_events && userStats.security_events.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono text-gray-300">
              <thead className="bg-gray-950 text-gray-400 border-b border-gray-800">
                <tr>
                  <th className="py-2 px-3">Timestamp</th>
                  <th className="py-2 px-3">Security Event</th>
                  <th className="py-2 px-3">Severity</th>
                  <th className="py-2 px-3">Request ID</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60">
                {userStats.security_events.map((ev) => (
                  <tr key={ev.id} className="hover:bg-gray-800/40">
                    <td className="py-2 px-3 text-gray-400">{new Date(ev.created_at).toLocaleString()}</td>
                    <td className="py-2 px-3 text-amber-400 font-semibold">{ev.event_type}</td>
                    <td className="py-2 px-3 text-red-400 uppercase font-bold">{ev.severity}</td>
                    <td className="py-2 px-3 text-gray-400">{ev.request_id || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-6 text-center text-xs text-gray-500 bg-gray-950/40 rounded border border-gray-800">
            No recent security violations detected. Security posture intact.
          </div>
        )}
      </div>
    </div>
  );
};
