import React, { useEffect, useState } from 'react';
import type { WebhookConfig, WebhookDelivery } from '../../services/webhooks';
import {
  fetchWebhooks,
  createWebhook,
  deleteWebhook,
  rotateWebhookSecret,
  testWebhook,
  fetchWebhookDeliveries
} from '../../services/webhooks';

export const WebhookManagement: React.FC<{ organizationId: string }> = ({ organizationId }) => {
  const [webhooks, setWebhooks] = useState<WebhookConfig[]>([]);
  const [url, setUrl] = useState('');
  const [description, setDescription] = useState('');
  const [newSecret, setNewSecret] = useState<string | null>(null);
  const [deliveries, setDeliveries] = useState<WebhookDelivery[]>([]);
  const [selectedWebhook, setSelectedWebhook] = useState<string | null>(null);

  const loadWebhooks = async () => {
    try {
      const data = await fetchWebhooks(organizationId);
      setWebhooks(data);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadWebhooks();
  }, [organizationId]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await createWebhook(organizationId, { url, description });
      setNewSecret(res.secret);
      setUrl('');
      setDescription('');
      loadWebhooks();
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this webhook?')) return;
    await deleteWebhook(organizationId, id);
    loadWebhooks();
  };

  const handleRotate = async (id: string) => {
    const res = await rotateWebhookSecret(organizationId, id);
    setNewSecret(res.secret);
  };

  const handleTest = async (id: string) => {
    try {
      const delivery = await testWebhook(organizationId, id);
      alert(`Test ping sent! Status: ${delivery.status} (HTTP ${delivery.http_status || 'N/A'})`);
    } catch (e: any) {
      alert(e.message);
    }
  };

  const handleViewDeliveries = async (id: string) => {
    setSelectedWebhook(id);
    const data = await fetchWebhookDeliveries(organizationId, id);
    setDeliveries(data);
  };

  return (
    <div className="webhook-management">
      <h3>Organization Webhooks</h3>
      
      {newSecret && (
        <div style={{ background: '#e6fffa', padding: '10px', border: '1px solid #319795', marginBottom: '15px' }}>
          <strong>Webhook Secret Created/Rotated:</strong> <code>{newSecret}</code>
          <p style={{ margin: 0, fontSize: '0.85em' }}>Save this secret now. It will not be shown again.</p>
        </div>
      )}

      <form onSubmit={handleCreate} style={{ marginBottom: '20px' }}>
        <div>
          <input
            type="url"
            placeholder="https://example.com/webhook"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            required
            style={{ width: '300px', marginRight: '10px' }}
          />
          <input
            type="text"
            placeholder="Description (optional)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            style={{ width: '200px', marginRight: '10px' }}
          />
          <button type="submit">Add Webhook</button>
        </div>
      </form>

      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '2px solid #ccc', textAlign: 'left' }}>
            <th>URL</th>
            <th>Description</th>
            <th>Status</th>
            <th>Events</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {webhooks.map((wh) => (
            <tr key={wh.id} style={{ borderBottom: '1px solid #eee' }}>
              <td>{wh.url}</td>
              <td>{wh.description || '-'}</td>
              <td>{wh.is_active ? 'Active' : 'Disabled'}</td>
              <td>{wh.subscribed_events.join(', ')}</td>
              <td>
                <button onClick={() => handleTest(wh.id)}>Test</button>{' '}
                <button onClick={() => handleRotate(wh.id)}>Rotate Secret</button>{' '}
                <button onClick={() => handleViewDeliveries(wh.id)}>Deliveries</button>{' '}
                <button onClick={() => handleDelete(wh.id)}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {selectedWebhook && (
        <div style={{ marginTop: '30px' }}>
          <h4>Delivery History ({selectedWebhook})</h4>
          <ul>
            {deliveries.map((d) => (
              <li key={d.id}>
                [{d.status.toUpperCase()}] HTTP {d.http_status || '-'} - Attempt {d.attempt_count}/{d.max_attempts} - {d.created_at} {d.error_message ? `(${d.error_message})` : ''}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
