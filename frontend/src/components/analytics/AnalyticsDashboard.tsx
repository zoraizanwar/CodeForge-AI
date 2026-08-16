import React, { useEffect, useState } from 'react';
import type { OverviewData, QuotaData, AIUsageSummary } from '../../services/analytics';
import {
  fetchOverview,
  fetchAIUsage,
  fetchQuotas,
  fetchReport,
  updateQuota
} from '../../services/analytics';

export const AnalyticsDashboard: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [aiUsage, setAiUsage] = useState<AIUsageSummary[]>([]);
  const [quotas, setQuotas] = useState<QuotaData[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [editingQuotaId, setEditingQuotaId] = useState<string | null>(null);
  const [newLimit, setNewLimit] = useState<string>('');

  const loadData = async () => {
    setLoading(true);
    try {
      const [ovData, aiData, qData] = await Promise.all([
        fetchOverview(organizationId),
        fetchAIUsage(organizationId),
        fetchQuotas(organizationId)
      ]);
      setOverview(ovData);
      setAiUsage(aiData);
      setQuotas(qData);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [organizationId]);

  const handleUpdateQuota = async (quotaId: string) => {
    const val = parseFloat(newLimit);
    if (isNaN(val) || val <= 0) return;
    try {
      await updateQuota(organizationId, quotaId, val);
      setEditingQuotaId(null);
      setNewLimit('');
      loadData();
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleGenerateReport = async () => {
    try {
      const report = await fetchReport(organizationId);
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `enterprise-report-${organizationId}.json`;
      a.click();
    } catch (e: any) {
      alert(e.message);
    }
  };

  if (loading) return <div>Loading Analytics...</div>;

  return (
    <div className="analytics-dashboard" style={{ padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h2>Enterprise Usage Analytics & Intelligence</h2>
        <button onClick={handleGenerateReport}>Export Enterprise Report (JSON)</button>
      </div>

      {overview && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '15px', marginBottom: '30px' }}>
          <div style={{ border: '1px solid #ccc', padding: '15px', borderRadius: '6px' }}>
            <h4 style={{ margin: 0, color: '#666' }}>Total Tokens</h4>
            <p style={{ fontSize: '1.5em', fontWeight: 'bold', margin: '5px 0 0 0' }}>{overview.total_tokens.toLocaleString()}</p>
          </div>
          <div style={{ border: '1px solid #ccc', padding: '15px', borderRadius: '6px' }}>
            <h4 style={{ margin: 0, color: '#666' }}>Estimated Cost</h4>
            <p style={{ fontSize: '1.5em', fontWeight: 'bold', margin: '5px 0 0 0' }}>${overview.estimated_cost.toFixed(4)}</p>
          </div>
          <div style={{ border: '1px solid #ccc', padding: '15px', borderRadius: '6px' }}>
            <h4 style={{ margin: 0, color: '#666' }}>API Requests</h4>
            <p style={{ fontSize: '1.5em', fontWeight: 'bold', margin: '5px 0 0 0' }}>{overview.api_requests.toLocaleString()}</p>
          </div>
          <div style={{ border: '1px solid #ccc', padding: '15px', borderRadius: '6px' }}>
            <h4 style={{ margin: 0, color: '#666' }}>Execution Pass Rate</h4>
            <p style={{ fontSize: '1.5em', fontWeight: 'bold', margin: '5px 0 0 0' }}>{(overview.execution_pass_rate * 100).toFixed(1)}%</p>
          </div>
          <div style={{ border: '1px solid #ccc', padding: '15px', borderRadius: '6px' }}>
            <h4 style={{ margin: 0, color: '#666' }}>Webhook Success Rate</h4>
            <p style={{ fontSize: '1.5em', fontWeight: 'bold', margin: '5px 0 0 0' }}>{(overview.webhook_success_rate * 100).toFixed(1)}%</p>
          </div>
        </div>
      )}

      <h3>AI Model Usage & Cost Breakdown</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '30px' }}>
        <thead>
          <tr style={{ borderBottom: '2px solid #ccc', textAlign: 'left' }}>
            <th>Provider</th>
            <th>Model</th>
            <th>Total Tokens</th>
            <th>Requests</th>
            <th>Estimated Cost</th>
          </tr>
        </thead>
        <tbody>
          {aiUsage.map((row, idx) => (
            <tr key={idx} style={{ borderBottom: '1px solid #eee' }}>
              <td>{row.provider}</td>
              <td>{row.model}</td>
              <td>{row.total_tokens.toLocaleString()}</td>
              <td>{row.total_requests}</td>
              <td>${row.estimated_cost.toFixed(4)}</td>
            </tr>
          ))}
          {aiUsage.length === 0 && (
            <tr>
              <td colSpan={5} style={{ padding: '10px', textAlign: 'center', color: '#888' }}>No AI completion usage recorded yet.</td>
            </tr>
          )}
        </tbody>
      </table>

      <h3>Organization Quotas & Controls</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '2px solid #ccc', textAlign: 'left' }}>
            <th>Quota Type</th>
            <th>Usage / Limit</th>
            <th>Utilization</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {quotas.map((q) => {
            const pct = (q.current_usage / q.limit_value) * 100;
            const isWarning = q.current_usage >= q.limit_value * q.warning_threshold;
            const isExceeded = q.current_usage >= q.limit_value;

            return (
              <tr key={q.id} style={{ borderBottom: '1px solid #eee' }}>
                <td>{q.quota_type}</td>
                <td>
                  {editingQuotaId === q.id ? (
                    <div>
                      <input
                        type="number"
                        value={newLimit}
                        onChange={(e) => setNewLimit(e.target.value)}
                        style={{ width: '100px', marginRight: '5px' }}
                      />
                      <button onClick={() => handleUpdateQuota(q.id)}>Save</button>{' '}
                      <button onClick={() => setEditingQuotaId(null)}>Cancel</button>
                    </div>
                  ) : (
                    `${q.current_usage.toLocaleString()} / ${q.limit_value.toLocaleString()}`
                  )}
                </td>
                <td style={{ width: '200px' }}>
                  <div style={{ background: '#eee', height: '10px', borderRadius: '5px', overflow: 'hidden' }}>
                    <div
                      style={{
                        width: `${Math.min(pct, 100)}%`,
                        background: isExceeded ? '#e53e3e' : isWarning ? '#dd6b20' : '#38a169',
                        height: '100%'
                      }}
                    />
                  </div>
                </td>
                <td>
                  {isExceeded ? (
                    <span style={{ color: '#e53e3e', fontWeight: 'bold' }}>EXCEEDED</span>
                  ) : isWarning ? (
                    <span style={{ color: '#dd6b20', fontWeight: 'bold' }}>WARNING</span>
                  ) : (
                    <span style={{ color: '#38a169' }}>OK</span>
                  )}
                </td>
                <td>
                  {editingQuotaId !== q.id && (
                    <button
                      onClick={() => {
                        setEditingQuotaId(q.id);
                        setNewLimit(String(q.limit_value));
                      }}
                    >
                      Modify Quota
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
