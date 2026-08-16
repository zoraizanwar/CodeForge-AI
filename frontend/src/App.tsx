import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { DashboardLayout } from './layouts/DashboardLayout';
import { Dashboard } from './pages/Dashboard';
import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { RepositoryDetail } from './pages/RepositoryDetail';
import { AuditLog } from './components/AuditLog';
import { SystemMonitoring } from './components/SystemMonitoring';
import { GovernanceDashboard } from './components/GovernanceDashboard';
import { AgentReliabilityDashboard } from './components/AgentReliabilityDashboard';

// Protected Route wrapper that redirects unauthenticated users to the Login view
const ProtectedRoute = () => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#0e0f13] flex flex-col items-center justify-center text-slate-400 font-sans">
        <div className="w-8 h-8 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mb-3"></div>
        <p className="text-xs uppercase tracking-widest font-semibold text-slate-500">Loading session...</p>
      </div>
    );
  }

  return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />;
};

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public Auth Routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          
          {/* Protected Main Panel Routes */}
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<DashboardLayout />}>
              <Route index element={<Dashboard />} />
              <Route path="repositories/:repoId" element={<RepositoryDetail />} />
              <Route path="audit" element={<AuditLog />} />
              <Route path="monitoring" element={<SystemMonitoring />} />
              <Route path="governance" element={<GovernanceDashboard />} />
              <Route path="reliability" element={<AgentReliabilityDashboard />} />
            </Route>
          </Route>

          {/* Catch-all redirection */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
