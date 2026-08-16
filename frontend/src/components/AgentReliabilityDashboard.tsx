import React, { useEffect, useState } from 'react';
import { Activity, BarChart2 } from 'lucide-react';
import { fetchReliability } from '../services/governance';

export const AgentReliabilityDashboard: React.FC = () => {
  const [metrics, setMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetchReliability();
        setMetrics(data);
      } catch (e) {
        console.error(e);
      }
      setLoading(false);
    };
    load();
  }, []);

  if (loading) {
    return <div className="p-8 text-gray-400">Loading Reliability Data...</div>;
  }

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-8 text-gray-200">
      <div className="flex items-center gap-3 border-b border-gray-800 pb-4">
        <BarChart2 className="w-8 h-8 text-indigo-400" />
        <div>
          <h1 className="text-2xl font-bold text-white">Agent Reliability & Performance</h1>
          <p className="text-sm text-gray-400">Success rates, human approvals, and confidence trends across the agent swarm.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <div className="bg-gray-900/60 p-5 rounded-xl border border-gray-800/80 text-center space-y-2">
          <Activity className="w-6 h-6 text-emerald-400 mx-auto" />
          <div className="text-sm text-gray-400 uppercase font-mono">Overall Success Rate</div>
          <div className="text-4xl font-bold text-white">{metrics?.success_rate || 0}%</div>
        </div>
        
        <div className="bg-gray-900/60 p-5 rounded-xl border border-gray-800/80 text-center space-y-2">
          <div className="text-sm text-gray-400 uppercase font-mono">Total Runs</div>
          <div className="text-4xl font-bold text-white">{metrics?.total_runs || 0}</div>
        </div>
        
        <div className="bg-gray-900/60 p-5 rounded-xl border border-gray-800/80 text-center space-y-2">
          <div className="text-sm text-gray-400 uppercase font-mono">Successful / Failed</div>
          <div className="text-2xl font-bold text-emerald-400 inline-block">{metrics?.success_count || 0}</div>
          <span className="mx-2 text-gray-600">/</span>
          <div className="text-2xl font-bold text-red-400 inline-block">{metrics?.failure_count || 0}</div>
        </div>
      </div>
    </div>
  );
};
