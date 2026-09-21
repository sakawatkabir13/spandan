import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LoadingSpinner } from './components/common/LoadingSpinner';

// Pages
import { Home } from './pages/Home';
import { LoginPage } from './pages/auth/LoginPage';
import { RegisterPage } from './pages/auth/RegisterPage';
import { DoctorDiscoveryPage } from './pages/doctors/DoctorDiscoveryPage';
import { DoctorProfileDetailPage } from './pages/doctors/DoctorProfileDetailPage';
import { AITriagePage } from './pages/ai/AITriagePage';
import { PatientDashboard } from './pages/dashboard/PatientDashboard';
import { DoctorDashboard } from './pages/dashboard/DoctorDashboard';
import { LiveQueueConsolePage } from './pages/dashboard/LiveQueueConsolePage';
import { AssistantDashboard } from './pages/dashboard/AssistantDashboard';
import { AdminDashboard } from './pages/dashboard/AdminDashboard';
import { UserManagementPage } from './pages/dashboard/UserManagementPage';
import { ProfilePage } from './pages/dashboard/ProfilePage';
import { LegalPage } from './pages/LegalPage';

const ProtectedRoute: React.FC<{ children: React.ReactNode; roles?: string[] }> = ({
  children,
  roles,
}) => {
  const { user, isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <LoadingSpinner size="lg" text="Verifying session..." />
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }

  if (roles && !roles.includes(user.role)) {
    // redirect to default dashboard for user role if wrong role required
    switch (user.role) {
      case 'patient':
        return <Navigate to="/dashboard/patient" replace />;
      case 'doctor':
        return <Navigate to="/dashboard/doctor" replace />;
      case 'assistant':
        return <Navigate to="/dashboard/assistant" replace />;
      case 'administrator':
        return <Navigate to="/dashboard/admin" replace />;
      default:
        return <Navigate to="/" replace />;
    }
  }

  return <>{children}</>;
};

const AppRoutes: React.FC = () => {
  return (
    <Routes>
      {/* Public Routes */}
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/doctors" element={<DoctorDiscoveryPage />} />
      <Route path="/doctors/:id" element={<DoctorProfileDetailPage />} />
      <Route path="/ai-triage" element={<AITriagePage />} />
      <Route path="/privacy" element={<LegalPage document="privacy" />} />
      <Route path="/terms" element={<LegalPage document="terms" />} />
      <Route path="/medical-disclaimer" element={<LegalPage document="medical" />} />

      {/* Patient Routes */}
      <Route
        path="/dashboard/patient"
        element={
          <ProtectedRoute roles={['patient']}>
            <PatientDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/dashboard/patient/profile"
        element={
          <ProtectedRoute roles={['patient']}>
            <ProfilePage />
          </ProtectedRoute>
        }
      />

      {/* Doctor Routes */}
      <Route
        path="/dashboard/doctor"
        element={
          <ProtectedRoute roles={['doctor']}>
            <DoctorDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/dashboard/doctor/chambers"
        element={
          <ProtectedRoute roles={['doctor']}>
            <DoctorDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/dashboard/doctor/queue"
        element={
          <ProtectedRoute roles={['doctor', 'assistant']}>
            <LiveQueueConsolePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/dashboard/doctor/profile"
        element={
          <ProtectedRoute roles={['doctor']}>
            <ProfilePage />
          </ProtectedRoute>
        }
      />

      {/* Assistant Routes */}
      <Route
        path="/dashboard/assistant"
        element={
          <ProtectedRoute roles={['assistant']}>
            <AssistantDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/dashboard/assistant/queue"
        element={
          <ProtectedRoute roles={['assistant']}>
            <LiveQueueConsolePage />
          </ProtectedRoute>
        }
      />

      <Route path="/dashboard/assistant/profile" element={<ProtectedRoute roles={['assistant']}><ProfilePage /></ProtectedRoute>} />
      <Route path="/dashboard/admin/profile" element={<ProtectedRoute roles={['administrator']}><ProfilePage /></ProtectedRoute>} />
      <Route path="/dashboard/admin/users" element={<ProtectedRoute roles={['administrator']}><UserManagementPage /></ProtectedRoute>} />
      {/* Admin Routes */}
      <Route
        path="/dashboard/admin/*"
        element={
          <ProtectedRoute roles={['administrator']}>
            <AdminDashboard />
          </ProtectedRoute>
        }
      />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
