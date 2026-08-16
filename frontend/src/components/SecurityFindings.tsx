import React from 'react';
import { ShieldCheck, ShieldAlert } from 'lucide-react';

export interface SecurityFindingData {
  rule_id: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | string;
  category: string;
  file?: string;
  line?: number;
  description: string;
  remediation: string;
}

interface SecurityFindingsProps {
  findings: SecurityFindingData[];
  passed: boolean;
  hasCriticalOrHigh: boolean;
  summary: string;
}

export const SecurityFindings: React.FC<SecurityFindingsProps> = ({ findings, passed, hasCriticalOrHigh, summary }) => {
  return (
    <div className={`p-4 border rounded-xl space-y-3 ${hasCriticalOrHigh ? 'bg-red-500/5 border-red-500/30' : 'bg-[#121319] border-gray-800'}`}>
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-bold uppercase tracking-wider text-rose-400 flex items-center gap-1.5">
          {passed ? <ShieldCheck className="w-4 h-4 text-emerald-400" /> : <ShieldAlert className="w-4 h-4 text-red-400" />} Dedicated Security Review
        </h3>
        <span className={`text-xs px-2 py-0.5 rounded-full border font-semibold ${passed ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' : 'bg-red-500/20 text-red-400 border-red-500/30'}`}>
          {passed ? 'Passed Security Audit' : 'Blocked (Critical/High Findings)'}
        </span>
      </div>

      <p className="text-xs text-gray-400">{summary}</p>

      {findings.length === 0 ? (
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg flex items-center gap-2 text-xs text-emerald-400">
          <ShieldCheck className="w-4 h-4" /> 0 Security Vulnerabilities Detected.
        </div>
      ) : (
        <div className="space-y-2">
          {findings.map((f, i) => (
            <div key={i} className="p-3 bg-[#171821] border border-red-500/30 rounded-lg text-xs space-y-1">
              <div className="flex items-center justify-between">
                <span className="font-mono text-red-400 font-bold">{f.rule_id} ({f.category})</span>
                <span className="px-2 py-0.5 rounded border text-[10px] uppercase font-bold bg-red-500/20 text-red-400 border-red-500/30">
                  {f.severity}
                </span>
              </div>
              <p className="text-gray-200">{f.description}</p>
              {f.file && <p className="text-gray-400 text-[11px]">Location: {f.file}:{f.line || 1}</p>}
              <p className="text-rose-300 text-[11px]"><strong>Remediation:</strong> {f.remediation}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
