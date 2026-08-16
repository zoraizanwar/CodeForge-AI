import React, { useEffect, useState } from 'react';
import type {
  RecoveryReadinessReport,
  BackupRecordData,
  RestorePreflightPlan,
  RecoveryEventData
} from '../../services/recovery';
import {
  fetchReadiness,
  fetchBackups,
  createBackup,
  verifyBackup,
  getRestorePlan,
  triggerJobRecovery,
  triggerWorkspaceCleanup,
  fetchRecoveryEvents
} from '../../services/recovery';

export const OperationsDashboard: React.FC = () => {
  const [readiness, setReadiness] = useState<RecoveryReadinessReport | null>(null);
  const [backups, setBackups] = useState<BackupRecordData[]>([]);
  const [events, setEvents] = useState<RecoveryEventData[]>([]);
  const [activePlan, setActivePlan] = useState<RestorePreflightPlan | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [rData, bData, eData] = await Promise.all([
        fetchReadiness(),
        fetchBackups(),
        fetchRecoveryEvents()
      ]);
      setReadiness(rData);
      setBackups(bData);
      setEvents(eData);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const handleCreateBackup = async () => {
    try {
      await createBackup('database');
      loadAll();
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleVerifyBackup = async (id: string) => {
    try {
      await verifyBackup(id);
      loadAll();
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleGenerateRestorePlan = async (id: string) => {
    try {
      const plan = await getRestorePlan(id);
      setActivePlan(plan);
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleTriggerJobRecovery = async () => {
    try {
      const res = await triggerJobRecovery();
      alert(`Job Recovery Executed: Recovered ${res.recovered_count}, Failed ${res.failed_count}`);
      loadAll();
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleTriggerCleanup = async () => {
    try {
      const res = await triggerWorkspaceCleanup();
      alert(`Workspace Cleanup: Cleaned ${res.cleaned} directory(ies), Freed ${(res.freed_bytes / 1024 / 1024).toFixed(2)} MB`);
      loadAll();
    } catch (e: any) {
      alert(e.message);
    }
  };

  if (loading) return <div>Loading Operations & Disaster Recovery Dashboard...</div>;

  return (
    <div className="operations-dashboard" style={{ padding: '20px' }}>
      <h2>Enterprise Operations & Disaster Recovery Dashboard</h2>

      {readiness && (
        <div style={{ background: readiness.overall_status === 'ready' ? '#f0fff4' : '#fff5f5', border: '1px solid #ccc', padding: '15px', borderRadius: '6px', marginBottom: '25px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h3 style={{ margin: 0 }}>System Readiness: <span style={{ textTransform: 'uppercase', color: readiness.overall_status === 'ready' ? '#38a169' : '#e53e3e' }}>{readiness.overall_status}</span></h3>
              <p style={{ margin: '5px 0 0 0', color: '#666', fontSize: '0.9em' }}>Last Diagnostic Scan: {readiness.timestamp}</p>
            </div>
            <div>
              <button onClick={handleTriggerJobRecovery} style={{ marginRight: '10px' }}>Run Job Recovery Scan</button>
              <button onClick={handleTriggerCleanup}>Run Workspace Cleanup</button>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px', marginTop: '15px' }}>
            {Object.entries(readiness.services).map(([svc, stat]) => (
              <div key={svc} style={{ border: '1px solid #ddd', padding: '10px', borderRadius: '4px', background: '#fff' }}>
                <strong style={{ textTransform: 'capitalize' }}>{svc.replace('_', ' ')}:</strong>{' '}
                <span style={{ color: stat === 'healthy' || stat === 'current' || stat === 'ok' ? '#38a169' : '#dd6b20' }}>{stat}</span>
              </div>
            ))}
          </div>

          {readiness.warnings.length > 0 && (
            <div style={{ marginTop: '15px', color: '#c53030' }}>
              <strong>Active Warnings:</strong>
              <ul style={{ margin: '5px 0 0 0', paddingLeft: '20px' }}>
                {readiness.warnings.map((w, idx) => <li key={idx}>{w}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
        <h3>Automated Database Backups</h3>
        <button onClick={handleCreateBackup}>Create Database Backup Now</button>
      </div>

      <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '30px' }}>
        <thead>
          <tr style={{ borderBottom: '2px solid #ccc', textAlign: 'left' }}>
            <th>Filename</th>
            <th>Type</th>
            <th>Size</th>
            <th>SHA-256 Checksum</th>
            <th>Verified</th>
            <th>Created At</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {backups.map((b) => (
            <tr key={b.id} style={{ borderBottom: '1px solid #eee' }}>
              <td>{b.filename}</td>
              <td>{b.backup_type}</td>
              <td>{(b.file_size_bytes / 1024).toFixed(1)} KB</td>
              <td><code>{b.checksum_sha256.substring(0, 12)}...</code></td>
              <td>{b.is_verified ? <span style={{ color: '#38a169' }}>VERIFIED</span> : <span style={{ color: '#e53e3e' }}>UNVERIFIED</span>}</td>
              <td>{b.created_at}</td>
              <td>
                <button onClick={() => handleVerifyBackup(b.id)} style={{ marginRight: '5px' }}>Verify</button>
                <button onClick={() => handleGenerateRestorePlan(b.id)}>Preflight Plan</button>
              </td>
            </tr>
          ))}
          {backups.length === 0 && (
            <tr><td colSpan={7} style={{ textAlign: 'center', padding: '15px', color: '#888' }}>No backup records found.</td></tr>
          )}
        </tbody>
      </table>

      {activePlan && (
        <div style={{ border: '2px solid #dd6b20', background: '#fffaf0', padding: '15px', borderRadius: '6px', marginBottom: '30px' }}>
          <h4>Restore Preflight Plan: {activePlan.filename}</h4>
          <p><strong>Estimated Downtime:</strong> {activePlan.estimated_downtime_seconds}s</p>
          <div style={{ margin: '10px 0', color: '#c53030' }}>
            <strong>Safety Protocol Warnings:</strong>
            <ul>
              {activePlan.warnings.map((w, idx) => <li key={idx}>{w}</li>)}
            </ul>
          </div>
          <button onClick={() => setActivePlan(null)}>Close Preflight Plan</button>
        </div>
      )}

      <h3>Recent System Recovery Events</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '2px solid #ccc', textAlign: 'left' }}>
            <th>Event Type</th>
            <th>Resource Type</th>
            <th>Resource ID</th>
            <th>Status</th>
            <th>Timestamp</th>
          </tr>
        </thead>
        <tbody>
          {events.map((e) => (
            <tr key={e.id} style={{ borderBottom: '1px solid #eee' }}>
              <td>{e.event_type}</td>
              <td>{e.resource_type}</td>
              <td>{e.resource_id || 'N/A'}</td>
              <td><span style={{ color: e.status === 'completed' ? '#38a169' : '#e53e3e' }}>{e.status}</span></td>
              <td>{e.created_at}</td>
            </tr>
          ))}
          {events.length === 0 && (
            <tr><td colSpan={5} style={{ textAlign: 'center', padding: '15px', color: '#888' }}>No recovery events logged.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
};
