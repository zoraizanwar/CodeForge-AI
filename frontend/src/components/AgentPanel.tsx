import React, { useState, useEffect } from 'react';
import { agentApi } from '../services/agent';
import type { AgentTask, FileChange, AgentExecution, GitOperation, AgentIteration } from '../services/agent';
import { 
  Bot, 
  Play, 
  CheckCircle, 
  AlertCircle, 
  Clock, 
  FileCode, 
  Sparkles, 
  RefreshCw, 
  FilePlus, 
  FileEdit, 
  FileMinus,
  ChevronRight,
  ShieldAlert,
  Code,
  Terminal,
  PlayCircle,
  AlertTriangle,
  XCircle,
  Activity,
  GitPullRequest,
  GitBranch,
  GitCommit,
  ExternalLink,
  ThumbsUp,
  ShieldCheck,
  Wrench
} from 'lucide-react';
import { agentRunsApi } from '../services/agentRuns';
import { AgentWorkflow } from './AgentWorkflow';

interface AgentPanelProps {
  repoId: string;
  repoStatus: string;
}

export const AgentPanel: React.FC<AgentPanelProps> = ({ repoId, repoStatus }) => {
  const [taskInput, setTaskInput] = useState('');
  const [tasks, setTasks] = useState<AgentTask[]>([]);
  const [selectedTask, setSelectedTask] = useState<AgentTask | null>(null);
  const [taskChanges, setTaskChanges] = useState<FileChange[]>([]);
  const [executions, setExecutions] = useState<AgentExecution[]>([]);
  const [selectedExecution, setSelectedExecution] = useState<AgentExecution | null>(null);
  const [gitOps, setGitOps] = useState<GitOperation[]>([]);
  const [activeGitOp, setActiveGitOp] = useState<GitOperation | null>(null);
  const [iterations, setIterations] = useState<AgentIteration[]>([]);
  const [activeIteration, setActiveIteration] = useState<AgentIteration | null>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'plan' | 'changes' | 'execution' | 'git' | 'repair' | 'multi_agent'>('plan');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [isCreatingPR, setIsCreatingPR] = useState(false);
  const [isRepairing, setIsRepairing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pollInterval, setPollInterval] = useState<number | null>(null);

  // Fetch all tasks on mount
  useEffect(() => {
    loadTasks();
  }, [repoId]);

  // Polling for active task, execution, Git operation & repair iteration status
  useEffect(() => {
    if (
      (selectedTask && ['pending', 'analyzing', 'planning', 'generating', 'executing', 'repairing'].includes(selectedTask.status)) ||
      (activeGitOp && ['pending', 'preparing', 'applying', 'committing', 'pushing', 'creating_pr'].includes(activeGitOp.status)) ||
      (activeIteration && ['analyzing', 'planning', 'generating', 'validating', 'executing'].includes(activeIteration.status))
    ) {
      const interval = window.setInterval(async () => {
        try {
          if (!selectedTask) return;
          const updatedTask = await agentApi.getTask(repoId, selectedTask.id);
          setSelectedTask(updatedTask);
          setTasks(prev => prev.map(t => t.id === updatedTask.id ? updatedTask : t));

          loadTaskChanges(updatedTask.id);
          loadTaskExecutions(updatedTask.id);
          loadGitOperations(updatedTask.id);
          loadIterations(updatedTask.id);
        } catch (err) {
          console.error('Polling task error:', err);
        }
      }, 2000);
      setPollInterval(interval);
      return () => clearInterval(interval);
    } else if (pollInterval) {
      clearInterval(pollInterval);
      setPollInterval(null);
    }
  }, [selectedTask?.id, selectedTask?.status, activeGitOp?.status, activeIteration?.status]);

  const loadTasks = async () => {
    try {
      const list = await agentApi.getTasks(repoId);
      setTasks(list);
      if (list.length > 0 && !selectedTask) {
        selectTask(list[0]);
      }
    } catch (err: any) {
      console.error('Failed to load agent tasks:', err);
    }
  };

  const loadTaskChanges = async (taskId: string) => {
    try {
      const res = await agentApi.getChanges(repoId, taskId);
      setTaskChanges(res.changes);
    } catch (err) {
      console.error('Failed to load task changes:', err);
    }
  };

  const loadTaskExecutions = async (taskId: string) => {
    try {
      const list = await agentApi.getExecutions(repoId, taskId);
      setExecutions(list);
      if (list.length > 0) {
        setSelectedExecution(list[0]);
      }
    } catch (err) {
      console.error('Failed to load executions:', err);
    }
  };

  const loadGitOperations = async (taskId: string) => {
    try {
      const list = await agentApi.getGitOperations(repoId, taskId);
      setGitOps(list);
      if (list.length > 0) {
        setActiveGitOp(list[0]);
      }
    } catch (err) {
      console.error('Failed to load Git operations:', err);
    }
  };

  const loadIterations = async (taskId: string) => {
    try {
      const list = await agentApi.getIterations(repoId, taskId);
      setIterations(list);
      if (list.length > 0) {
        setActiveIteration(list[list.length - 1]);
      }
    } catch (err) {
      console.error('Failed to load iterations:', err);
    }
  };

  const handleSubmitTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!taskInput.trim() || isSubmitting) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const newTask = await agentApi.createTask(repoId, taskInput.trim());
      setTaskInput('');
      setTasks(prev => [newTask, ...prev]);
      setSelectedTask(newTask);
      setExecutions([]);
      setSelectedExecution(null);
      setGitOps([]);
      setActiveGitOp(null);
      setIterations([]);
      setActiveIteration(null);
      setActiveTab('plan');
    } catch (err: any) {
      setError(err.message || 'Failed to submit agent task.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRunExecution = async () => {
    if (!selectedTask || isExecuting) return;
    setIsExecuting(true);
    setError(null);

    try {
      const exec = await agentApi.executeTask(repoId, selectedTask.id);
      setSelectedExecution(exec);
      setExecutions(prev => [exec, ...prev]);
      setActiveTab('execution');
      setSelectedTask(prev => prev ? { ...prev, status: 'executing' } : prev);
    } catch (err: any) {
      setError(err.message || 'Failed to trigger test execution.');
    } finally {
      setIsExecuting(false);
    }
  };

  const handleApproveTask = async () => {
    if (!selectedTask || isApproving) return;
    setIsApproving(true);
    setError(null);

    try {
      const approvedTask = await agentApi.approveTask(repoId, selectedTask.id);
      setSelectedTask(approvedTask);
      setTasks(prev => prev.map(t => t.id === approvedTask.id ? approvedTask : t));
    } catch (err: any) {
      setError(err.message || 'Failed to approve task changes.');
    } finally {
      setIsApproving(false);
    }
  };

  const handleCreatePullRequest = async () => {
    if (!selectedTask || isCreatingPR) return;
    setIsCreatingPR(true);
    setError(null);

    try {
      const op = await agentApi.createPullRequest(repoId, selectedTask.id);
      setActiveGitOp(op);
      setGitOps(prev => [op, ...prev]);
      setActiveTab('git');
    } catch (err: any) {
      setError(err.message || 'Failed to trigger Pull Request creation.');
    } finally {
      setIsCreatingPR(false);
    }
  };

  const handleTriggerRepair = async () => {
    if (!selectedTask || isRepairing) return;
    setIsRepairing(true);
    setError(null);

    try {
      const repairedTask = await agentApi.triggerRepair(repoId, selectedTask.id);
      setSelectedTask(repairedTask);
      setActiveTab('repair');
      loadIterations(repairedTask.id);
    } catch (err: any) {
      setError(err.message || 'Failed to trigger repair loop.');
    } finally {
      setIsRepairing(false);
    }
  };

  const handleStartMultiAgentRun = async () => {
    if (!taskInput.trim() || isSubmitting) return;
    setIsSubmitting(true);
    setError(null);

    try {
      const run = await agentRunsApi.startRun(repoId, taskInput.trim(), selectedTask?.id);
      setActiveRunId(run.id);
      setActiveTab('multi_agent');
      setTaskInput('');
    } catch (err: any) {
      setError(err.message || 'Failed to start multi-agent run.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const selectTask = (task: AgentTask) => {
    setSelectedTask(task);
    setTaskChanges([]);
    setExecutions([]);
    setSelectedExecution(null);
    setGitOps([]);
    setActiveGitOp(null);
    setIterations([]);
    setActiveIteration(null);

    loadTaskChanges(task.id);
    loadTaskExecutions(task.id);
    loadGitOperations(task.id);
    loadIterations(task.id);
  };

  const getStatusBadge = (status: AgentTask['status']) => {
    switch (status) {
      case 'pending':
        return <span className="px-2.5 py-1 text-xs font-semibold bg-gray-700 text-gray-300 rounded-full flex items-center gap-1.5"><Clock className="w-3.5 h-3.5" /> Pending</span>;
      case 'analyzing':
        return <span className="px-2.5 py-1 text-xs font-semibold bg-blue-900/60 text-blue-300 border border-blue-700 rounded-full flex items-center gap-1.5 animate-pulse"><RefreshCw className="w-3.5 h-3.5 animate-spin" /> Analyzing</span>;
      case 'planning':
        return <span className="px-2.5 py-1 text-xs font-semibold bg-indigo-900/60 text-indigo-300 border border-indigo-700 rounded-full flex items-center gap-1.5 animate-pulse"><Sparkles className="w-3.5 h-3.5 animate-spin" /> Planning</span>;
      case 'generating':
        return <span className="px-2.5 py-1 text-xs font-semibold bg-purple-900/60 text-purple-300 border border-purple-700 rounded-full flex items-center gap-1.5 animate-pulse"><Bot className="w-3.5 h-3.5 animate-spin" /> Generating</span>;
      case 'ready_for_review':
        return <span className="px-2.5 py-1 text-xs font-semibold bg-emerald-900/60 text-emerald-300 border border-emerald-700 rounded-full flex items-center gap-1.5"><CheckCircle className="w-3.5 h-3.5" /> Ready for Review</span>;
      case 'approved':
        return <span className="px-2.5 py-1 text-xs font-semibold bg-teal-900/80 text-teal-300 border border-teal-600 rounded-full flex items-center gap-1.5"><ShieldCheck className="w-3.5 h-3.5" /> Approved</span>;
      case 'executing':
        return <span className="px-2.5 py-1 text-xs font-semibold bg-amber-900/60 text-amber-300 border border-amber-700 rounded-full flex items-center gap-1.5 animate-pulse"><Activity className="w-3.5 h-3.5 animate-spin" /> Executing Tests</span>;
      case 'execution_failed':
        return <span className="px-2.5 py-1 text-xs font-semibold bg-red-900/80 text-red-300 border border-red-600 rounded-full flex items-center gap-1.5"><XCircle className="w-3.5 h-3.5" /> Tests Failed</span>;
      case 'repairing':
        return <span className="px-2.5 py-1 text-xs font-semibold bg-orange-900/80 text-orange-300 border border-orange-600 rounded-full flex items-center gap-1.5 animate-pulse"><Wrench className="w-3.5 h-3.5 animate-spin" /> Repairing Failure</span>;
      case 'repair_ready':
        return <span className="px-2.5 py-1 text-xs font-semibold bg-emerald-900/60 text-emerald-300 border border-emerald-700 rounded-full flex items-center gap-1.5"><CheckCircle className="w-3.5 h-3.5" /> Repair Ready</span>;
      case 'execution_passed':
        return <span className="px-2.5 py-1 text-xs font-semibold bg-emerald-900/80 text-emerald-300 border border-emerald-600 rounded-full flex items-center gap-1.5"><CheckCircle className="w-3.5 h-3.5" /> Tests Passed</span>;
      case 'human_review_required':
        return <span className="px-2.5 py-1 text-xs font-semibold bg-amber-950 text-amber-400 border border-amber-700 rounded-full flex items-center gap-1.5"><AlertTriangle className="w-3.5 h-3.5" /> Human Review Required</span>;
      case 'pr_created':
        return <span className="px-2.5 py-1 text-xs font-semibold bg-purple-900/90 text-purple-300 border border-purple-600 rounded-full flex items-center gap-1.5"><GitPullRequest className="w-3.5 h-3.5" /> PR Created</span>;
      case 'failed':
        return <span className="px-2.5 py-1 text-xs font-semibold bg-red-900/60 text-red-300 border border-red-700 rounded-full flex items-center gap-1.5"><AlertCircle className="w-3.5 h-3.5" /> Failed</span>;
      default:
        return null;
    }
  };

  const getOperationBadge = (op: FileChange['operation']) => {
    switch (op) {
      case 'create':
        return <span className="px-2 py-0.5 text-xs font-mono font-bold bg-emerald-950 text-emerald-400 border border-emerald-800 rounded flex items-center gap-1"><FilePlus className="w-3 h-3" /> CREATE</span>;
      case 'modify':
        return <span className="px-2 py-0.5 text-xs font-mono font-bold bg-blue-950 text-blue-400 border border-blue-800 rounded flex items-center gap-1"><FileEdit className="w-3 h-3" /> MODIFY</span>;
      case 'delete':
        return <span className="px-2 py-0.5 text-xs font-mono font-bold bg-red-950 text-red-400 border border-red-800 rounded flex items-center gap-1"><FileMinus className="w-3 h-3" /> DELETE</span>;
    }
  };

  const getFileCategoryBadge = (filePath: string) => {
    const p = filePath.toLowerCase();
    const isFrontend = p.startsWith('frontend') || p.includes('src/components') || p.includes('src/pages') || p.endsWith('.tsx') || p.endsWith('.jsx') || p.endsWith('.css') || p.endsWith('.html');
    const isBackend = p.startsWith('backend') || p.includes('app/') || p.includes('api/') || p.includes('services/') || p.endsWith('.py') || p.endsWith('.go') || p.endsWith('.java') || p.endsWith('.sql');

    if (isFrontend) {
      return <span className="px-2 py-0.5 text-[10px] font-mono font-bold rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">FRONTEND UI</span>;
    }
    if (isBackend) {
      return <span className="px-2 py-0.5 text-[10px] font-mono font-bold rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">BACKEND SERVICE</span>;
    }
    return <span className="px-2 py-0.5 text-[10px] font-mono font-bold rounded bg-gray-500/10 text-gray-400 border border-gray-500/20">CONFIG / OTHER</span>;
  };

  const renderDiffLines = (diffStr: string) => {
    if (!diffStr) return <p className="text-gray-500 text-xs italic">No diff available.</p>;

    const lines = diffStr.split('\n');
    return (
      <div className="font-mono text-xs overflow-x-auto bg-gray-950 p-3 rounded-lg border border-gray-800 space-y-0.5 leading-relaxed">
        {lines.map((line, idx) => {
          let bgClass = 'text-gray-300';
          if (line.startsWith('+++') || line.startsWith('---')) {
            bgClass = 'text-gray-400 font-bold';
          } else if (line.startsWith('@@')) {
            bgClass = 'text-cyan-400 font-bold bg-cyan-950/40 px-1 py-0.5 rounded';
          } else if (line.startsWith('+')) {
            bgClass = 'bg-emerald-950/70 text-emerald-300 px-1 py-0.5 rounded-sm block';
          } else if (line.startsWith('-')) {
            bgClass = 'bg-red-950/70 text-red-300 px-1 py-0.5 rounded-sm block';
          }
          return <div key={idx} className={bgClass}>{line || ' '}</div>;
        })}
      </div>
    );
  };

  const latestExecution = executions.length > 0 ? executions[0] : null;
  const isExecutionAllowed = selectedTask && ['ready_for_review', 'approved', 'execution_passed', 'execution_failed', 'repair_ready'].includes(selectedTask.status);
  const latestPassedExec = executions.find(e => e.status === 'passed');
  const isPRCreationAllowed = selectedTask && selectedTask.is_approved && latestPassedExec && (!activeGitOp || activeGitOp.status === 'completed' || activeGitOp.status === 'failed');
  const isRepairAllowed = selectedTask && (latestExecution?.status === 'failed' || selectedTask.status === 'execution_failed') && iterations.length < 3 && selectedTask.status !== 'repairing';

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl shadow-2xl p-6 mt-6">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-800 pb-4 mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-indigo-600/20 border border-indigo-500/30 rounded-xl text-indigo-400">
            <Bot className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              CodeForge AI Engineer
              <span className="text-xs font-normal px-2 py-0.5 rounded bg-orange-950 text-orange-300 border border-orange-800">
                Step 10 Autonomous Feedback Loop
              </span>
            </h2>
            <p className="text-xs text-gray-400">
              Autonomous planning, code generation, sandbox testing, bug fixing, & PR creation
            </p>
          </div>
        </div>
        {selectedTask && getStatusBadge(selectedTask.status)}
      </div>

      {/* Task Submission Form */}
      <form onSubmit={handleSubmitTask} className="mb-6 space-y-3">
        <label className="block text-xs font-semibold text-gray-300 uppercase tracking-wider">
          New Engineering Task
        </label>
        <div className="relative">
          <textarea
            value={taskInput}
            onChange={(e) => setTaskInput(e.target.value)}
            placeholder="Describe what you want CodeForge AI to build or refactor (e.g. 'Add a health check API route in main.py with unit tests')..."
            rows={3}
            disabled={isSubmitting || repoStatus !== 'indexed'}
            className="w-full bg-gray-950 border border-gray-800 rounded-xl p-3.5 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 disabled:opacity-50 transition"
          />
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500">
            {taskInput.length}/2000 chars
          </span>
          <div className="flex gap-2">
          <button
            type="submit"
            disabled={!taskInput.trim() || isSubmitting || repoStatus !== 'indexed'}
            className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-800 text-white text-xs font-semibold rounded-lg flex items-center gap-2 transition shadow-lg shadow-indigo-600/20 disabled:shadow-none"
          >
            {isSubmitting ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" /> Starting Task...
              </>
            ) : (
              <>
                <Play className="w-4 h-4" /> Start AI Agent
              </>
            )}
          </button>
          <button
            type="button"
            onClick={handleStartMultiAgentRun}
            disabled={!taskInput.trim() || isSubmitting || repoStatus !== 'indexed'}
            className="px-5 py-2.5 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-800 text-white text-xs font-semibold rounded-lg flex items-center gap-2 transition shadow-lg shadow-purple-600/20 disabled:shadow-none"
          >
            <Bot className="w-4 h-4" /> Multi-Agent
          </button>
          </div>
        </div>
        {error && (
          <div className="p-3 bg-red-950/60 border border-red-800/80 rounded-lg text-xs text-red-300 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}
      </form>

      {/* Task History Bar */}
      {tasks.length > 0 && (
        <div className="mb-6">
          <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
            Task History ({tasks.length})
          </label>
          <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-thin">
            {tasks.map((task) => (
              <button
                key={task.id}
                onClick={() => selectTask(task)}
                className={`flex-shrink-0 px-3.5 py-2 rounded-lg text-xs font-medium border text-left transition ${
                  selectedTask?.id === task.id
                    ? 'bg-indigo-950/80 border-indigo-500 text-white shadow-md'
                    : 'bg-gray-950 border-gray-800 text-gray-400 hover:text-gray-200 hover:border-gray-700'
                }`}
              >
                <div className="font-semibold truncate max-w-[200px]">
                  {task.task_description}
                </div>
                <div className="text-[10px] text-gray-500 mt-1 flex items-center gap-1">
                  {task.status} {task.is_approved && '• Approved'}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Selected Task Details & Content Area */}
      {selectedTask ? (
        <div className="bg-gray-950 border border-gray-800 rounded-xl p-5 space-y-5">
          {/* Active Task Progress Banner */}
          {['pending', 'analyzing', 'planning', 'generating', 'executing', 'repairing'].includes(selectedTask.status) && (
            <div className="p-4 bg-indigo-950/40 border border-indigo-800/60 rounded-xl flex items-center justify-between">
              <div className="flex items-center gap-3">
                <RefreshCw className="w-5 h-5 text-indigo-400 animate-spin" />
                <div>
                  <h4 className="text-sm font-bold text-white capitalize">
                    Agent Pipeline: {selectedTask.status}
                  </h4>
                  <p className="text-xs text-indigo-300/80">
                    {selectedTask.status === 'analyzing' && 'Retrieving symbols, dependencies, and file context...'}
                    {selectedTask.status === 'planning' && 'Constructing structured architectural implementation plan...'}
                    {selectedTask.status === 'generating' && 'Synthesizing code changes and verifying security boundaries...'}
                    {selectedTask.status === 'executing' && 'Safely applying patch inside temporary workspace & running tests...'}
                    {selectedTask.status === 'repairing' && 'Analyzing execution failure, generating fix, & running validation...'}
                    {selectedTask.status === 'pending' && 'Queued for processing...'}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Action Bar for Execution, Repair & PR Approval */}
          <div className="p-4 bg-gray-900 border border-indigo-900/50 rounded-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                  Safe Execution & Autonomous Repair Controls
                </h4>
                <p className="text-xs text-gray-400 mt-0.5">
                  CodeForge can generate a repair based on failed test results. Repairs are validated in isolated execution environments and will not modify your original repository automatically.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              {/* Repair Button */}
              <button
                onClick={handleTriggerRepair}
                disabled={!isRepairAllowed || isRepairing}
                className="px-3.5 py-2 bg-orange-600 hover:bg-orange-500 disabled:bg-gray-800 text-white text-xs font-bold rounded-lg flex items-center gap-1.5 transition shadow-md shadow-orange-600/20"
              >
                {isRepairing ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Wrench className="w-3.5 h-3.5" />} Analyze Failure & Fix
              </button>

              {/* Approval Button */}
              {!selectedTask.is_approved ? (
                <button
                  onClick={handleApproveTask}
                  disabled={isApproving || taskChanges.length === 0}
                  className="px-3.5 py-2 bg-teal-600 hover:bg-teal-500 disabled:bg-gray-800 text-white text-xs font-bold rounded-lg flex items-center gap-1.5 transition shadow-md shadow-teal-600/20"
                >
                  {isApproving ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <ThumbsUp className="w-3.5 h-3.5" />} Approve Patch
                </button>
              ) : (
                <span className="px-3 py-1.5 bg-teal-950 text-teal-300 border border-teal-800 text-xs font-bold rounded-lg flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-teal-400" /> Approved
                </span>
              )}

              {/* Execution Button */}
              <button
                onClick={handleRunExecution}
                disabled={!isExecutionAllowed || isExecuting || selectedTask.status === 'executing'}
                className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-800 text-white text-xs font-bold rounded-lg flex items-center gap-1.5 transition shadow-md shadow-emerald-600/20"
              >
                {isExecuting || selectedTask.status === 'executing' ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Sandbox...
                  </>
                ) : (
                  <>
                    <PlayCircle className="w-3.5 h-3.5" /> Run Sandbox Tests
                  </>
                )}
              </button>

              {/* Create PR Button */}
              <button
                onClick={handleCreatePullRequest}
                disabled={!isPRCreationAllowed || isCreatingPR || activeGitOp?.status === 'pushing'}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-800 text-white text-xs font-bold rounded-lg flex items-center gap-1.5 transition shadow-lg shadow-purple-600/20 disabled:shadow-none"
              >
                {isCreatingPR || (activeGitOp && activeGitOp.status !== 'completed' && activeGitOp.status !== 'failed') ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Creating PR...
                  </>
                ) : (
                  <>
                    <GitPullRequest className="w-3.5 h-3.5" /> Create GitHub PR
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Tabs header */}
          <div className="flex border-b border-gray-800">
            <button
              onClick={() => setActiveTab('plan')}
              className={`px-4 py-2.5 text-xs font-semibold border-b-2 flex items-center gap-2 transition ${
                activeTab === 'plan'
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-gray-400 hover:text-gray-200'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" /> Implementation Plan
            </button>
            <button
              onClick={() => setActiveTab('changes')}
              className={`px-4 py-2.5 text-xs font-semibold border-b-2 flex items-center gap-2 transition ${
                activeTab === 'changes'
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-gray-400 hover:text-gray-200'
              }`}
            >
              <FileCode className="w-3.5 h-3.5" /> Code Changes ({taskChanges.length})
            </button>
            <button
              onClick={() => setActiveTab('execution')}
              className={`px-4 py-2.5 text-xs font-semibold border-b-2 flex items-center gap-2 transition ${
                activeTab === 'execution'
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-gray-400 hover:text-gray-200'
              }`}
            >
              <Terminal className="w-3.5 h-3.5" /> Sandbox Tests ({executions.length})
            </button>
            <button
              onClick={() => setActiveTab('repair')}
              className={`px-4 py-2.5 text-xs font-semibold border-b-2 flex items-center gap-2 transition ${
                activeTab === 'repair'
                  ? 'border-orange-500 text-orange-400'
                  : 'border-transparent text-gray-400 hover:text-gray-200'
              }`}
            >
              <Wrench className="w-3.5 h-3.5" /> Autonomous Repair ({iterations.length})
            </button>
            <button
              onClick={() => setActiveTab('git')}
              className={`px-4 py-2.5 text-xs font-semibold border-b-2 flex items-center gap-2 transition ${
                activeTab === 'git'
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-gray-400 hover:text-gray-200'
              }`}
            >
              <GitPullRequest className="w-3.5 h-3.5" /> GitHub PR ({gitOps.length})
            </button>
            {activeRunId && (
              <button
                onClick={() => setActiveTab('multi_agent')}
                className={`px-4 py-2.5 text-xs font-semibold border-b-2 flex items-center gap-2 transition ${
                  activeTab === 'multi_agent'
                    ? 'border-indigo-500 text-indigo-400'
                    : 'border-transparent text-gray-400 hover:text-gray-200'
                }`}
              >
                <Bot className="w-3.5 h-3.5" /> Multi-Agent Workflow
              </button>
            )}
          </div>

          {/* Tab 0: Multi-Agent Workflow */}
          {activeTab === 'multi_agent' && activeRunId && (
            <AgentWorkflow repoId={repoId} runId={activeRunId} />
          )}

          {/* Tab 1: Implementation Plan */}
          {activeTab === 'plan' && (
            <div className="space-y-4">
              {selectedTask.plan ? (
                <>
                  <div>
                    <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">
                      Task Summary
                    </h4>
                    <p className="text-sm text-gray-200 bg-gray-900/60 p-3 rounded-lg border border-gray-800">
                      {selectedTask.plan.task_summary}
                    </p>
                  </div>

                  <div>
                    <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-1">
                      Architecture Understanding
                    </h4>
                    <p className="text-xs text-gray-300 bg-gray-900/60 p-3 rounded-lg border border-gray-800 leading-relaxed">
                      {selectedTask.plan.architecture_understanding}
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
                        Relevant Files ({selectedTask.plan.relevant_files?.length || 0})
                      </h4>
                      <div className="bg-gray-900/60 p-3 rounded-lg border border-gray-800 space-y-1">
                        {selectedTask.plan.relevant_files?.map((f, i) => (
                          <div key={i} className="text-xs font-mono text-cyan-400 flex items-center gap-1.5">
                            <Code className="w-3 h-3 text-cyan-500" /> {f}
                          </div>
                        )) || <p className="text-xs text-gray-500 italic">None identified</p>}
                      </div>
                    </div>

                    <div>
                      <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
                        Proposed File Edits
                      </h4>
                      <div className="bg-gray-900/60 p-3 rounded-lg border border-gray-800 space-y-1">
                        {selectedTask.plan.proposed_changes?.map((c, i) => (
                          <div key={i} className="text-xs text-gray-300 flex items-start gap-1.5">
                            <ChevronRight className="w-3 h-3 text-indigo-400 flex-shrink-0 mt-0.5" /> {c}
                          </div>
                        )) || <p className="text-xs text-gray-500 italic">None</p>}
                      </div>
                    </div>
                  </div>

                  <div>
                    <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
                      Implementation Order & Tests
                    </h4>
                    <div className="bg-gray-900/60 p-3 rounded-lg border border-gray-800 space-y-2">
                      <div className="text-xs text-gray-300 font-medium">Steps:</div>
                      {selectedTask.plan.implementation_order?.map((step, i) => (
                        <div key={i} className="text-xs text-gray-400 pl-2 border-l border-indigo-800">{step}</div>
                      ))}
                      <div className="text-xs text-gray-300 font-medium pt-2">Tests:</div>
                      {selectedTask.plan.tests?.map((test, i) => (
                        <div key={i} className="text-xs text-emerald-400 font-mono">✓ {test}</div>
                      ))}
                    </div>
                  </div>

                  {selectedTask.plan.risks && selectedTask.plan.risks.length > 0 && (
                    <div>
                      <h4 className="text-xs font-bold text-amber-400 uppercase tracking-wider mb-1 flex items-center gap-1">
                        <ShieldAlert className="w-3.5 h-3.5" /> Security & Compatibility Risks
                      </h4>
                      <div className="bg-amber-950/20 border border-amber-900/50 p-3 rounded-lg space-y-1">
                        {selectedTask.plan.risks.map((risk, i) => (
                          <p key={i} className="text-xs text-amber-300/90">• {risk}</p>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center py-8 text-gray-500 text-xs">
                  {selectedTask.status === 'failed' ? 'Plan creation failed.' : 'Implementation plan is being generated...'}
                </div>
              )}
            </div>
          )}

          {/* Tab 2: Proposed Code Changes & Diffs */}
          {activeTab === 'changes' && (
            <div className="space-y-6">
              {taskChanges.length > 0 && (
                <div className="p-3.5 bg-gray-900 border border-gray-800 rounded-xl flex flex-wrap items-center justify-between gap-3 shadow-sm">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-gray-300">Target Scope Overview:</span>
                  </div>
                  <div className="flex items-center gap-3 text-xs">
                    <span className="px-2.5 py-1 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20 font-medium flex items-center gap-1.5">
                      🎨 Frontend Changes: <strong className="font-bold">{taskChanges.filter(c => {
                        const p = c.file_path.toLowerCase();
                        return p.startsWith('frontend') || p.includes('src/components') || p.includes('src/pages') || p.endsWith('.tsx') || p.endsWith('.jsx') || p.endsWith('.css') || p.endsWith('.html');
                      }).length}</strong> files
                    </span>
                    <span className="px-2.5 py-1 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20 font-medium flex items-center gap-1.5">
                      ⚙️ Backend Changes: <strong className="font-bold">{taskChanges.filter(c => {
                        const p = c.file_path.toLowerCase();
                        return p.startsWith('backend') || p.includes('app/') || p.includes('api/') || p.includes('services/') || p.endsWith('.py') || p.endsWith('.go') || p.endsWith('.java') || p.endsWith('.sql');
                      }).length}</strong> files
                    </span>
                  </div>
                </div>
              )}

              {taskChanges.length > 0 ? (
                taskChanges.map((change, idx) => (
                  <div key={idx} className="bg-gray-900/80 border border-gray-800 rounded-xl overflow-hidden shadow-sm">
                    <div className="p-3.5 bg-gray-900 border-b border-gray-800 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {getFileCategoryBadge(change.file_path)}
                        {getOperationBadge(change.operation)}
                        <span className="font-mono text-xs font-bold text-white">
                          {change.file_path}
                        </span>
                      </div>
                      <span className="text-[11px] text-gray-400 font-mono">
                        Confidence: {(change.confidence * 100).toFixed(0)}%
                      </span>
                    </div>

                    <div className="p-3 bg-gray-950/40 border-b border-gray-800/80">
                      <p className="text-xs text-gray-300">
                        <span className="font-semibold text-gray-400">Explanation:</span> {change.explanation}
                      </p>
                    </div>

                    <div className="p-4">
                      <h5 className="text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-2">
                        Unified Diff Preview
                      </h5>
                      {renderDiffLines(change.diff)}
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-10 text-gray-500 text-xs">
                  No code changes available.
                </div>
              )}
            </div>
          )}

          {/* Tab 3: Test Execution Output */}
          {activeTab === 'execution' && (
            <div className="space-y-6">
              {selectedExecution ? (
                <>
                  <div className="p-4 bg-gray-900 border border-gray-800 rounded-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-bold text-white">
                          Sandbox Execution Run
                        </h4>
                        <span className={`px-2 py-0.5 text-xs font-bold rounded ${
                          selectedExecution.status === 'passed' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' :
                          selectedExecution.status === 'failed' ? 'bg-red-950 text-red-400 border border-red-800' :
                          'bg-amber-950 text-amber-400 border border-amber-800 animate-pulse'
                        }`}>
                          {selectedExecution.status.toUpperCase()}
                        </span>
                      </div>
                    </div>
                    {selectedExecution.test_summary && (
                      <div className="flex items-center gap-4 text-xs font-mono bg-gray-950 p-2.5 rounded-lg border border-gray-800">
                        <div><span className="text-gray-500">Run:</span> <span className="text-white font-bold">{selectedExecution.test_summary.tests_run}</span></div>
                        <div><span className="text-emerald-500">Passed:</span> <span className="text-emerald-400 font-bold">{selectedExecution.test_summary.tests_passed}</span></div>
                        <div><span className="text-red-500">Failed:</span> <span className="text-red-400 font-bold">{selectedExecution.test_summary.tests_failed}</span></div>
                        <div><span className="text-cyan-500">Time:</span> <span className="text-cyan-400 font-bold">{selectedExecution.test_summary.duration_seconds}s</span></div>
                      </div>
                    )}
                  </div>

                  {selectedExecution.command_results && selectedExecution.command_results.length > 0 && (
                    <div className="space-y-4">
                      {selectedExecution.command_results.map((res, i) => (
                        <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden font-mono text-xs">
                          <div className="p-3 bg-gray-950 border-b border-gray-800 flex items-center justify-between">
                            <span className="text-cyan-400 font-bold flex items-center gap-2">
                              <Terminal className="w-4 h-4 text-cyan-500" /> ${res.command}
                            </span>
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${res.exit_code === 0 ? 'bg-emerald-950 text-emerald-400' : 'bg-red-950 text-red-400'}`}>
                              Exit: {res.exit_code} ({res.duration_seconds}s)
                            </span>
                          </div>
                          {res.stdout && <pre className="p-3 bg-gray-950/60 border-b border-gray-800 text-gray-300 overflow-x-auto whitespace-pre-wrap">{res.stdout}</pre>}
                          {res.stderr && <pre className="p-3 bg-red-950/20 text-red-300 overflow-x-auto whitespace-pre-wrap">{res.stderr}</pre>}
                        </div>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center py-12 text-gray-500 text-xs">
                  No execution runs triggered yet.
                </div>
              )}
            </div>
          )}

          {/* Tab 4: Autonomous Repair & Feedback Loop */}
          {activeTab === 'repair' && (
            <div className="space-y-6">
              {iterations.length > 0 ? (
                <div className="space-y-6">
                  {iterations.map((iter) => (
                    <div key={iter.id} className="p-5 bg-gray-900/90 border border-gray-800 rounded-xl space-y-4 shadow-sm">
                      <div className="flex items-center justify-between border-b border-gray-800 pb-3">
                        <div className="flex items-center gap-2.5">
                          <div className="w-6 h-6 rounded-full bg-orange-950 border border-orange-700 flex items-center justify-center text-xs font-bold text-orange-400">
                            #{iter.iteration_number}
                          </div>
                          <h4 className="text-sm font-bold text-white">
                            Repair Attempt Iteration {iter.iteration_number}/3
                          </h4>
                        </div>
                        <span className={`px-2.5 py-1 text-xs font-bold rounded-full ${
                          iter.status === 'passed' ? 'bg-emerald-950 text-emerald-300 border border-emerald-700' :
                          iter.status === 'stopped' ? 'bg-amber-950 text-amber-300 border border-amber-700' :
                          iter.status === 'failed' ? 'bg-red-950 text-red-300 border border-red-700' :
                          'bg-orange-900/60 text-orange-300 border border-orange-700 animate-pulse'
                        }`}>
                          {iter.status.toUpperCase()}
                        </span>
                      </div>

                      {/* Root Cause Analysis Box */}
                      {iter.root_cause && (
                        <div className="bg-gray-950 p-4 rounded-lg border border-gray-800 space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-bold text-orange-400 uppercase tracking-wider flex items-center gap-1.5">
                              <Wrench className="w-3.5 h-3.5" /> Root Cause Diagnosis
                            </span>
                            {iter.failure_category && (
                              <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-orange-950 text-orange-300 border border-orange-800 rounded">
                                {iter.failure_category}
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-gray-200 leading-relaxed font-mono">
                            {iter.root_cause}
                          </p>
                        </div>
                      )}

                      {/* Repair Plan Summary */}
                      {iter.plan && (
                        <div className="bg-gray-950/60 p-3 rounded-lg border border-gray-800 text-xs space-y-1">
                          <span className="text-gray-400 font-bold">Repair Plan:</span> {iter.plan.summary || 'Targeted fix'}
                        </div>
                      )}

                      {/* Error message */}
                      {iter.error_message && (
                        <div className="p-3 bg-red-950/50 border border-red-800/80 rounded-lg text-xs text-red-300 flex items-center gap-2">
                          <AlertCircle className="w-4 h-4 flex-shrink-0" />
                          {iter.error_message}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12 text-gray-500 text-xs">
                  No repair iterations run yet. Click "Analyze Failure & Fix" after a test run fails to trigger autonomous repair.
                </div>
              )}
            </div>
          )}

          {/* Tab 5: GitHub Pull Request */}
          {activeTab === 'git' && (
            <div className="space-y-6">
              {activeGitOp ? (
                <>
                  <div className="p-5 bg-purple-950/30 border border-purple-800/60 rounded-xl space-y-4">
                    <div className="flex items-center justify-between border-b border-purple-900/60 pb-3">
                      <div className="flex items-center gap-2.5">
                        <GitPullRequest className="w-5 h-5 text-purple-400" />
                        <h4 className="text-sm font-bold text-white">
                          GitHub Pull Request Automation
                        </h4>
                      </div>
                      <span className={`px-2.5 py-1 text-xs font-bold rounded-full ${
                        activeGitOp.status === 'completed' ? 'bg-emerald-950 text-emerald-300 border border-emerald-700' :
                        activeGitOp.status === 'failed' ? 'bg-red-950 text-red-300 border border-red-700' :
                        'bg-purple-900/60 text-purple-300 border border-purple-700 animate-pulse'
                      }`}>
                        {activeGitOp.status.toUpperCase()}
                      </span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 font-mono text-xs">
                      <div className="bg-gray-950/80 p-3 rounded-lg border border-gray-800 space-y-1">
                        <span className="text-gray-500 block text-[10px] uppercase font-bold">Feature Branch</span>
                        <div className="text-purple-300 font-bold flex items-center gap-1.5">
                          <GitBranch className="w-3.5 h-3.5 text-purple-400" /> {activeGitOp.branch_name}
                        </div>
                      </div>

                      <div className="bg-gray-950/80 p-3 rounded-lg border border-gray-800 space-y-1">
                        <span className="text-gray-500 block text-[10px] uppercase font-bold">Commit SHA</span>
                        <div className="text-cyan-300 font-bold flex items-center gap-1.5">
                          <GitCommit className="w-3.5 h-3.5 text-cyan-400" /> {activeGitOp.commit_sha ? activeGitOp.commit_sha.substring(0, 10) : 'Pending commit...'}
                        </div>
                      </div>
                    </div>

                    <div className="p-4 bg-emerald-950/40 border border-emerald-800/80 rounded-xl flex items-center justify-between">
                      <div>
                        <h5 className="text-xs font-bold text-white flex items-center gap-2">
                          <ShieldCheck className="w-4 h-4 text-emerald-400" />
                          GitHub Feature Branch & PR Ready
                        </h5>
                        <p className="text-xs text-emerald-300/80 mt-1">
                          Branch: <code className="text-purple-300 font-bold">{activeGitOp.branch_name}</code> — Code changes committed and applied locally.
                        </p>
                      </div>
                      <a
                        href={activeGitOp.pull_request_url || `https://github.com/zoraizanwar/WEB-TERM-PROJECT/compare/main...${activeGitOp.branch_name}?expand=1`}
                        target="_blank"
                        rel="noreferrer"
                        className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-lg flex items-center gap-2 transition shadow-lg shadow-emerald-600/20 shrink-0"
                      >
                        Open PR / Compare on GitHub <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    </div>

                    {activeGitOp.error_message && (
                      <div className="p-3 bg-red-950/60 border border-red-800/80 rounded-lg text-xs text-red-300 flex items-center gap-2">
                        <AlertCircle className="w-4 h-4 flex-shrink-0" />
                        {activeGitOp.error_message}
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <div className="text-center py-12 text-gray-500 text-xs">
                  No Pull Request created yet. Approve changes and ensure a sandbox test run passes to enable PR creation.
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className="text-center py-12 border border-dashed border-gray-800 rounded-xl bg-gray-950/40">
          <Bot className="w-10 h-10 text-gray-600 mx-auto mb-3" />
          <h3 className="text-sm font-semibold text-gray-300">No Task Selected</h3>
          <p className="text-xs text-gray-500 mt-1 max-w-sm mx-auto">
            Submit a development request above to let CodeForge AI plan, generate, test, repair failures, and open Pull Requests.
          </p>
        </div>
      )}
    </div>
  );
};
