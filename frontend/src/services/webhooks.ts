export interface WebhookConfig {
  id: string;
  organization_id: string;
  url: string;
  description?: string;
  subscribed_events: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface WebhookCreateInput {
  url: string;
  description?: string;
  subscribed_events?: string[];
}

export interface WebhookCreateResponse extends WebhookConfig {
  secret: string;
}

export interface SystemEvent {
  id: string;
  event_type: string;
  organization_id?: string;
  repository_id?: string;
  user_id?: string;
  idempotency_key?: string;
  payload: any;
  created_at: string;
}

export interface WebhookDelivery {
  id: string;
  webhook_id: string;
  event_id: string;
  status: string;
  attempt_count: number;
  max_attempts: number;
  http_status?: number;
  request_headers?: any;
  response_headers?: any;
  response_body?: string;
  execution_time_ms?: number;
  error_message?: string;
  next_retry_at?: string;
  created_at: string;
  updated_at: string;
}

export const fetchWebhooks = async (orgId: string): Promise<WebhookConfig[]> => {
  const token = sessionStorage.getItem('access_token');
  const res = await fetch(`/api/v1/organizations/${orgId}/webhooks`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Failed to fetch webhooks');
  return res.json();
};

export const createWebhook = async (orgId: string, input: WebhookCreateInput): Promise<WebhookCreateResponse> => {
  const token = sessionStorage.getItem('access_token');
  const res = await fetch(`/api/v1/organizations/${orgId}/webhooks`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify(input)
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to create webhook');
  }
  return res.json();
};

export const deleteWebhook = async (orgId: string, webhookId: string): Promise<void> => {
  const token = sessionStorage.getItem('access_token');
  const res = await fetch(`/api/v1/organizations/${orgId}/webhooks/${webhookId}`, {
    method: 'DELETE',
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Failed to delete webhook');
};

export const rotateWebhookSecret = async (orgId: string, webhookId: string): Promise<{ webhook_id: string; secret: string }> => {
  const token = sessionStorage.getItem('access_token');
  const res = await fetch(`/api/v1/organizations/${orgId}/webhooks/${webhookId}/rotate-secret`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Failed to rotate webhook secret');
  return res.json();
};

export const testWebhook = async (orgId: string, webhookId: string): Promise<WebhookDelivery> => {
  const token = sessionStorage.getItem('access_token');
  const res = await fetch(`/api/v1/organizations/${orgId}/webhooks/${webhookId}/test`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Failed to send test webhook ping');
  return res.json();
};

export const fetchEvents = async (orgId: string): Promise<SystemEvent[]> => {
  const token = sessionStorage.getItem('access_token');
  const res = await fetch(`/api/v1/organizations/${orgId}/events`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Failed to fetch events');
  return res.json();
};

export const fetchWebhookDeliveries = async (orgId: string, webhookId: string): Promise<WebhookDelivery[]> => {
  const token = sessionStorage.getItem('access_token');
  const res = await fetch(`/api/v1/organizations/${orgId}/webhooks/${webhookId}/deliveries`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!res.ok) throw new Error('Failed to fetch deliveries');
  return res.json();
};
