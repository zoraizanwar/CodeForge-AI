import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { repositoryApi } from '../services/repository';
import { jobsApi, type AgentJob } from '../services/jobs';
import { agentRunsApi, type AgentRun } from '../services/agentRuns';
import { AnalysisPanel } from '../components/AnalysisPanel';
import { AgentPanel } from '../components/AgentPanel';
import { JobMonitor } from '../components/JobMonitor';
import { AgentWorkflow } from '../components/AgentWorkflow';
import type { RepositoryResponse, FileTreeItem, FileContentResponse } from '../services/repository';
import { 
  Folder, 
  FolderOpen, 
  FileCode, 
  FileText, 
  ChevronRight, 
  ChevronDown, 
  RefreshCw, 
  Trash2, 
  ArrowLeft, 
  Cpu, 
  Layers,
  Terminal,
  Globe,
  ExternalLink
} from 'lucide-react';

export const RepositoryDetail: React.FC = () => {
  const { repoId } = useParams<{ repoId: string }>();
  const navigate = useNavigate();

  const [repo, setRepo] = useState<RepositoryResponse | null>(null);
  const [tree, setTree] = useState<FileTreeItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // File viewing states
  const [selectedFile, setSelectedFile] = useState<FileContentResponse | null>(null);
  const [fileLoading, setFileLoading] = useState<boolean>(false);
  const [fileError, setFileError] = useState<string | null>(null);

  // Syncing states
  const [syncing, setSyncing] = useState<boolean>(false);

  const [expandedFolders, setExpandedFolders] = useState<Record<string, boolean>>({});

  const [activeJobs, setActiveJobs] = useState<AgentJob[]>([]);
  const [activeRuns, setActiveRuns] = useState<AgentRun[]>([]);

  const fetchRepoData = async (silent = false) => {
    if (!repoId) return;
    if (!silent) setLoading(true);
    try {
      const metadata = await repositoryApi.getRepository(repoId);
      setRepo(metadata);
      
      if (metadata.status === 'indexed') {
        const fileTree = await repositoryApi.getRepositoryTree(repoId);
        setTree(fileTree);
      }

      const jobs = await jobsApi.listJobs(repoId);
      setActiveJobs(jobs.filter(j => ['queued', 'running', 'retrying', 'cancelling'].includes(j.status)));

      const runs = await agentRunsApi.listRuns(repoId);
      setActiveRuns(runs.filter(r => ['pending', 'running', 'reviewing', 'testing', 'repairing', 'human_review_required'].includes(r.status)));
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to load repository.');
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    fetchRepoData();
  }, [repoId]);

  // Poll status if repository is importing/indexing
  useEffect(() => {
    if (repo?.status === 'importing') {
      const interval = setInterval(() => {
        fetchRepoData(true);
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [repo]);

  const handleSync = async () => {
    if (!repoId) return;
    setSyncing(true);
    setErrorMsg(null);
    try {
      await repositoryApi.reindexRepository(repoId);
      setRepo(prev => prev ? { ...prev, status: 'importing' } : null);
      setSelectedFile(null);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to trigger sync.');
    } finally {
      setSyncing(false);
    }
  };

  const handleDelete = async () => {
    if (!repoId) return;
    const confirm = window.confirm("Are you sure you want to disconnect and delete this project workspace from CodeForge AI? This will not delete the repository on GitHub.");
    if (!confirm) return;

    try {
      await repositoryApi.deleteRepository(repoId);
      navigate('/');
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to delete repository.');
    }
  };

  const handleFileClick = async (filePath: string) => {
    if (!repoId) return;
    setFileLoading(true);
    setFileError(null);
    setSelectedFile(null);
    try {
      const fileData = await repositoryApi.readRepositoryFile(repoId, filePath);
      setSelectedFile(fileData);
    } catch (err: any) {
      setFileError(err.message || 'Failed to read file.');
    } finally {
      setFileLoading(false);
    }
  };

  const toggleFolder = (folderPath: string) => {
    setExpandedFolders(prev => ({
      ...prev,
      [folderPath]: !prev[folderPath]
    }));
  };

  // Helper to render tree nodes recursively
  const renderTreeNodes = (nodes: FileTreeItem[], depth = 0) => {
    return nodes.map((node) => {
      const isDir = node.type === 'directory';
      const isOpen = expandedFolders[node.path];
      const hasChildren = node.children && node.children.length > 0;

      return (
        <div key={node.path} className="select-none font-sans">
          <div 
            onClick={() => isDir ? toggleFolder(node.path) : handleFileClick(node.path)}
            className={`flex items-center gap-1.5 py-1 px-2 rounded text-xs cursor-pointer transition-all hover:bg-gray-850 ${
              selectedFile?.path === node.path 
                ? 'bg-purple-600/10 border border-purple-500/20 text-purple-400 font-medium' 
                : 'text-gray-400 hover:text-gray-200 border border-transparent'
            }`}
            style={{ paddingLeft: `${depth * 12 + 8}px` }}
          >
            {isDir ? (
              <>
                <span className="text-gray-500">
                  {isOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                </span>
                <span className="text-purple-400">
                  {isOpen ? <FolderOpen className="w-4 h-4" /> : <Folder className="w-4 h-4" />}
                </span>
              </>
            ) : (
              <>
                <span className="w-3.5" /> {/* Align indent spacer */}
                <span className="text-gray-500">
                  {node.name.endsWith('.md') ? <FileText className="w-4 h-4" /> : <FileCode className="w-4 h-4" />}
                </span>
              </>
            )}
            <span className="truncate">{node.name}</span>
          </div>

          {isDir && isOpen && hasChildren && (
            <div className="mt-0.5">
              {renderTreeNodes(node.children || [], depth + 1)}
            </div>
          )}
        </div>
      );
    });
  };

  if (loading) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center text-gray-500 font-sans">
        <RefreshCw className="w-8 h-8 animate-spin text-purple-500 mb-3" />
        <p className="text-xs uppercase tracking-widest font-semibold text-gray-600">Loading codebase...</p>
      </div>
    );
  }

  if (errorMsg || !repo) {
    return (
      <div className="max-w-md mx-auto mt-12 p-6 bg-[#121319] border border-gray-800 rounded-xl text-center space-y-4 font-sans">
        <h2 className="text-base font-bold text-rose-450">Error Loading Codebase</h2>
        <p className="text-xs text-gray-400">{errorMsg || 'Workspace not found.'}</p>
        <button 
          onClick={() => navigate('/')}
          className="inline-flex items-center gap-1.5 px-4 py-2 text-xs bg-gray-800 hover:bg-gray-700 text-gray-200 rounded-lg cursor-pointer transition-all"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Dashboard
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6 font-sans">
      {/* Top Header Navigation */}
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-800 pb-5">
        <div className="flex items-center gap-3">
          <button 
            onClick={() => navigate('/')}
            className="p-2 bg-[#121319] hover:bg-gray-800 border border-gray-800 rounded-lg text-gray-400 hover:text-gray-200 transition-all cursor-pointer"
            title="Back to Dashboard"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-white tracking-tight">{repo.name}</h1>
              <span className={`text-[9px] px-1.5 py-0.5 rounded font-mono font-semibold ${
                repo.status === 'indexed' ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400' :
                repo.status === 'failed' ? 'bg-rose-500/10 border border-rose-500/20 text-rose-450' :
                'bg-purple-500/10 border border-purple-500/20 text-purple-400 animate-pulse'
              }`}>
                {repo.status.toUpperCase()}
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-0.5">
              Owner: <span className="text-gray-400">{repo.owner}</span> • Default Branch: <span className="font-mono bg-gray-900 border border-gray-850 px-1 py-0.2 rounded text-gray-400">{repo.default_branch}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <a
            href="http://localhost:8080"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-all shadow-md shadow-emerald-600/20 cursor-pointer"
          >
            <Globe className="w-3.5 h-3.5" />
            Open Live Website (http://localhost:8080)
            <ExternalLink className="w-3 h-3" />
          </a>
          <button
            onClick={handleSync}
            disabled={syncing || repo.status === 'importing'}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold bg-[#121319] hover:bg-gray-800 border border-gray-800 text-gray-300 rounded-lg disabled:opacity-50 transition-all cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${syncing || repo.status === 'importing' ? 'animate-spin' : ''}`} />
            Sync Codebase
          </button>
          <button
            onClick={handleDelete}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold bg-rose-950/20 hover:bg-rose-900/25 border border-rose-800/30 text-rose-400 rounded-lg transition-all cursor-pointer"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Delete Project
          </button>
        </div>
      </header>

      {/* Main Grid View */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        
        {/* Left Column Pane: File tree and statistics */}
        <div className="lg:col-span-1 space-y-6">
          
          {/* Active Multi-Agent Workflows */}
          {activeRuns.length > 0 && repoId && (
            <div className="space-y-3">
              <h2 className="text-xs font-bold uppercase tracking-wider text-purple-400 flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5" /> Active Multi-Agent Runs ({activeRuns.length})
              </h2>
              {activeRuns.map(r => (
                <AgentWorkflow key={r.id} repoId={repoId} runId={r.id} />
              ))}
            </div>
          )}

          {/* Active Job Monitors */}
          {activeJobs.length > 0 && (
            <div className="space-y-3">
              <h2 className="text-xs font-bold uppercase tracking-wider text-indigo-400 flex items-center gap-1.5">
                <Terminal className="w-3.5 h-3.5" /> Active Durable Jobs ({activeJobs.length})
              </h2>
              {activeJobs.map(j => (
                <JobMonitor key={j.id} jobId={j.id} />
              ))}
            </div>
          )}

          {/* Metadata Cards */}
          <div className="p-4 bg-[#121319] border border-gray-800 rounded-xl space-y-4">
            <h2 className="text-xs font-bold uppercase tracking-wider text-gray-500 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-purple-400" />
              Codebase Index
            </h2>
            
            {repo.languages && Object.keys(repo.languages).length > 0 && (
              <div className="space-y-2">
                <p className="text-[10px] text-gray-400 font-semibold uppercase">Languages</p>
                <div className="space-y-1.5">
                  {Object.entries(repo.languages).map(([lang, pct]) => (
                    <div key={lang} className="text-xs">
                      <div className="flex justify-between text-gray-300">
                        <span>{lang}</span>
                        <span>{pct}%</span>
                      </div>
                      <div className="w-full h-1 bg-gray-900 rounded-full overflow-hidden mt-1">
                        <div className="h-full bg-purple-650" style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {repo.frameworks && repo.frameworks.length > 0 && (
              <div className="space-y-2 pt-2 border-t border-gray-850">
                <p className="text-[10px] text-gray-400 font-semibold uppercase">Frameworks</p>
                <div className="flex flex-wrap gap-1">
                  {repo.frameworks.map((fw) => (
                    <span key={fw} className="text-[10px] px-2 py-0.5 rounded bg-purple-600/10 border border-purple-500/20 text-purple-400">
                      {fw}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {repo.dependency_files && repo.dependency_files.length > 0 && (
              <div className="space-y-2 pt-2 border-t border-gray-850">
                <p className="text-[10px] text-gray-400 font-semibold uppercase">Configuration Files</p>
                <div className="space-y-1 font-mono text-[10px] text-gray-500">
                  {repo.dependency_files.map((file) => (
                    <div key={file} className="flex items-center gap-1">
                      <span className="w-1 h-1 rounded-full bg-gray-600" />
                      {file}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Collapsible File tree List */}
          <div className="p-4 bg-[#121319] border border-gray-800 rounded-xl space-y-3">
            <h2 className="text-xs font-bold uppercase tracking-wider text-gray-500 flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-purple-400" />
              File Tree
            </h2>
            
            {repo.status === 'importing' ? (
              <div className="text-xs text-purple-400 italic py-2 animate-pulse">
                Codebase is indexing, file tree is currently loading...
              </div>
            ) : repo.status === 'failed' ? (
              <div className="text-xs text-rose-450 italic py-2">
                Failed to index codebase. Check connection logs.
              </div>
            ) : tree.length === 0 ? (
              <div className="text-xs text-gray-500 italic py-2">
                Workspace is empty.
              </div>
            ) : (
              <div className="space-y-0.5 max-h-[50vh] overflow-y-auto pr-1">
                {renderTreeNodes(tree)}
              </div>
            )}
          </div>
        </div>

        {/* Right Column Pane: Code viewer panels */}
        <div className="lg:col-span-3">
          <div className="bg-[#121319] border border-gray-800 rounded-xl min-h-[60vh] flex flex-col justify-between overflow-hidden">
            
            {/* Code Viewer Panel Header */}
            <div className="h-12 border-b border-gray-800 flex items-center justify-between px-6 bg-[#16171e]/50 font-mono text-[11px] text-gray-400 select-none">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-purple-400" />
                <span>{selectedFile ? selectedFile.path : 'inspect_panel.sh'}</span>
              </div>
              {selectedFile && (
                <span>{(selectedFile.size / 1024).toFixed(1)} KB</span>
              )}
            </div>

            {/* Code Viewer Panel Content */}
            <div className="flex-1 p-6 font-mono text-xs overflow-auto bg-[#0a0b0d]">
              {fileLoading ? (
                <div className="h-full flex flex-col items-center justify-center text-gray-600 gap-2">
                  <RefreshCw className="w-6 h-6 animate-spin text-purple-500" />
                  <p>Loading code contents...</p>
                </div>
              ) : fileError ? (
                <div className="h-full flex items-center justify-center text-rose-450 font-medium bg-rose-500/5 border border-rose-950/20 rounded p-4">
                  {fileError}
                </div>
              ) : selectedFile ? (
                <pre className="text-gray-300 leading-relaxed overflow-x-auto select-text whitespace-pre-wrap">
                  {selectedFile.content}
                </pre>
              ) : (
                <div className="h-full min-h-[45vh] flex flex-col items-center justify-center text-center text-gray-600 space-y-2">
                  <FileCode className="w-12 h-12 text-gray-800" />
                  <div>
                    <h3 className="text-gray-400 text-sm font-semibold">No file selected</h3>
                    <p className="text-[11px] max-w-xs mt-1">Select an active file from the file tree structure on the left side to display its source contents.</p>
                  </div>
                </div>
              )}
            </div>

            {/* Code Viewer Panel Footer bar */}
            <div className="h-8 border-t border-gray-850 px-6 flex items-center bg-[#121319] text-[10px] text-gray-500 font-mono select-none">
              <span>utf-8 • target: windows-local</span>
            </div>
          </div>
        </div>

      </div>

      {/* Analysis Panel & Agent Panel — full width below the code explorer */}
      {repoId && repo.status === 'indexed' && (
        <>
          <AgentPanel repoId={repoId} repoStatus={repo.status} />
          <AnalysisPanel repoId={repoId} repoStatus={repo.status} />
        </>
      )}
    </div>
  );
};
