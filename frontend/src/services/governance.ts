import { API_BASE_URL, getAuthHeaders } from './api';

const GOVERNANCE_API_URL = `${API_BASE_URL}/api/v1/governance`;

export interface WorkflowDecision {
  id: string;
  stage: string;
  decision_type: string;
  confidence_score: number;
  rationale: string;
  escalation_result: string;
  created_at: string;
}

export interface PolicyDecision {
  id: string;
  policy_name: string;
  decision: string;
  reason: string;
  metadata: Record<string, any> | null;
  created_at: string;
}

export interface RiskAssessment {
  id: string;
  risk_level: string;
  factors: string[];
  impact_analysis: Record<string, any> | null;
  created_at: string;
}

export interface ApprovalRecord {
  id: string;
  scope: string;
  status: string;
  reason: string;
  created_at: string;
  updated_at: string;
}

export async function fetchDecisions(skip = 0, limit = 100) {
  const res = await fetch(`${GOVERNANCE_API_URL}/decisions?skip=${skip}&limit=${limit}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Failed to fetch workflow decisions');
  return res.json();
}

export async function fetchPolicies(skip = 0, limit = 100) {
  const res = await fetch(`${GOVERNANCE_API_URL}/policies?skip=${skip}&limit=${limit}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Failed to fetch policy decisions');
  return res.json();
}

export async function fetchRisks(skip = 0, limit = 100) {
  const res = await fetch(`${GOVERNANCE_API_URL}/risk?skip=${skip}&limit=${limit}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Failed to fetch risk assessments');
  return res.json();
}

export async function fetchApprovals(skip = 0, limit = 100) {
  const res = await fetch(`${GOVERNANCE_API_URL}/approvals?skip=${skip}&limit=${limit}`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Failed to fetch approvals');
  return res.json();
}

export async function fetchReliability() {
  const res = await fetch(`${GOVERNANCE_API_URL}/reliability`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Failed to fetch reliability metrics');
  return res.json();
}

export async function approveAction(approvalId: string, reason = "") {
  const res = await fetch(`${GOVERNANCE_API_URL}/approvals/${approvalId}/approve?reason=${encodeURIComponent(reason)}`, {
    method: 'POST',
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Failed to approve action');
  return res.json();
}

export async function rejectAction(approvalId: string, reason = "") {
  const res = await fetch(`${GOVERNANCE_API_URL}/approvals/${approvalId}/reject?reason=${encodeURIComponent(reason)}`, {
    method: 'POST',
    headers: getAuthHeaders(),
  });
  if (!res.ok) throw new Error('Failed to reject action');
  return res.json();
}
