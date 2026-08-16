import React, { useEffect, useState } from 'react';
import { Shield, ShieldAlert, AlertTriangle, List, FileCheck } from 'lucide-react';
import { fetchPolicies, fetchRisks, fetchApprovals, fetchDecisions, type PolicyDecision, type RiskAssessment, type ApprovalRecord, type WorkflowDecision, approveAction, rejectAction } from '../services/governance';

export const GovernanceDashboard: React.FC = () => {
  const [policies, setPolicies] = useState<PolicyDecision[]>([]);
  const [risks, setRisks] = useState<RiskAssessment[]>([]);
  const [approvals, setApprovals] = useState<ApprovalRecord[]>([]);
  const [decisions, setDecisions] = useState<WorkflowDecision[]>([]);
  
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const [p, r, a, d] = await Promise.all([
          fetchPolicies(0, 10),
          fetchRisks(0, 10),
          fetchApprovals(0, 10),
          fetchDecisions(0, 10)
        ]);
        setPolicies(p.items);
        setRisks(r.items);
        setApprovals(a.items);
        setDecisions(d.items);
      } catch (e) {
        console.error(e);
      }
      setLoading(false);
    };
    loadData();
  }, []);

  const handleApprove = async (id: string) => {
    await approveAction(id, "Approved via dashboard");
    const a = await fetchApprovals(0, 10);
    setApprovals(a.items);
  };
  
  const handleReject = async (id: string) => {
    await rejectAction(id, "Rejected via dashboard");
    const a = await fetchApprovals(0, 10);
    setApprovals(a.items);
  };

  if (loading) {
    return <div className="p-8 text-gray-400">Loading Governance Data...</div>;
  }

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-8 text-gray-200">
      <div className="flex items-center gap-3 border-b border-gray-800 pb-4">
        <Shield className="w-8 h-8 text-indigo-400" />
        <div>
          <h1 className="text-2xl font-bold text-white">Enterprise Governance Dashboard</h1>
          <p className="text-sm text-gray-400">Policy decisions, Risk assessments, and Manual approvals.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Approvals */}
        <div className="bg-gray-900/60 p-5 rounded-xl border border-gray-800/80">
          <h2 className="text-lg font-semibold flex items-center gap-2 mb-4 text-white">
            <FileCheck className="w-5 h-5 text-emerald-400" /> Pending Approvals
          </h2>
          <div className="space-y-3">
            {approvals.map(a => (
              <div key={a.id} className="p-4 bg-gray-950 rounded border border-gray-800 flex justify-between items-center">
                <div>
                  <span className="text-sm font-semibold uppercase text-gray-300 block">{a.scope} Approval</span>
                  <span className={`text-xs ${a.status === 'pending' ? 'text-amber-400' : a.status === 'approved' ? 'text-emerald-400' : 'text-red-400'}`}>Status: {a.status}</span>
                </div>
                {a.status === 'pending' && (
                  <div className="flex gap-2">
                    <button onClick={() => handleApprove(a.id)} className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 rounded text-xs text-white">Approve</button>
                    <button onClick={() => handleReject(a.id)} className="px-3 py-1 bg-red-600 hover:bg-red-500 rounded text-xs text-white">Reject</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Policies */}
        <div className="bg-gray-900/60 p-5 rounded-xl border border-gray-800/80">
          <h2 className="text-lg font-semibold flex items-center gap-2 mb-4 text-white">
            <ShieldAlert className="w-5 h-5 text-indigo-400" /> Recent Policy Decisions
          </h2>
          <div className="space-y-3">
            {policies.map(p => (
              <div key={p.id} className="p-3 bg-gray-950 rounded border border-gray-800">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-sm font-semibold text-gray-300">{p.policy_name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${p.decision === 'allow' ? 'bg-emerald-900 text-emerald-400' : p.decision === 'deny' ? 'bg-red-900 text-red-400' : 'bg-amber-900 text-amber-400'}`}>
                    {p.decision}
                  </span>
                </div>
                <span className="text-xs text-gray-500 block">{p.reason}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Risks */}
        <div className="bg-gray-900/60 p-5 rounded-xl border border-gray-800/80">
          <h2 className="text-lg font-semibold flex items-center gap-2 mb-4 text-white">
            <AlertTriangle className="w-5 h-5 text-amber-400" /> Risk Assessments
          </h2>
          <div className="space-y-3">
            {risks.map(r => (
              <div key={r.id} className="p-3 bg-gray-950 rounded border border-gray-800">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-sm text-gray-300">Run ID: {r.id.split('-')[0]}...</span>
                  <span className={`text-xs font-bold uppercase ${r.risk_level === 'low' ? 'text-emerald-400' : r.risk_level === 'critical' ? 'text-red-400' : 'text-amber-400'}`}>
                    {r.risk_level} RISK
                  </span>
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {r.factors.map((f, i) => <div key={i}>• {f}</div>)}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Workflow Decisions */}
        <div className="bg-gray-900/60 p-5 rounded-xl border border-gray-800/80">
          <h2 className="text-lg font-semibold flex items-center gap-2 mb-4 text-white">
            <List className="w-5 h-5 text-blue-400" /> Workflow Decisions
          </h2>
          <div className="space-y-3">
            {decisions.map(d => (
              <div key={d.id} className="p-3 bg-gray-950 rounded border border-gray-800">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-sm text-gray-300 capitalize">{d.stage} Stage</span>
                  <span className="text-xs text-blue-400 font-mono">Conf: {(d.confidence_score * 100).toFixed(0)}%</span>
                </div>
                <span className="text-xs text-gray-500 block">{d.rationale}</span>
                <span className="text-xs font-semibold mt-2 block text-indigo-300">Action: {d.escalation_result}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
