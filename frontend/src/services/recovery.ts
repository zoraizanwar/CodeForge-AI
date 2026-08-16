export interface RecoveryReadinessReport {
  overall_status: string;
  timestamp: string;
  services: Record<string, string>;
  warnings: string[];
  database_diagnostics: {
    status: string;
    latency_ms: number;
    pool_size: number;
    checkedin: number;
    checkedout: number;
    overflow: number;
  };
}

export interface BackupRecordData {
  id: string;
  organization_id?: string;
  backup_type: string;
  filename: string;
  file_size_bytes: number;
  checksum_sha256: string;
  status: string;
  is_verified: boolean;
  created_at: string;
}

export interface RestorePreflightPlan {
  backup_id: string;
  filename: string;
  file_size_bytes: number;
  created_at?: string;
  is_verified: boolean;
  engine: string;
  requires_explicit_admin_confirmation: boolean;
  estimated_downtime_seconds: number;
  preflight_checks: Record<string, boolean>;
  warnings: string[];
}

export interface RecoveryEventData {
  id: string;
  organization_id?: string;
  event_type: string;
  resource_type: string;
  resource_id?: string;
  status: string;
  details?: Record<string, any>;
  created_at: string;
}

export const fetchReadiness = async (): Promise<RecoveryReadinessReport> => {
  const token = sessionStorage.getItem('access_token') || localStorage.getItem('cf_token');
  const res = await fetch('/api/v1/recovery/readiness', {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Failed to fetch disaster recovery readiness');
  return res.json();
};

export const fetchBackups = async (orgId?: string): Promise<BackupRecordData[]> => {
  const token = sessionStorage.getItem('access_token') || localStorage.getItem('cf_token');
  const url = orgId ? `/api/v1/recovery/backups?organization_id=${orgId}` : '/api/v1/recovery/backups';
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Failed to fetch backups');
  return res.json();
};

export const createBackup = async (backupType: string = 'database', orgId?: string): Promise<BackupRecordData> => {
  const token = sessionStorage.getItem('access_token') || localStorage.getItem('cf_token');
  const res = await fetch('/api/v1/recovery/backups', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify({ organization_id: orgId, backup_type: backupType })
  });
  if (!res.ok) throw new Error('Failed to create backup');
  return res.json();
};

export const verifyBackup = async (backupId: string): Promise<any> => {
  const token = sessionStorage.getItem('access_token') || localStorage.getItem('cf_token');
  const res = await fetch(`/api/v1/recovery/backups/${backupId}/verify`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Failed to verify backup');
  return res.json();
};

export const getRestorePlan = async (backupId: string): Promise<RestorePreflightPlan> => {
  const token = sessionStorage.getItem('access_token') || localStorage.getItem('cf_token');
  const res = await fetch(`/api/v1/recovery/backups/${backupId}/restore-plan`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Failed to generate restore plan');
  return res.json();
};

export const triggerJobRecovery = async (): Promise<any> => {
  const token = sessionStorage.getItem('access_token') || localStorage.getItem('cf_token');
  const res = await fetch('/api/v1/recovery/jobs/recover', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Failed to trigger job recovery');
  return res.json();
};

export const triggerWorkspaceCleanup = async (): Promise<any> => {
  const token = sessionStorage.getItem('access_token') || localStorage.getItem('cf_token');
  const res = await fetch('/api/v1/recovery/workspace/cleanup', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Failed to trigger workspace cleanup');
  return res.json();
};

export const fetchRecoveryEvents = async (): Promise<RecoveryEventData[]> => {
  const token = sessionStorage.getItem('access_token') || localStorage.getItem('cf_token');
  const res = await fetch('/api/v1/recovery/events', {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Failed to fetch recovery events');
  return res.json();
};
