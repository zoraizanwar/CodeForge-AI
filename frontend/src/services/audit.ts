/**
 * Audit Log API Client Service for CodeForge AI Step 14 Observability.
 */
import { API_BASE_URL, getAuthHeaders } from './api';

const AUDIT_API_URL = `${API_BASE_URL}/api/v1/audit`;

export interface AuditEvent {
  id: string;
  user_id: string | null;
  repository_id: string | null;
  agent_task_id: string | null;
  agent_run_id: string | null;
  job_id: string | null;
  event_type: string;
  severity: 'info' | 'warning' | 'error' | 'critical';
  request_id: string | null;
  success: boolean;
  metadata: Record<string, any> | null;
  created_at: string;
}

export interface AuditListResponse {
  total: number;
  items: AuditEvent[];
  limit: number;
  offset: number;
}

export interface AuditFilterParams {
  event_type?: string;
  severity?: string;
  success?: boolean;
  repository_id?: string;
  agent_task_id?: string;
  request_id?: string;
  limit?: number;
  offset?: number;
}

export async function fetchAuditEvents(params: AuditFilterParams = {}): Promise<AuditListResponse> {
  const query = new URLSearchParams();
  if (params.event_type) query.append('event_type', params.event_type);
  if (params.severity) query.append('severity', params.severity);
  if (params.success !== undefined) query.append('success', String(params.success));
  if (params.repository_id) query.append('repository_id', params.repository_id);
  if (params.agent_task_id) query.append('agent_task_id', params.agent_task_id);
  if (params.request_id) query.append('request_id', params.request_id);
  if (params.limit !== undefined) query.append('limit', String(params.limit));
  if (params.offset !== undefined) query.append('offset', String(params.offset));

  const res = await fetch(`${AUDIT_API_URL}?${query.toString()}`, {
    headers: getAuthHeaders(),
  });

  if (!res.ok) {
    throw new Error('Failed to fetch audit events');
  }

  return res.json();
}

export async function fetchAuditEventDetail(eventId: string): Promise<AuditEvent> {
  const res = await fetch(`${AUDIT_API_URL}/${eventId}`, {
    headers: getAuthHeaders(),
  });

  if (!res.ok) {
    throw new Error('Failed to fetch audit event detail');
  }

  return res.json();
}
