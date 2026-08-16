import React, { useEffect, useState } from 'react';
import { Shield, ShieldAlert, CheckCircle, XCircle, Filter, ChevronLeft, ChevronRight, Eye, RefreshCw, Activity } from 'lucide-react';
import { fetchAuditEvents, type AuditEvent } from '../services/audit';

export const AuditLog: React.FC = () => {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [eventTypeFilter, setEventTypeFilter] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');
  const [requestIdFilter, setRequestIdFilter] = useState('');
  const [page, setPage] = useState(0);
  const limit = 15;

  // Selected event modal
  const [selectedEvent, setSelectedEvent] = useState<AuditEvent | null>(null);

  const loadAuditData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAuditEvents({
        event_type: eventTypeFilter || undefined,
        severity: severityFilter || undefined,
        request_id: requestIdFilter || undefined,
        limit,
        offset: page * limit,
      });
      setEvents(data.items);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.message || 'Failed to load audit events');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAuditData();
  }, [page, severityFilter, eventTypeFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(0);
    loadAuditData();
  };

  const getSeverityBadge = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical':
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-950/60 text-red-400 border border-red-800/40"><ShieldAlert className="w-3.5 h-3.5" /> CRITICAL</span>;
      case 'error':
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-orange-950/60 text-orange-400 border border-orange-800/40"><XCircle className="w-3.5 h-3.5" /> ERROR</span>;
      case 'warning':
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-yellow-950/60 text-yellow-400 border border-yellow-800/40"><Shield className="w-3.5 h-3.5" /> WARNING</span>;
      default:
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-950/60 text-blue-400 border border-blue-800/40"><Activity className="w-3.5 h-3.5" /> INFO</span>;
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6 text-gray-200">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-gray-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2.5">
            <Shield className="w-7 h-7 text-indigo-400" />
            Audit Logging & Observability Trail
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Immutable tenant-isolated operational events, security violations, and workflow audits.
          </p>
        </div>
        <button
          onClick={loadAuditData}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 text-sm bg-gray-800 hover:bg-gray-700 text-gray-200 rounded-md border border-gray-700 transition"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      {/* Filter Controls */}
      <form onSubmit={handleSearchSubmit} className="grid grid-cols-1 sm:grid-cols-4 gap-3 bg-gray-900/60 p-4 rounded-xl border border-gray-800/80">
        <div>
          <label className="block text-xs text-gray-400 mb-1">Event Category</label>
          <input
            type="text"
            placeholder="e.g. security., agent."
            value={eventTypeFilter}
            onChange={(e) => setEventTypeFilter(e.target.value)}
            className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-indigo-500"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Severity</label>
          <select
            value={severityFilter}
            onChange={(e) => { setSeverityFilter(e.target.value); setPage(0); }}
            className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-indigo-500"
          >
            <option value="">All Severities</option>
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="error">Error</option>
            <option value="critical">Critical</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">Request ID</label>
          <input
            type="text"
            placeholder="Filter by X-Request-ID"
            value={requestIdFilter}
            onChange={(e) => setRequestIdFilter(e.target.value)}
            className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-indigo-500"
          />
        </div>
        <div className="flex items-end gap-2">
          <button
            type="submit"
            className="w-full flex items-center justify-center gap-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg px-4 py-1.5 text-sm font-medium transition"
          >
            <Filter className="w-4 h-4" /> Filter Events
          </button>
        </div>
      </form>

      {/* Main Audit Event Table */}
      <div className="bg-gray-900/60 rounded-xl border border-gray-800/80 overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-gray-400 flex items-center justify-center gap-2">
            <RefreshCw className="w-5 h-5 animate-spin" /> Loading audit trail records...
          </div>
        ) : error ? (
          <div className="p-6 text-center text-red-400 bg-red-950/20 border-b border-red-900/40">
            {error}
          </div>
        ) : events.length === 0 ? (
          <div className="p-12 text-center text-gray-500">
            No audit events found matching specified filters.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-gray-300">
              <thead className="bg-gray-950/80 text-gray-400 uppercase text-xs border-b border-gray-800">
                <tr>
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">Event Type</th>
                  <th className="py-3 px-4">Severity</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Request ID</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60">
                {events.map((event) => (
                  <tr key={event.id} className="hover:bg-gray-800/40 transition">
                    <td className="py-3 px-4 font-mono text-xs text-gray-400 whitespace-nowrap">
                      {new Date(event.created_at).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 font-mono text-xs font-semibold text-indigo-300">
                      {event.event_type}
                    </td>
                    <td className="py-3 px-4">
                      {getSeverityBadge(event.severity)}
                    </td>
                    <td className="py-3 px-4">
                      {event.success ? (
                        <span className="inline-flex items-center gap-1 text-xs text-emerald-400"><CheckCircle className="w-3.5 h-3.5" /> Success</span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-xs text-red-400"><XCircle className="w-3.5 h-3.5" /> Failed</span>
                      )}
                    </td>
                    <td className="py-3 px-4 font-mono text-xs text-gray-400 truncate max-w-[140px]">
                      {event.request_id || '-'}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => setSelectedEvent(event)}
                        className="inline-flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 bg-gray-800/80 hover:bg-gray-800 px-2.5 py-1 rounded transition"
                      >
                        <Eye className="w-3.5 h-3.5" /> View Detail
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Footer */}
        <div className="flex items-center justify-between px-4 py-3 bg-gray-950/60 border-t border-gray-800 text-xs text-gray-400">
          <div>
            Showing <span className="font-semibold text-white">{events.length > 0 ? page * limit + 1 : 0}</span> to{' '}
            <span className="font-semibold text-white">{Math.min((page + 1) * limit, total)}</span> of{' '}
            <span className="font-semibold text-white">{total}</span> events
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-2.5 py-1 rounded bg-gray-800 hover:bg-gray-700 disabled:opacity-40 transition flex items-center gap-1"
            >
              <ChevronLeft className="w-3.5 h-3.5" /> Previous
            </button>
            <span className="px-2">Page {page + 1} of {Math.ceil(total / limit) || 1}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={(page + 1) * limit >= total}
              className="px-2.5 py-1 rounded bg-gray-800 hover:bg-gray-700 disabled:opacity-40 transition flex items-center gap-1"
            >
              Next <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Event Detail Modal */}
      {selectedEvent && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-gray-900 border border-gray-800 rounded-xl max-w-2xl w-full max-h-[85vh] overflow-y-auto p-6 space-y-4 shadow-2xl">
            <div className="flex justify-between items-center border-b border-gray-800 pb-3">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <Shield className="w-5 h-5 text-indigo-400" />
                Audit Event Detail
              </h3>
              <button
                onClick={() => setSelectedEvent(null)}
                className="text-gray-400 hover:text-white text-sm font-mono px-2 py-1 bg-gray-800 rounded"
              >
                ✕
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4 text-xs font-mono">
              <div className="bg-gray-950 p-2.5 rounded border border-gray-800">
                <span className="text-gray-500 block">EVENT TYPE</span>
                <span className="text-indigo-400 font-semibold">{selectedEvent.event_type}</span>
              </div>
              <div className="bg-gray-950 p-2.5 rounded border border-gray-800">
                <span className="text-gray-500 block">SEVERITY</span>
                {getSeverityBadge(selectedEvent.severity)}
              </div>
              <div className="bg-gray-950 p-2.5 rounded border border-gray-800">
                <span className="text-gray-500 block">REQUEST ID</span>
                <span className="text-gray-300">{selectedEvent.request_id || 'N/A'}</span>
              </div>
              <div className="bg-gray-950 p-2.5 rounded border border-gray-800">
                <span className="text-gray-500 block">TIMESTAMP</span>
                <span className="text-gray-300">{new Date(selectedEvent.created_at).toISOString()}</span>
              </div>
            </div>

            <div>
              <span className="text-xs font-mono text-gray-400 mb-1 block">EVENT METADATA PAYLOAD</span>
              <pre className="bg-gray-950 p-3 rounded border border-gray-800 text-xs font-mono text-emerald-400 overflow-x-auto max-h-60">
                {JSON.stringify(selectedEvent.metadata || {}, null, 2)}
              </pre>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setSelectedEvent(null)}
                className="px-4 py-1.5 bg-gray-800 hover:bg-gray-700 text-white rounded text-xs font-medium"
              >
                Close Detail
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
