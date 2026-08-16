import React from 'react';
import { AlertTriangle, CheckCircle } from 'lucide-react';

export interface ReviewFindingData {
  file: string;
  line: number;
  category: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info' | string;
  description: string;
  recommendation: string;
}

interface ReviewFindingsProps {
  findings: ReviewFindingData[];
  approved: boolean;
  summary: string;
}

export const ReviewFindings: React.FC<ReviewFindingsProps> = ({ findings, approved, summary }) => {
  const getSeverityBadge = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical':
        return 'bg-red-500/20 text-red-400 border-red-500/30';
      case 'high':
        return 'bg-orange-500/20 text-orange-400 border-orange-500/30';
      case 'medium':
        return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
      case 'low':
        return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      default:
        return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
    }
  };

  return (
    <div className="p-4 bg-[#121319] border border-gray-800 rounded-xl space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-bold uppercase tracking-wider text-indigo-400 flex items-center gap-1.5">
          <AlertTriangle className="w-4 h-4 text-indigo-400" /> Code Reviewer Findings
        </h3>
        <span className={`text-xs px-2 py-0.5 rounded-full border font-semibold ${approved ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' : 'bg-red-500/20 text-red-400 border-red-500/30'}`}>
          {approved ? 'Approved' : 'Changes Requested'}
        </span>
      </div>

      <p className="text-xs text-gray-400">{summary}</p>

      {findings.length === 0 ? (
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg flex items-center gap-2 text-xs text-emerald-400">
          <CheckCircle className="w-4 h-4" /> No code quality issues identified.
        </div>
      ) : (
        <div className="space-y-2">
          {findings.map((f, i) => (
            <div key={i} className="p-3 bg-[#171821] border border-gray-800 rounded-lg text-xs space-y-1">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-gray-200">{f.file}:{f.line}</span>
                <span className={`px-2 py-0.5 rounded border text-[10px] uppercase font-bold ${getSeverityBadge(f.severity)}`}>
                  {f.severity}
                </span>
              </div>
              <p className="text-gray-300">{f.description}</p>
              <p className="text-gray-400 text-[11px]"><strong>Recommendation:</strong> {f.recommendation}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
