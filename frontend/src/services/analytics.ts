export interface OverviewData {
  total_tokens: number;
  estimated_cost: number;
  api_requests: number;
  execution_pass_rate: number;
  webhook_success_rate: number;
}

export interface QuotaData {
  id: string;
  organization_id: string;
  quota_type: string;
  limit_value: number;
  current_usage: number;
  warning_threshold: number;
  is_enabled: boolean;
  reset_period: string;
  updated_at: string;
}

export interface AIUsageSummary {
  provider: string;
  model: string;
  total_tokens: number;
  estimated_cost: number;
  total_requests: number;
}

export interface UsageRecordData {
  id: string;
  organization_id: string;
  event_type: string;
  provider?: string;
  model?: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  duration_ms: number;
  estimated_cost: number;
  created_at: string;
}

export interface ReportData {
  organization_id: string;
  overview: OverviewData;
  quotas: QuotaData[];
  top_ai_models: AIUsageSummary[];
}

export const fetchOverview = async (orgId: string): Promise<OverviewData> => {
  const token = sessionStorage.getItem('access_token') || localStorage.getItem('cf_token');
  const res = await fetch(`/api/v1/organizations/${orgId}/analytics/overview`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Failed to fetch analytics overview');
  return res.json();
};

export const fetchAIUsage = async (orgId: string): Promise<AIUsageSummary[]> => {
  const token = sessionStorage.getItem('access_token') || localStorage.getItem('cf_token');
  const res = await fetch(`/api/v1/organizations/${orgId}/analytics/ai-usage`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Failed to fetch AI usage');
  return res.json();
};

export const fetchQuotas = async (orgId: string): Promise<QuotaData[]> => {
  const token = sessionStorage.getItem('access_token') || localStorage.getItem('cf_token');
  const res = await fetch(`/api/v1/organizations/${orgId}/analytics/quotas`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Failed to fetch quotas');
  return res.json();
};

export const updateQuota = async (orgId: string, quotaId: string, limitValue: number): Promise<QuotaData> => {
  const token = sessionStorage.getItem('access_token') || localStorage.getItem('cf_token');
  const res = await fetch(`/api/v1/organizations/${orgId}/analytics/quotas/${quotaId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify({ limit_value: limitValue })
  });
  if (!res.ok) throw new Error('Failed to update quota');
  return res.json();
};

export const fetchReport = async (orgId: string): Promise<ReportData> => {
  const token = sessionStorage.getItem('access_token') || localStorage.getItem('cf_token');
  const res = await fetch(`/api/v1/organizations/${orgId}/analytics/report`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Failed to fetch enterprise report');
  return res.json();
};
