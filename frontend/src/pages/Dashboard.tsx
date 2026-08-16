import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import type { InfoResponse } from '../services/api';
import { githubApi } from '../services/github';
import type { GitHubStatusResponse, GitHubRepositoriesResponse } from '../services/github';
import { repositoryApi } from '../services/repository';
import type { RepositoryResponse } from '../services/repository';
import { GitBranch, Box, FileText, ArrowRight, Cpu } from 'lucide-react';

export const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const [apiInfo, setApiInfo] = useState<InfoResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  
  // GitHub Integration States
  const [githubStatus, setGithubStatus] = useState<GitHubStatusResponse>({ connected: false });
  const [reposResponse, setReposResponse] = useState<GitHubRepositoriesResponse | null>(null);
  const [reposLoading, setReposLoading] = useState<boolean>(false);
  const [showRepos, setShowRepos] = useState<boolean>(false);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // CodeForge Repository States
  const [importedRepos, setImportedRepos] = useState<RepositoryResponse[]>([]);

  const fetchGithubStatus = async () => {
    try {
      const status = await githubApi.getGitHubStatus();
      setGithubStatus(status);
    } catch (err) {
      console.error("Failed to fetch GitHub status:", err);
    }
  };

  const fetchImportedRepos = async () => {
    try {
      const list = await repositoryApi.listRepositories();
      setImportedRepos(list);
    } catch (err) {
      console.error("Failed to fetch imported repositories:", err);
    }
  };

  useEffect(() => {
    const fetchInfo = async () => {
      try {
        const info = await api.getV1Info();
        setApiInfo(info);
      } catch (err) {
        console.error("Failed to fetch API metadata info:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchInfo();
    fetchGithubStatus();
    fetchImportedRepos();

    // Check for callback redirect search params
    const params = new URLSearchParams(window.location.search);
    if (params.get('github') === 'connected') {
      window.history.replaceState({}, document.title, window.location.pathname);
      fetchGithubStatus();
    }
  }, []);

  // Poll for status updates every 5 seconds if any repo is in 'importing' status
  useEffect(() => {
    const hasImporting = importedRepos.some(r => r.status === 'importing');
    if (hasImporting) {
      const interval = setInterval(fetchImportedRepos, 5000);
      return () => clearInterval(interval);
    }
  }, [importedRepos]);

  const handleConnect = async () => {
    setActionLoading(true);
    setErrorMsg(null);
    try {
      const response = await githubApi.connectGitHub();
      window.location.href = response.url;
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to connect GitHub App.');
      setActionLoading(false);
    }
  };

  const handleSync = async () => {
    setActionLoading(true);
    setErrorMsg(null);
    try {
      const status = await githubApi.syncGitHub();
      setGithubStatus(status);
      if (status.connected) {
        const response = await githubApi.getRepositories(1, 100);
        setReposResponse(response);
        setShowRepos(true);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to sync GitHub connection.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDisconnect = async () => {
    setActionLoading(true);
    setErrorMsg(null);
    try {
      await githubApi.disconnectGitHub();
      setGithubStatus({ connected: false });
      setReposResponse(null);
      setShowRepos(false);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to disconnect GitHub.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleViewRepos = async () => {
    if (showRepos) {
      setShowRepos(false);
      return;
    }
    setReposLoading(true);
    setErrorMsg(null);
    try {
      const response = await githubApi.getRepositories(1, 100);
      setReposResponse(response);
      setShowRepos(true);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to fetch repositories.');
    } finally {
      setReposLoading(false);
    }
  };

  const handleImport = async (githubRepoId: number) => {
    setActionLoading(true);
    setErrorMsg(null);
    try {
      await repositoryApi.importRepository(githubRepoId);
      await fetchImportedRepos();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to import repository.');
    } finally {
      setActionLoading(false);
    }
  };

  const steps = [
    { title: '1. Connect Repository', desc: 'Securely authenticate and index your GitHub or local git repository.' },
    { title: '2. Issue Goal Instructions', desc: 'Describe the feature, bugfix, or coding task you want CodeForge to solve.' },
    { title: '3. Approve AI Execution Plan', desc: 'Review the generated multi-file implementation plan and proposed file modifications.' },
    { title: '4. Automatic Code & Verify', desc: 'The agent patches the code, runs tests in a secure sandbox, and creates a Pull Request.' },
  ];

  return (
    <div className="max-w-5xl mx-auto space-y-12">
      {/* Hero Welcome Header */}
      <section className="space-y-4">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-purple-600/10 border border-purple-500/20 text-purple-400 text-xs font-medium">
          <Cpu className="w-3.5 h-3.5" /> Project Foundation Active
        </div>
        <h1 className="text-4xl font-extrabold tracking-tight text-white sm:text-5xl">
          Meet <span className="text-purple-500">CodeForge AI</span>
        </h1>
        <p className="text-lg text-gray-400 max-w-2xl font-light">
          An autonomous, tool-equipped software engineering agent designed to solve complex codebase tasks, run test suites inside isolated sandboxes, and submit pull requests.
        </p>
      </section>

      {/* GitHub Integration Panel */}
      <section className="bg-[#121319] border border-gray-800 rounded-xl p-6 space-y-4 relative overflow-hidden">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="bg-purple-600/10 p-3 rounded-lg text-purple-400">
              <GitBranch className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white">GitHub Integration</h2>
              <p className="text-xs text-gray-400">
                {githubStatus.connected 
                  ? `Connected to GitHub App as @${githubStatus.github_login} (${githubStatus.github_account_type})` 
                  : 'Link your GitHub App installation to list authorized repositories.'
                }
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {githubStatus.connected ? (
              <>
                <button
                  onClick={handleSync}
                  disabled={actionLoading}
                  className="px-3 py-2 text-xs font-semibold bg-gray-800 border border-gray-700 text-gray-300 hover:bg-gray-750 rounded-lg disabled:opacity-50 transition-all cursor-pointer"
                  title="Sync GitHub installation"
                >
                  Sync
                </button>
                <button
                  onClick={handleViewRepos}
                  disabled={reposLoading || actionLoading}
                  className="px-4 py-2 text-xs font-semibold bg-purple-650 text-white hover:bg-purple-600 rounded-lg disabled:opacity-50 transition-all cursor-pointer"
                >
                  {reposLoading ? 'Loading...' : showRepos ? 'Hide Repositories' : 'View Repositories'}
                </button>
                <button
                  onClick={handleDisconnect}
                  disabled={actionLoading}
                  className="px-4 py-2 text-xs font-semibold bg-rose-950/30 border border-rose-800/40 text-rose-400 hover:bg-rose-900/25 rounded-lg disabled:opacity-50 transition-all cursor-pointer"
                >
                  Disconnect
                </button>
              </>
            ) : (
              <div className="flex items-center gap-2">
                <button
                  onClick={handleConnect}
                  disabled={actionLoading}
                  className="px-4 py-2 text-xs font-semibold bg-purple-600 hover:bg-purple-500 text-white rounded-lg disabled:opacity-50 transition-all cursor-pointer"
                >
                  {actionLoading ? 'Connecting...' : 'Connect GitHub'}
                </button>
                <button
                  onClick={handleSync}
                  disabled={actionLoading}
                  className="px-3 py-2 text-xs font-semibold bg-gray-800 border border-gray-700 text-gray-300 hover:bg-gray-750 rounded-lg disabled:opacity-50 transition-all cursor-pointer"
                  title="Sync existing GitHub installation if already saved on GitHub"
                >
                  Sync Connection
                </button>
              </div>
            )}
          </div>
        </div>


        {errorMsg && (
          <div className="p-3 text-xs bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded-lg">
            {errorMsg}
          </div>
        )}

        {/* Repository Grid List */}
        {showRepos && reposResponse && (
          <div className="border-t border-gray-800 pt-4 mt-2 space-y-3">
            <div className="flex justify-between items-center text-xs text-gray-500 mb-2">
              <span>Authorized Repositories ({reposResponse.total_count})</span>
            </div>
            {reposResponse.repositories.length === 0 ? (
              <p className="text-xs text-gray-500 italic">No repositories found or authorized for this installation.</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-96 overflow-y-auto pr-1">
                {reposResponse.repositories.map((repo) => {
                  const imported = importedRepos.find(r => r.github_repo_id === repo.id);
                  return (
                    <div
                      key={repo.id}
                      className="p-3 bg-[#0e0f13] border border-gray-800/60 rounded-lg flex items-center justify-between"
                    >
                      <div className="min-w-0 pr-2">
                        <div className="flex items-center gap-1.5">
                          <span className="text-xs font-bold text-gray-300 truncate">
                            {repo.name}
                          </span>
                          <span className={`text-[9px] px-1.5 py-0.5 rounded font-mono ${repo.private ? 'bg-amber-500/10 border border-amber-500/20 text-amber-400' : 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400'}`}>
                            {repo.private ? 'Private' : 'Public'}
                          </span>
                        </div>
                        <p className="text-[10px] text-gray-500 truncate mt-1">
                          Owner: {repo.owner.login} • Branch: <span className="font-mono text-[9px] bg-gray-900 border border-gray-850 px-1 py-0.2 rounded text-gray-400">{repo.default_branch}</span>
                        </p>
                      </div>

                      <div className="flex-shrink-0">
                        {imported ? (
                          imported.status === 'indexed' ? (
                            <button
                              onClick={() => navigate(`/repositories/${imported.id}`)}
                              className="px-2.5 py-1.5 text-[10px] font-bold bg-purple-650 hover:bg-purple-600 text-white rounded transition-all cursor-pointer"
                            >
                              Open
                            </button>
                          ) : imported.status === 'importing' ? (
                            <span className="text-[10px] text-purple-400 font-mono animate-pulse">
                              Importing...
                            </span>
                          ) : (
                            <button
                              onClick={() => handleImport(repo.id)}
                              className="px-2.5 py-1.5 text-[10px] font-bold bg-rose-950/20 border border-rose-900/40 text-rose-450 rounded transition-all cursor-pointer"
                            >
                              Retry
                            </button>
                          )
                        ) : (
                          <button
                            onClick={() => handleImport(repo.id)}
                            className="px-2.5 py-1.5 text-[10px] font-bold bg-gray-800 hover:bg-gray-700 text-gray-205 rounded transition-all cursor-pointer"
                          >
                            Import
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </section>

      {/* Connected / Imported Repositories Grid */}
      {importedRepos.length > 0 && (
        <section className="space-y-4">
          <h2 className="text-xl font-bold text-white">Imported Projects</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {importedRepos.map((repo) => (
              <div 
                key={repo.id}
                className="p-5 bg-[#121319] border border-gray-800 rounded-xl flex flex-col justify-between gap-4"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold text-gray-205 truncate pr-2" title={repo.full_name}>
                      {repo.name}
                    </h3>
                    <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-semibold ${
                      repo.status === 'indexed' ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400' :
                      repo.status === 'failed' ? 'bg-rose-500/10 border border-rose-500/20 text-rose-450' :
                      'bg-purple-500/10 border border-purple-500/20 text-purple-400 animate-pulse'
                    }`}>
                      {repo.status.toUpperCase()}
                    </span>
                  </div>
                  <p className="text-[10px] text-gray-500 mt-1 font-mono">{repo.owner} • branch: {repo.default_branch}</p>
                  
                  {repo.error_message && (
                    <p className="text-[11px] text-rose-400/80 bg-rose-500/5 p-2 rounded border border-rose-950/20 mt-2 font-mono truncate" title={repo.error_message}>
                      {repo.error_message}
                    </p>
                  )}

                  {repo.languages && Object.keys(repo.languages).length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-3">
                      {Object.entries(repo.languages).slice(0, 3).map(([lang, pct]) => (
                        <span key={lang} className="text-[9px] px-1.5 py-0.5 rounded bg-gray-900 border border-gray-800 text-gray-400 font-mono">
                          {lang}: {pct}%
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-between border-t border-gray-850 pt-3 text-xs">
                  <span className="text-gray-500 text-[10px]">
                    {repo.last_indexed_at ? `Synced: ${new Date(repo.last_indexed_at).toLocaleTimeString()}` : 'Not synced yet'}
                  </span>
                  
                  <div className="flex items-center gap-2">
                    {repo.status === 'indexed' ? (
                      <button
                        onClick={() => navigate(`/repositories/${repo.id}`)}
                        className="px-3 py-1.5 text-[11px] font-semibold bg-purple-650 hover:bg-purple-600 text-white rounded-md cursor-pointer transition-all"
                      >
                        View Codebase
                      </button>
                    ) : repo.status === 'failed' ? (
                      <button
                        onClick={() => handleImport(repo.github_repo_id)}
                        className="px-3 py-1.5 text-[11px] font-semibold bg-gray-800 hover:bg-gray-750 text-gray-200 rounded-md cursor-pointer transition-all"
                      >
                        Retry Import
                      </button>
                    ) : (
                      <span className="text-[10px] text-purple-400 font-mono flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-ping" />
                        Indexing...
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Backend API Info Box */}
      <section className="bg-[#121319] border border-gray-800 rounded-xl p-6 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-purple-600/5 rounded-full blur-3xl pointer-events-none" />
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-500">Backend Core Metadata</h2>
            {loading ? (
              <div className="h-6 w-48 bg-gray-800 animate-pulse rounded" />
            ) : apiInfo ? (
              <div className="space-y-1">
                <p className="text-lg font-bold text-white">{apiInfo.name}</p>
                <p className="text-sm text-gray-400">{apiInfo.description}</p>
              </div>
            ) : (
              <div className="text-sm text-rose-400">Unable to query API server. Ensure backend is running.</div>
            )}
          </div>
          <div className="flex items-center gap-4 text-xs font-mono text-gray-400">
            <div className="px-3 py-2 bg-gray-900 border border-gray-800 rounded-md">
              API Version: <span className="text-purple-400">{apiInfo?.version || 'N/A'}</span>
            </div>
            <div className="px-3 py-2 bg-gray-900 border border-gray-800 rounded-md">
              Env: <span className="text-purple-400">Development</span>
            </div>
          </div>
        </div>
      </section>

      {/* Workflow Step Grid */}
      <section className="space-y-6">
        <h2 className="text-xl font-bold text-white">Agent Operations Pipeline</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {steps.map((step, idx) => (
            <div 
              key={idx} 
              className="p-5 bg-[#121319]/40 border border-gray-800/80 rounded-xl hover:border-gray-800 transition-all duration-200"
            >
              <h3 className="text-sm font-bold text-gray-300 mb-1">{step.title}</h3>
              <p className="text-xs text-gray-500 leading-relaxed">{step.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Feature Focus Cards */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Repo index */}
        <div className="p-6 bg-[#121319] border border-gray-800 rounded-xl space-y-4">
          <div className="p-3 bg-purple-600/10 text-purple-400 rounded-lg w-fit">
            <GitBranch className="w-6 h-6" />
          </div>
          <h3 className="text-base font-bold text-white">GitHub Integrations</h3>
          <p className="text-xs text-gray-400 leading-relaxed">
            Dynamic repository checkout, branch management, and automated Pull Request creation based on developer feedback loops.
          </p>
        </div>

        {/* Sandbox */}
        <div className="p-6 bg-[#121319] border border-gray-800 rounded-xl space-y-4">
          <div className="p-3 bg-purple-600/10 text-purple-400 rounded-lg w-fit">
            <Box className="w-6 h-6" />
          </div>
          <h3 className="text-base font-bold text-white">Safe Execution Sandbox</h3>
          <p className="text-xs text-gray-400 leading-relaxed">
            Executes generated code modifications inside an isolated Docker sandbox. Verifies tests and captures standard outputs safely.
          </p>
        </div>

        {/* AI Planning */}
        <div className="p-6 bg-[#121319] border border-gray-800 rounded-xl space-y-4">
          <div className="p-3 bg-purple-600/10 text-purple-400 rounded-lg w-fit">
            <FileText className="w-6 h-6" />
          </div>
          <h3 className="text-base font-bold text-white">Dynamic AI Planning</h3>
          <p className="text-xs text-gray-400 leading-relaxed">
            Analyzes existing files using modular AI Providers (supporting Grok, OpenAI, Ollama), generating human-readable diff logs.
          </p>
        </div>
      </section>

      {/* Quick Launch Panel */}
      <section className="p-6 bg-gradient-to-r from-purple-900/10 to-[#121319] border border-purple-500/20 rounded-xl flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <h3 className="text-base font-bold text-white">Start Building in Step 2</h3>
          <p className="text-xs text-gray-400">Connect your repository and run your first autonomous agent run loop.</p>
        </div>
        <button 
          disabled
          className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm bg-purple-600 text-white font-medium hover:bg-purple-500 disabled:opacity-50 disabled:hover:bg-purple-600 cursor-not-allowed select-none transition-all"
        >
          Initialize Agent Run <ArrowRight className="w-4 h-4" />
        </button>
      </section>
    </div>
  );
};
