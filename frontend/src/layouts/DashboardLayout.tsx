import React, { useEffect, useState } from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import { Terminal, Database, Cpu, Activity, LayoutDashboard, History, Settings, CheckCircle2, AlertCircle, LogOut, Shield, BarChart3 } from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';

export const DashboardLayout: React.FC = () => {
  const location = useLocation();
  const { user, logout } = useAuth();
  const [dbStatus, setDbStatus] = useState<'ok' | 'error' | 'loading'>('loading');
  const [apiStatus, setApiStatus] = useState<'ok' | 'error' | 'loading'>('loading');

  const checkStatus = async () => {
    try {
      const health = await api.getHealth();
      setApiStatus(health.status === 'ok' ? 'ok' : 'error');
    } catch {
      setApiStatus('error');
    }

    try {
      const ready = await api.getReady();
      setDbStatus(ready.services.database === 'ok' ? 'ok' : 'error');
    } catch {
      setDbStatus('error');
    }
  };

  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 10000); // Poll health status every 10s
    return () => clearInterval(interval);
  }, []);

  const navItems = [
    { path: '/', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/audit', label: 'Audit Trail', icon: Shield },
    { path: '/monitoring', label: 'System Monitoring', icon: BarChart3 },
    { path: '/governance', label: 'Governance', icon: Shield },
    { path: '/reliability', label: 'Agent Reliability', icon: Activity },
    { path: '/history', label: 'Runs History', icon: History, disabled: true },
    { path: '/settings', label: 'Settings', icon: Settings, disabled: true },
  ];

  return (
    <div className="flex h-screen w-screen bg-[#0e0f13] text-gray-200 overflow-hidden font-sans">
      {/* Sidebar */}
      <aside className="w-64 border-r border-gray-800 bg-[#121319] flex flex-col justify-between select-none">
        <div>
          {/* Brand Header */}
          <div className="p-6 border-b border-gray-800">
            <div className="flex items-center gap-3">
              <div className="bg-purple-600 p-2 rounded-lg text-white">
                <Cpu className="w-5 h-5 animate-pulse" />
              </div>
              <div>
                <h1 className="text-lg font-bold tracking-tight text-white">CodeForge AI</h1>
                <p className="text-[10px] text-purple-400 font-semibold tracking-wider uppercase">Your AI Software Engineer</p>
              </div>
            </div>
          </div>

          {/* Navigation Items */}
          <nav className="p-4 space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <div key={item.path}>
                  {item.disabled ? (
                    <span
                      className="flex items-center gap-3 px-3 py-2.5 text-sm font-medium text-gray-600 cursor-not-allowed"
                      title="Coming soon in Step 2"
                    >
                      <Icon className="w-4 h-4" />
                      {item.label}
                      <span className="ml-auto text-[8.5px] px-1.5 py-0.5 rounded-full bg-gray-900 border border-gray-800 text-gray-500 font-normal">
                        Soon
                      </span>
                    </span>
                  ) : (
                    <Link
                      to={item.path}
                      className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                        isActive
                          ? 'bg-purple-600/10 border border-purple-500/30 text-purple-400'
                          : 'text-gray-400 hover:bg-gray-800/50 border border-transparent hover:text-gray-200'
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                      {item.label}
                    </Link>
                  )}
                </div>
              );
            })}
          </nav>
        </div>

        <div>
          {/* User profile & logout controls */}
          {user && (
            <div className="px-4 py-3 mx-4 mb-2 bg-[#1b1c24]/50 border border-gray-800 rounded-lg flex items-center justify-between">
              <div className="min-w-0 flex-1 pr-2">
                <p className="text-xs font-semibold text-gray-200 truncate" title={user.email}>
                  {user.email}
                </p>
                <p className="text-[9px] text-gray-500 font-mono">Developer ID</p>
              </div>
              <button
                onClick={logout}
                className="p-1.5 text-gray-400 hover:text-rose-450 hover:bg-rose-500/10 rounded-lg transition-colors cursor-pointer"
                title="Sign Out"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Footer Diagnostic Panel */}
          <div className="p-4 border-t border-gray-800 bg-[#0e0f13]/50 text-[11px] space-y-2">
            <h2 className="font-semibold text-gray-500 uppercase tracking-wider text-[9px] mb-2">Services Status</h2>
            
            {/* API Health */}
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-gray-400">
                <Activity className="w-3 h-3" /> API Server
              </span>
              <span className="flex items-center gap-1">
                {apiStatus === 'ok' ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                ) : apiStatus === 'error' ? (
                  <AlertCircle className="w-3.5 h-3.5 text-rose-500" />
                ) : (
                  <span className="w-2 h-2 rounded-full bg-yellow-500 animate-pulse" />
                )}
              </span>
            </div>

            {/* Database Readiness */}
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-gray-400">
                <Database className="w-3 h-3" /> Database (DB)
              </span>
              <span className="flex items-center gap-1">
                {dbStatus === 'ok' ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                ) : dbStatus === 'error' ? (
                  <AlertCircle className="w-3.5 h-3.5 text-rose-500" />
                ) : (
                  <span className="w-2 h-2 rounded-full bg-yellow-500 animate-pulse" />
                )}
              </span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Pane */}
      <main className="flex-1 flex flex-col overflow-hidden bg-[#0e0f13]">
        {/* Top Header */}
        <header className="h-16 border-b border-gray-800 flex items-center px-8 bg-[#121319]/30">
          <div className="flex items-center gap-2 text-xs bg-gray-900/60 border border-gray-800 px-3 py-1.5 rounded-md font-mono text-gray-400">
            <Terminal className="w-3.5 h-3.5 text-purple-400" />
            <span>powershell: ./codeforge-agent.ps1</span>
          </div>
        </header>

        {/* Dynamic page context */}
        <div className="flex-1 overflow-auto p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
};
