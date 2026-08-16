import React, { useEffect, useState } from 'react';
import type { AgentRun } from '../services/agentRuns';
import { agentRunsApi } from '../services/agentRuns';
import { AgentStepTimeline } from './AgentStepTimeline';
import { ReviewFindings } from './ReviewFindings';
import { SecurityFindings } from './SecurityFindings';
import { Pause, RotateCcw, AlertTriangle, Cpu } from 'lucide-react';

interface AgentWorkflowProps {
  repoId: string;
  runId: string;
  onRunUpdated?: (run: AgentRun) => void;
}

export const AgentWorkflow: React.FC<AgentWorkflowProps> = ({ repoId, runId, onRunUpdated }) => {
  const [run, setRun] = useState<AgentRun | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchRun = async () => {
    try {
      const data = await agentRunsApi.getRun(repoId, runId);
      setRun(data);
      if (onRunUpdated) onRunUpdated(data);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to fetch run data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRun();

    const unsubscribe = agentRunsApi.connectRunStream(repoId, runId, (data) => {
      if (data.type === 'run_initial_state' && data.run) {
        setRun(data.run);
      } else {
        fetchRun();
      }
    });

    return () => unsubscribe();
  }, [repoId, runId]);

  const handleCancel = async () => {
    try {
      const updated = await agentRunsApi.cancelRun(repoId, runId);
      setRun(updated);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to cancel run.');
    }
  };

  const handleRetry = async () => {
    try {
      const updated = await agentRunsApi.retryRun(repoId, runId);
      setRun(updated);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to retry run.');
    }
  };

  if (loading) {
    return (
      <div className="p-6 bg-[#121319] border border-gray-800 rounded-xl text-center space-y-2">
        <Cpu className="w-6 h-6 text-indigo-400 animate-spin mx-auto" />
        <p className="text-xs text-gray-400">Loading Multi-Agent Workflow...</p>
      </div>
    );
  }

  if (!run) {
    return (
      <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-xs text-red-400">
        {errorMsg || 'Agent run not found.'}
      </div>
    );
  }

  const reviewerStep = run.steps.find((s) => s.agent_type === 'reviewer' && s.output);
  const securityStep = run.steps.find((s) => s.agent_type === 'security' && s.output);

  return (
    <div className="space-y-6">
      {/* Workflow Header Card */}
      <div className="p-5 bg-[#121319] border border-gray-800 rounded-xl space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-400">
              Multi-Agent Orchestrator
            </span>
            <h2 className="text-base font-bold text-gray-100 flex items-center gap-2">
              <Cpu className="w-5 h-5 text-indigo-400" />
              Stage: {run.workflow_stage}
            </h2>
          </div>

          <div className="flex items-center gap-2">
            {['queued', 'running', 'reviewing', 'testing', 'repairing'].includes(run.status) && (
              <button
                onClick={handleCancel}
                className="px-3 py-1.5 bg-red-500/20 hover:bg-red-500/30 text-red-400 border border-red-500/30 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition"
              >
                <Pause className="w-3.5 h-3.5" /> Cancel Workflow
              </button>
            )}

            {['failed', 'cancelled'].includes(run.status) && (
              <button
                onClick={handleRetry}
                className="px-3 py-1.5 bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-400 border border-indigo-500/30 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition"
              >
                <RotateCcw className="w-3.5 h-3.5" /> Retry Workflow
              </button>
            )}
          </div>
        </div>

        {/* Progress Bar */}
        <div className="space-y-1.5">
          <div className="flex justify-between text-xs text-gray-400">
            <span>Overall Progress</span>
            <span className="font-semibold text-gray-200">{run.overall_progress}%</span>
          </div>
          <div className="w-full h-2 bg-gray-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-emerald-500 transition-all duration-500"
              style={{ width: `${run.overall_progress}%` }}
            />
          </div>
        </div>

        {/* Status Callouts */}
        {run.status === 'human_review_required' && (
          <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg text-xs text-amber-400 space-y-2">
            <div className="flex items-center gap-2 font-bold text-sm">
              <AlertTriangle className="w-4 h-4 text-amber-400" /> Human Approval Gate Triggered
            </div>
            <p className="text-gray-300">
              {run.final_decision?.reason || 'All automated checks finished. Explicit human review is required before Git PR creation.'}
            </p>
          </div>
        )}
      </div>

      {/* Code Reviewer & Security Reviewer Findings Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {reviewerStep && (
          <ReviewFindings
            findings={reviewerStep.output?.findings || []}
            approved={reviewerStep.output?.approved ?? true}
            summary={reviewerStep.output?.summary || ''}
          />
        )}

        {securityStep && (
          <SecurityFindings
            findings={securityStep.output?.findings || []}
            passed={securityStep.output?.passed ?? true}
            hasCriticalOrHigh={securityStep.output?.has_critical_or_high ?? false}
            summary={securityStep.output?.summary || ''}
          />
        )}
      </div>

      {/* Step Timeline */}
      <AgentStepTimeline steps={run.steps} currentAgent={run.current_agent} />
    </div>
  );
};
