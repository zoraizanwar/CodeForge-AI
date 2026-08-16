import React, { useState, useEffect } from 'react';
import { jobsApi } from '../services/jobs';
import type { AgentJob } from '../services/jobs';
import {
  Activity,
  CheckCircle2,
  XCircle,
  Clock,
  RefreshCw,
  RotateCcw,
  Ban,
  Layers,
  Wifi,
  WifiOff,
  AlertTriangle
} from 'lucide-react';

interface JobMonitorProps {
  jobId: string;
  onJobCompleted?: (job: AgentJob) => void;
  onJobCancelled?: (job: AgentJob) => void;
}

export const JobMonitor: React.FC<JobMonitorProps> = ({
  jobId,
  onJobCompleted,
  onJobCancelled
}) => {
  const [job, setJob] = useState<AgentJob | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>('Connecting real-time monitor...');
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [isCancelling, setIsCancelling] = useState<boolean>(false);
  const [isRetrying, setIsRetrying] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) return;

    // Load initial job details
    jobsApi.getJob(jobId).then(setJob).catch(err => {
      console.error('Failed to load initial job state:', err);
    });

    // Establish real-time WebSocket connection
    const cleanupWs = jobsApi.connectJobStream(
      jobId,
      (updatedJob, message) => {
        setIsConnected(true);
        setJob(updatedJob);
        if (message) setStatusMessage(message);

        if (updatedJob.status === 'completed' && onJobCompleted) {
          onJobCompleted(updatedJob);
        } else if (updatedJob.status === 'cancelled' && onJobCancelled) {
          onJobCancelled(updatedJob);
        }
      },
      (err) => {
        setIsConnected(false);
        console.error('Job WebSocket stream error:', err);
      },
      () => {
        setIsConnected(false);
      }
    );

    return () => {
      cleanupWs();
    };
  }, [jobId]);

  const handleCancelJob = async () => {
    if (!job || isCancelling) return;
    setIsCancelling(true);
    setError(null);
    try {
      await jobsApi.cancelJob(job.id);
      const updated = await jobsApi.getJob(job.id);
      setJob(updated);
    } catch (err: any) {
      setError(err.message || 'Failed to cancel job.');
    } finally {
      setIsCancelling(false);
    }
  };

  const handleRetryJob = async () => {
    if (!job || isRetrying) return;
    setIsRetrying(true);
    setError(null);
    try {
      const retried = await jobsApi.retryJob(job.id);
      setJob(retried);
    } catch (err: any) {
      setError(err.message || 'Failed to retry job.');
    } finally {
      setIsRetrying(false);
    }
  };

  if (!job) {
    return (
      <div className="p-4 bg-gray-900 border border-gray-800 rounded-xl flex items-center justify-between text-xs text-gray-400">
        <span className="flex items-center gap-2">
          <RefreshCw className="w-4 h-4 animate-spin text-indigo-400" /> Initializing Job Monitor #{jobId.substring(0, 8)}...
        </span>
      </div>
    );
  }

  const isCancellable = ['queued', 'running', 'retrying'].includes(job.status);
  const isRetryable = ['failed', 'cancelled'].includes(job.status);

  const getStatusBadge = () => {
    switch (job.status) {
      case 'queued':
        return <span className="px-2.5 py-1 text-xs font-semibold bg-gray-800 text-gray-300 rounded-full flex items-center gap-1.5"><Clock className="w-3.5 h-3.5" /> Queued</span>;
      case 'running':
        return <span className="px-2.5 py-1 text-xs font-semibold bg-blue-900/60 text-blue-300 border border-blue-700 rounded-full flex items-center gap-1.5 animate-pulse"><Activity className="w-3.5 h-3.5 animate-spin text-blue-400" /> Running</span>;
      case 'retrying':
        return <span className="px-2.5 py-1 text-xs font-semibold bg-amber-900/60 text-amber-300 border border-amber-700 rounded-full flex items-center gap-1.5 animate-pulse"><RotateCcw className="w-3.5 h-3.5 animate-spin text-amber-400" /> Retrying ({job.attempt_count}/{job.max_attempts})</span>;
      case 'cancelling':
        return <span className="px-2.5 py-1 text-xs font-semibold bg-orange-900/60 text-orange-300 border border-orange-700 rounded-full flex items-center gap-1.5 animate-pulse"><Ban className="w-3.5 h-3.5 animate-spin" /> Cancelling</span>;
      case 'cancelled':
        return <span className="px-2.5 py-1 text-xs font-semibold bg-gray-800 text-gray-400 border border-gray-700 rounded-full flex items-center gap-1.5"><Ban className="w-3.5 h-3.5" /> Cancelled</span>;
      case 'completed':
        return <span className="px-2.5 py-1 text-xs font-semibold bg-emerald-900/80 text-emerald-300 border border-emerald-600 rounded-full flex items-center gap-1.5"><CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Completed</span>;
      case 'failed':
        return <span className="px-2.5 py-1 text-xs font-semibold bg-red-900/80 text-red-300 border border-red-600 rounded-full flex items-center gap-1.5"><XCircle className="w-3.5 h-3.5 text-red-400" /> Failed</span>;
      default:
        return null;
    }
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3.5 shadow-lg">
      {/* Top Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="p-2 bg-indigo-950 border border-indigo-800/80 rounded-lg text-indigo-400">
            <Layers className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-white uppercase tracking-wider">
                Job #{job.id.substring(0, 8)} ({job.job_type})
              </span>
              <span className="text-[10px] text-gray-500 font-mono">
                Attempt {job.attempt_count}/{job.max_attempts}
              </span>
            </div>
            <p className="text-[11px] text-gray-400 flex items-center gap-1">
              Stage: <span className="text-indigo-300 font-semibold">{job.current_stage}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* WebSocket Status Indicator */}
          <span className={`flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded ${isConnected ? 'text-emerald-400 bg-emerald-950/60' : 'text-gray-500 bg-gray-950'}`}>
            {isConnected ? <Wifi className="w-3 h-3 text-emerald-400" /> : <WifiOff className="w-3 h-3 text-gray-500" />}
            {isConnected ? 'LIVE' : 'OFFLINE'}
          </span>

          {getStatusBadge()}
        </div>
      </div>

      {/* Progress Bar */}
      <div className="space-y-1">
        <div className="flex justify-between text-[11px] text-gray-400 font-mono">
          <span>{statusMessage}</span>
          <span className="font-bold text-indigo-400">{job.progress}%</span>
        </div>
        <div className="w-full bg-gray-950 h-2 rounded-full overflow-hidden border border-gray-800">
          <div
            className={`h-full transition-all duration-500 ${
              job.status === 'completed' ? 'bg-emerald-500' :
              job.status === 'failed' ? 'bg-red-500' :
              job.status === 'cancelled' ? 'bg-gray-600' : 'bg-indigo-500'
            }`}
            style={{ width: `${job.progress}%` }}
          />
        </div>
      </div>

      {/* Error Banner if any */}
      {job.error_message && (
        <div className="p-2.5 bg-red-950/40 border border-red-800/60 rounded-lg text-xs text-red-300 flex items-start gap-2 font-mono">
          <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
          <div>{job.error_message}</div>
        </div>
      )}

      {/* Error notification from actions */}
      {error && (
        <div className="p-2 bg-red-950/60 border border-red-800 rounded-lg text-xs text-red-300">
          {error}
        </div>
      )}

      {/* Footer Controls & Timestamps */}
      <div className="flex items-center justify-between border-t border-gray-800/80 pt-2.5 text-[11px] text-gray-500">
        <div>
          {job.created_at && (
            <span>Created: {new Date(job.created_at).toLocaleTimeString()}</span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {isCancellable && (
            <button
              onClick={handleCancelJob}
              disabled={isCancelling}
              className="px-3 py-1 bg-red-950 hover:bg-red-900 text-red-300 border border-red-800 text-xs font-semibold rounded-lg flex items-center gap-1 transition"
            >
              {isCancelling ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Ban className="w-3 h-3" />} Cancel Job
            </button>
          )}

          {isRetryable && (
            <button
              onClick={handleRetryJob}
              disabled={isRetrying}
              className="px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg flex items-center gap-1 transition shadow-md"
            >
              {isRetrying ? <RefreshCw className="w-3 h-3 animate-spin" /> : <RotateCcw className="w-3 h-3" />} Retry Job
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
