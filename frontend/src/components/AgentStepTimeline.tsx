import React from 'react';
import type { AgentRunStep } from '../services/agentRuns';
import { CheckCircle2, Clock, XCircle, AlertCircle, Wrench, Shield, Code, FileText, Cpu } from 'lucide-react';

interface AgentStepTimelineProps {
  steps: AgentRunStep[];
  currentAgent?: string;
}

export const AgentStepTimeline: React.FC<AgentStepTimelineProps> = ({ steps }) => {
  const agentIcons: Record<string, React.ReactNode> = {
    planner: <FileText className="w-4 h-4 text-blue-400" />,
    engineer: <Code className="w-4 h-4 text-indigo-400" />,
    reviewer: <CheckCircle2 className="w-4 h-4 text-purple-400" />,
    security: <Shield className="w-4 h-4 text-rose-400" />,
    tester: <Cpu className="w-4 h-4 text-emerald-400" />,
    repair: <Wrench className="w-4 h-4 text-amber-400" />,
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'passed':
      case 'completed':
        return <span className="flex items-center gap-1 text-emerald-400 text-xs font-semibold"><CheckCircle2 className="w-3.5 h-3.5" /> Passed</span>;
      case 'failed':
        return <span className="flex items-center gap-1 text-red-400 text-xs font-semibold"><XCircle className="w-3.5 h-3.5" /> Failed</span>;
      case 'running':
        return <span className="flex items-center gap-1 text-indigo-400 text-xs font-semibold animate-pulse"><Clock className="w-3.5 h-3.5" /> Running</span>;
      case 'review_needed':
        return <span className="flex items-center gap-1 text-amber-400 text-xs font-semibold"><AlertCircle className="w-3.5 h-3.5" /> Review Needed</span>;
      default:
        return <span className="text-gray-500 text-xs">Pending</span>;
    }
  };

  return (
    <div className="p-4 bg-[#121319] border border-gray-800 rounded-xl space-y-4">
      <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400">
        Multi-Agent Execution Timeline
      </h3>

      <div className="relative border-l-2 border-gray-800 ml-3 space-y-4 pl-4">
        {steps.map((step) => (
          <div key={step.id} className="relative group">
            {/* Timeline Dot */}
            <div className={`absolute -left-[23px] top-0.5 w-4 h-4 rounded-full border-2 flex items-center justify-center bg-[#121319] ${
              step.status === 'passed' ? 'border-emerald-500 text-emerald-400' :
              step.status === 'failed' ? 'border-red-500 text-red-400' :
              step.status === 'running' ? 'border-indigo-500 text-indigo-400 animate-pulse' : 'border-gray-700'
            }`}>
            </div>

            <div className="bg-[#171821] border border-gray-800 rounded-lg p-3 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {agentIcons[step.agent_type] || <Cpu className="w-4 h-4 text-gray-400" />}
                  <span className="font-bold text-xs uppercase tracking-wide text-gray-200">{step.agent_type} Agent</span>
                </div>
                {getStatusBadge(step.status)}
              </div>

              {step.confidence !== undefined && (
                <div className="flex items-center justify-between text-[11px] text-gray-400">
                  <span>Confidence Score:</span>
                  <span className={`font-semibold ${step.confidence >= 0.8 ? 'text-emerald-400' : 'text-amber-400'}`}>
                    {(step.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              )}

              {step.error_message && (
                <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 p-2 rounded">
                  {step.error_message}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
