import React, { useEffect, useState, useCallback } from 'react';
import { analysisApi, type AnalysisStatus, type SymbolItem, type SearchResultItem } from '../services/analysis';
import {
  Brain,
  Search,
  Code2,
  Package,
  PlayCircle,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Clock,
  Loader2,
  ChevronRight,
  FileCode,
  Layers,
  Zap,
} from 'lucide-react';

interface AnalysisPanelProps {
  repoId: string;
  repoStatus: string;
}

const SYMBOL_COLORS: Record<string, string> = {
  class: 'text-violet-400 bg-violet-500/10 border-violet-500/20',
  function: 'text-sky-400 bg-sky-500/10 border-sky-500/20',
  method: 'text-teal-400 bg-teal-500/10 border-teal-500/20',
  route: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  import: 'text-gray-400 bg-gray-500/10 border-gray-500/20',
};

const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const cfg: Record<string, { icon: React.ReactNode; cls: string; label: string }> = {
    completed: {
      icon: <CheckCircle2 className="w-3 h-3" />,
      cls: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
      label: 'Analysis Complete',
    },
    processing: {
      icon: <Loader2 className="w-3 h-3 animate-spin" />,
      cls: 'text-purple-400 bg-purple-500/10 border-purple-500/20',
      label: 'Analyzing…',
    },
    pending: {
      icon: <Clock className="w-3 h-3" />,
      cls: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
      label: 'Pending',
    },
    failed: {
      icon: <AlertCircle className="w-3 h-3" />,
      cls: 'text-rose-400 bg-rose-500/10 border-rose-500/20',
      label: 'Failed',
    },
  };
  const c = cfg[status] ?? cfg.pending;
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded border ${c.cls}`}>
      {c.icon}{c.label}
    </span>
  );
};

export const AnalysisPanel: React.FC<AnalysisPanelProps> = ({ repoId, repoStatus }) => {
  const [tab, setTab] = useState<'overview' | 'symbols' | 'search'>('overview');
  const [analysis, setAnalysis] = useState<AnalysisStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [symbols, setSymbols] = useState<SymbolItem[]>([]);
  const [symbolsLoading, setSymbolsLoading] = useState(false);
  const [symbolFilter, setSymbolFilter] = useState('');
  const [symbolTypeFilter, setSymbolTypeFilter] = useState('');

  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResultItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const fetchAnalysis = useCallback(async () => {
    try {
      const a = await analysisApi.getAnalysis(repoId);
      setAnalysis(a);
      setError(null);
    } catch (err: any) {
      if (err.message?.includes('404') || err.message?.includes('not been analyzed')) {
        setAnalysis(null);
        setError(null);
      } else {
        setError(err.message);
      }
    }
  }, [repoId]);


  useEffect(() => {
    setLoading(true);
    fetchAnalysis().finally(() => setLoading(false));
  }, [fetchAnalysis]);

  // Poll when analysis is in progress
  useEffect(() => {
    if (analysis?.status === 'processing' || analysis?.status === 'pending') {
      const interval = setInterval(fetchAnalysis, 4000);
      return () => clearInterval(interval);
    }
  }, [analysis?.status, fetchAnalysis]);

  const handleTrigger = async () => {
    setTriggering(true);
    setError(null);
    try {
      await analysisApi.triggerAnalysis(repoId);
      await fetchAnalysis();
    } catch (err: any) {
      setError(err.message || 'Failed to trigger analysis');
    } finally {
      setTriggering(false);
    }
  };

  const loadSymbols = async () => {
    setSymbolsLoading(true);
    try {
      const data = await analysisApi.getSymbols(repoId, {
        symbolType: symbolTypeFilter || undefined,
        limit: 200,
      });
      setSymbols(data);
    } catch (err: any) {
      setSymbols([]);
    } finally {
      setSymbolsLoading(false);
    }
  };

  useEffect(() => {
    if (tab === 'symbols' && analysis?.status === 'completed') {
      loadSymbols();
    }
  }, [tab, symbolTypeFilter, analysis?.status]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setSearching(true);
    setSearchError(null);
    try {
      const result = await analysisApi.searchCode(repoId, searchQuery.trim(), 10);
      setSearchResults(result.results);
    } catch (err: any) {
      setSearchError(err.message || 'Search failed');
    } finally {
      setSearching(false);
    }
  };

  const filteredSymbols = symbols.filter(s =>
    s.name.toLowerCase().includes(symbolFilter.toLowerCase()) ||
    s.file_path.toLowerCase().includes(symbolFilter.toLowerCase())
  );

  const canAnalyze = repoStatus === 'indexed' || repoStatus === 'failed';
  const isAnalyzed = analysis?.status === 'completed';

  return (
    <div className="bg-[#121319] border border-gray-800 rounded-xl flex flex-col min-h-[60vh] overflow-hidden font-sans">
      {/* Panel Header */}
      <div className="border-b border-gray-800 px-5 pt-4 pb-0">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Brain className="w-4 h-4 text-purple-400" />
            <h2 className="text-xs font-bold uppercase tracking-widest text-gray-400">
              AI Intelligence
            </h2>
            {analysis && <StatusBadge status={analysis.status} />}
          </div>
          {canAnalyze && (
            <button
              onClick={handleTrigger}
              disabled={triggering || analysis?.status === 'processing' || analysis?.status === 'pending'}
              className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-semibold bg-purple-600/10 hover:bg-purple-600/20 border border-purple-500/20 hover:border-purple-400/30 text-purple-400 rounded-lg transition-all disabled:opacity-50 cursor-pointer"
            >
              {triggering ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <PlayCircle className="w-3 h-3" />
              )}
              {analysis ? 'Re-analyze' : 'Analyze'}
            </button>
          )}
        </div>

        {/* Tabs */}
        <div className="flex gap-0 -mb-px">
          {[
            { id: 'overview', icon: <Layers className="w-3 h-3" />, label: 'Overview' },
            { id: 'symbols', icon: <Code2 className="w-3 h-3" />, label: 'Symbols' },
            { id: 'search', icon: <Search className="w-3 h-3" />, label: 'Search' },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id as typeof tab)}
              className={`flex items-center gap-1.5 px-4 py-2 text-xs font-medium border-b-2 transition-all cursor-pointer ${
                tab === t.id
                  ? 'border-purple-500 text-purple-400'
                  : 'border-transparent text-gray-500 hover:text-gray-300'
              }`}
            >
              {t.icon} {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Panel Body */}
      <div className="flex-1 p-5 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center h-40 gap-2 text-gray-600">
            <RefreshCw className="w-5 h-5 animate-spin text-purple-500" />
            <span className="text-xs">Loading analysis…</span>
          </div>
        ) : error ? (
          <div className="p-3 rounded-lg bg-rose-500/5 border border-rose-800/30 text-rose-400 text-xs">
            {error}
          </div>
        ) : tab === 'overview' ? (
          <OverviewTab analysis={analysis} onTrigger={handleTrigger} triggering={triggering} canAnalyze={canAnalyze} />
        ) : tab === 'symbols' ? (
          <SymbolsTab
            symbols={filteredSymbols}
            loading={symbolsLoading}
            isAnalyzed={isAnalyzed}
            filter={symbolFilter}
            onFilterChange={setSymbolFilter}
            typeFilter={symbolTypeFilter}
            onTypeFilterChange={setSymbolTypeFilter}
          />
        ) : (
          <SearchTab
            query={searchQuery}
            onQueryChange={setSearchQuery}
            onSearch={handleSearch}
            results={searchResults}
            searching={searching}
            error={searchError}
            isAnalyzed={isAnalyzed}
          />
        )}
      </div>
    </div>
  );
};

// ── Overview Tab ──────────────────────────────────────────────────────────────

const OverviewTab: React.FC<{
  analysis: AnalysisStatus | null;
  onTrigger: () => void;
  triggering: boolean;
  canAnalyze: boolean;
}> = ({ analysis, onTrigger, triggering, canAnalyze }) => {
  if (!analysis) {
    return (
      <div className="flex flex-col items-center justify-center h-48 text-center gap-3">
        <Brain className="w-10 h-10 text-gray-800" />
        <div>
          <p className="text-sm font-semibold text-gray-400">No analysis yet</p>
          <p className="text-xs text-gray-600 mt-1 max-w-xs">
            Trigger an analysis to extract symbols, dependencies, frameworks, and enable semantic code search.
          </p>
        </div>
        {canAnalyze && (
          <button
            onClick={onTrigger}
            disabled={triggering}
            className="mt-2 flex items-center gap-1.5 px-4 py-2 text-xs font-semibold bg-purple-600 hover:bg-purple-500 text-white rounded-lg transition-all disabled:opacity-50 cursor-pointer"
          >
            {triggering ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
            Run Analysis
          </button>
        )}
      </div>
    );
  }

  if (analysis.status === 'processing' || analysis.status === 'pending') {
    return (
      <div className="flex flex-col items-center justify-center h-48 gap-3 text-center">
        <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
        <p className="text-xs text-gray-400">
          Analysis is running in the background. This may take a minute…
        </p>
      </div>
    );
  }

  if (analysis.status === 'failed') {
    return (
      <div className="space-y-3">
        <div className="p-3 rounded-lg bg-rose-500/5 border border-rose-800/20 text-rose-400 text-xs">
          Analysis failed: {analysis.error_message || 'Unknown error'}
        </div>
        {canAnalyze && (
          <button
            onClick={onTrigger}
            disabled={triggering}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-rose-600/10 hover:bg-rose-600/20 border border-rose-500/20 text-rose-400 rounded-lg transition-all cursor-pointer"
          >
            <RefreshCw className="w-3 h-3" /> Retry Analysis
          </button>
        )}
      </div>
    );
  }

  const deps = analysis.dependencies_parsed ?? {};
  const depCount = Object.keys(deps).length;
  const entryPoints = analysis.entry_points ?? [];
  const frameworks = analysis.frameworks ?? [];

  return (
    <div className="space-y-4">
      {/* Architecture Summary */}
      {analysis.architecture_summary && (
        <div className="p-3 rounded-lg bg-purple-500/5 border border-purple-500/10">
          <p className="text-[11px] text-purple-300 leading-relaxed">{analysis.architecture_summary}</p>
        </div>
      )}

      {/* Frameworks */}
      {frameworks.length > 0 && (
        <div className="space-y-2">
          <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500 flex items-center gap-1">
            <Zap className="w-3 h-3 text-amber-400" /> Detected Frameworks
          </p>
          <div className="flex flex-wrap gap-1.5">
            {frameworks.map(fw => (
              <span key={fw} className="text-[11px] px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20 text-amber-400 font-medium">
                {fw}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Entry Points */}
      {entryPoints.length > 0 && (
        <div className="space-y-2">
          <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500 flex items-center gap-1">
            <PlayCircle className="w-3 h-3 text-sky-400" /> Entry Points
          </p>
          <div className="space-y-1">
            {entryPoints.map(ep => (
              <div key={ep} className="flex items-center gap-1.5 text-[11px] text-sky-400 font-mono">
                <FileCode className="w-3 h-3 flex-shrink-0" />
                <span className="truncate">{ep}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Dependencies */}
      {depCount > 0 && (
        <div className="space-y-2">
          <p className="text-[10px] font-bold uppercase tracking-wider text-gray-500 flex items-center gap-1">
            <Package className="w-3 h-3 text-teal-400" /> Dependencies
            <span className="ml-1 text-teal-400 font-semibold">{depCount}</span>
          </p>
          <div className="max-h-40 overflow-y-auto space-y-0.5 font-mono pr-1">
            {Object.entries(deps).slice(0, 50).map(([pkg, ver]) => (
              <div key={pkg} className="flex items-center justify-between text-[10px] py-0.5">
                <span className="text-gray-400 truncate max-w-[60%]">{pkg}</span>
                <span className="text-gray-600 font-normal">{ver || 'any'}</span>
              </div>
            ))}
            {depCount > 50 && (
              <p className="text-[10px] text-gray-600 italic pt-1">…and {depCount - 50} more</p>
            )}
          </div>
        </div>
      )}

      {analysis.last_analyzed_at && (
        <p className="text-[10px] text-gray-600 pt-2 border-t border-gray-850">
          Last analyzed: {new Date(analysis.last_analyzed_at).toLocaleString()}
        </p>
      )}
    </div>
  );
};

// ── Symbols Tab ───────────────────────────────────────────────────────────────

const SymbolsTab: React.FC<{
  symbols: SymbolItem[];
  loading: boolean;
  isAnalyzed: boolean;
  filter: string;
  onFilterChange: (v: string) => void;
  typeFilter: string;
  onTypeFilterChange: (v: string) => void;
}> = ({ symbols, loading, isAnalyzed, filter, onFilterChange, typeFilter, onTypeFilterChange }) => {
  if (!isAnalyzed) {
    return (
      <div className="flex items-center justify-center h-40 text-gray-600 text-xs">
        Run an analysis first to extract code symbols.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Filters */}
      <div className="flex gap-2">
        <input
          type="text"
          value={filter}
          onChange={e => onFilterChange(e.target.value)}
          placeholder="Filter by name or file…"
          className="flex-1 px-3 py-1.5 text-xs bg-[#0a0b0d] border border-gray-800 rounded-lg text-gray-300 placeholder-gray-600 focus:outline-none focus:border-purple-500/50 transition-all"
        />
        <select
          value={typeFilter}
          onChange={e => onTypeFilterChange(e.target.value)}
          className="px-3 py-1.5 text-xs bg-[#0a0b0d] border border-gray-800 rounded-lg text-gray-400 focus:outline-none focus:border-purple-500/50 transition-all cursor-pointer"
        >
          <option value="">All types</option>
          <option value="class">Class</option>
          <option value="function">Function</option>
          <option value="method">Method</option>
          <option value="route">Route</option>
        </select>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-gray-600 text-xs py-6 justify-center">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading symbols…
        </div>
      ) : symbols.length === 0 ? (
        <div className="text-center text-gray-600 text-xs py-6">No symbols matched your filter.</div>
      ) : (
        <div className="space-y-1 max-h-[50vh] overflow-y-auto pr-1">
          {symbols.map(sym => {
            const cls = SYMBOL_COLORS[sym.type] ?? SYMBOL_COLORS.import;
            return (
              <div key={sym.id} className="flex items-center gap-2 py-1 px-2 rounded hover:bg-gray-900 group transition-colors">
                <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border font-mono ${cls}`}>
                  {sym.type[0].toUpperCase()}
                </span>
                <span className="text-xs text-gray-200 font-mono flex-1 truncate">{sym.name}</span>
                <span className="text-[10px] text-gray-600 truncate max-w-[35%] font-mono group-hover:text-gray-500 flex items-center gap-1">
                  <ChevronRight className="w-2.5 h-2.5 flex-shrink-0" />
                  {sym.file_path}:{sym.line_number}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

// ── Search Tab ────────────────────────────────────────────────────────────────

const SearchTab: React.FC<{
  query: string;
  onQueryChange: (v: string) => void;
  onSearch: (e: React.FormEvent) => void;
  results: SearchResultItem[];
  searching: boolean;
  error: string | null;
  isAnalyzed: boolean;
}> = ({ query, onQueryChange, onSearch, results, searching, error, isAnalyzed }) => {
  if (!isAnalyzed) {
    return (
      <div className="flex items-center justify-center h-40 text-gray-600 text-xs">
        Run an analysis first to enable semantic code search.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <form onSubmit={onSearch} className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={e => onQueryChange(e.target.value)}
          placeholder="Search code semantically… e.g. 'authentication logic'"
          className="flex-1 px-3 py-1.5 text-xs bg-[#0a0b0d] border border-gray-800 rounded-lg text-gray-300 placeholder-gray-600 focus:outline-none focus:border-purple-500/50 transition-all"
        />
        <button
          type="submit"
          disabled={searching || !query.trim()}
          className="px-4 py-1.5 text-xs font-semibold bg-purple-600 hover:bg-purple-500 text-white rounded-lg transition-all disabled:opacity-50 cursor-pointer flex items-center gap-1.5"
        >
          {searching ? <Loader2 className="w-3 h-3 animate-spin" /> : <Search className="w-3 h-3" />}
          Search
        </button>
      </form>

      {error && (
        <div className="text-xs text-rose-400 p-2 bg-rose-500/5 border border-rose-800/20 rounded-lg">{error}</div>
      )}

      {results.length > 0 && (
        <div className="space-y-2 max-h-[52vh] overflow-y-auto pr-1">
          {results.map((r, i) => (
            <div key={r.chunk_id} className="p-3 rounded-lg bg-[#0a0b0d] border border-gray-800 hover:border-gray-700 transition-colors">
              <div className="flex items-start justify-between gap-2 mb-2">
                <div className="flex items-center gap-1.5 min-w-0">
                  <FileCode className="w-3 h-3 text-purple-400 flex-shrink-0" />
                  <span className="text-[11px] text-gray-300 font-mono truncate">{r.file_path}</span>
                  <span className="text-[10px] text-gray-600 font-mono flex-shrink-0">:{r.start_line}-{r.end_line}</span>
                </div>
                <div className="flex items-center gap-1.5 flex-shrink-0">
                  {r.symbol_name && (
                    <span className="text-[9px] text-sky-400 bg-sky-500/10 border border-sky-500/20 px-1.5 py-0.5 rounded font-mono">
                      {r.symbol_name}
                    </span>
                  )}
                  <span className="text-[9px] text-gray-600">#{i + 1}</span>
                </div>
              </div>
              <pre className="text-[10px] text-gray-400 font-mono leading-relaxed overflow-x-auto whitespace-pre-wrap max-h-28 overflow-y-hidden">
                {r.content}
              </pre>
            </div>
          ))}
        </div>
      )}

      {!searching && results.length === 0 && query && (
        <div className="text-center text-gray-600 text-xs py-6">No results found for this query.</div>
      )}
    </div>
  );
};
