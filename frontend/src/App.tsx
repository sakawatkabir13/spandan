import { useLanguage } from './context/LanguageContext';
import React, { Suspense, lazy, useEffect } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppErrorBoundary } from './components/common/AppErrorBoundary';
import { EnglishOnly } from './context/LanguageContext';
import { MainLayout } from './components/layout/MainLayout';
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LoadingSpinner } from './components/common/LoadingSpinner';

// Pages
import { Home } from './pages/Home';
const ChatAssistant = lazy(() => import('./components/chat/ChatAssistant').then(module => ({ default: module.ChatAssistant })));

const DirectoryDetailPage = lazy(() => import('./pages/doctors/DirectoryDetailPage').then(module => ({ default: module.DirectoryDetailPage })));
const LoginPage = lazy(() => import('./pages/auth/LoginPage').then(module => ({ default: module.LoginPage })));
const RegisterPage = lazy(() => import('./pages/auth/RegisterPage').then(module => ({ default: module.RegisterPage })));
const DoctorDiscoveryPage = lazy(() => import('./pages/doctors/DoctorDiscoveryPage').then(module => ({ default: module.DoctorDiscoveryPage })));
const DoctorProfileDetailPage = lazy(() => import('./pages/doctors/DoctorProfileDetailPage').then(module => ({ default: module.DoctorProfileDetailPage })));
const AITriagePage = lazy(() => import('./pages/ai/AITriagePage').then(module => ({ default: module.AITriagePage })));
const PatientDashboard = lazy(() => import('./pages/dashboard/PatientDashboard').then(module => ({ default: module.PatientDashboard })));
const DoctorDashboard = lazy(() => import('./pages/dashboard/DoctorDashboard').then(module => ({ default: module.DoctorDashboard })));
const LiveQueueConsolePage = lazy(() => import('./pages/dashboard/LiveQueueConsolePage').then(module => ({ default: module.LiveQueueConsolePage })));
const AssistantDashboard = lazy(() => import('./pages/dashboard/AssistantDashboard').then(module => ({ default: module.AssistantDashboard })));
const AdminDashboard = lazy(() => import('./pages/dashboard/AdminDashboard').then(module => ({ default: module.AdminDashboard })));
const UserManagementPage = lazy(() => import('./pages/dashboard/UserManagementPage').then(module => ({ default: module.UserManagementPage })));
const ProfilePage = lazy(() => import('./pages/dashboard/ProfilePage').then(module => ({ default: module.ProfilePage })));
const LegalPage = lazy(() => import('./pages/LegalPage').then(module => ({ default: module.LegalPage })));
const AccountActionPage = lazy(() => import('./pages/auth/AccountActionPage').then(module => ({ default: module.AccountActionPage })));
const ToolsPage = lazy(() => import('./pages/dashboard/ToolsPage').then(module => ({ default: module.ToolsPage })));
const PaymentsPage = lazy(() => import('./pages/dashboard/PaymentsPage').then(module => ({ default: module.PaymentsPage })));
const PatientRecordsPage = lazy(() => import('./pages/dashboard/PatientRecordsPage').then(module => ({ default: module.PatientRecordsPage })));
const AppointmentDetailsPage = lazy(() => import('./pages/dashboard/AppointmentDetailsPage').then(module => ({ default: module.AppointmentDetailsPage })));
const HealthRecordsPage = lazy(() => import('./pages/dashboard/HealthRecordsPage').then(module => ({ default: module.HealthRecordsPage })));
const PatientHomePage = lazy(() => import('./pages/dashboard/PatientHomePage').then(module => ({ default: module.PatientHomePage })));
const TodayPage = lazy(() => import('./pages/dashboard/TodayPage').then(module => ({ default: module.TodayPage })));

const ProtectedRoute: React.FC<{ children: React.ReactNode; roles?: string[] }> = ({
  children,
  roles,
}) => {
  const { t: uiText } = useLanguage();
  const { user, isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <LoadingSpinner size="lg" text={uiText("Verifying session...")} />
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" state={{ from: location.pathname + location.search + location.hash }} replace />;
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
  const { t: uiText } = useLanguage();
  const { pathname, hash } = useLocation();
  useEffect(() => {
    // Announce a completed route and move keyboard focus past repeated navigation.
    // Lazy routes may not have a heading until their chunk or data has arrived.
    if (hash) return;
    const announce = () => {
      const heading = document.querySelector<HTMLElement>('main h1, main h2');
      if (!heading || heading.closest('[aria-busy="true"]')) return false;
      document.title = `${heading.textContent?.trim() || 'Care'} | Spandan`;
      heading.tabIndex = -1;
      heading.focus({ preventScroll: true });
      return true;
    };
    let observer: MutationObserver | undefined;
    const frame = requestAnimationFrame(() => {
      if (announce()) return;
      observer = new MutationObserver(() => { if (announce()) observer?.disconnect(); });
      observer.observe(document.body, { childList: true, subtree: true });
    });
    const timeout = window.setTimeout(() => observer?.disconnect(), 10000);
    return () => { cancelAnimationFrame(frame); observer?.disconnect(); clearTimeout(timeout); };
  }, [pathname, hash]);
  useEffect(() => {
    if (!hash) { window.scrollTo(0, 0); return; }
    let targetId: string;
    try { targetId = decodeURIComponent(hash.slice(1)); } catch { return; }
    const scroll = () => {
      const target = document.getElementById(targetId);
      if (!target) return false;
      target.scrollIntoView({ block: 'start' });
      return true;
    };
    if (scroll()) return;
    const observer = new MutationObserver(() => { if (scroll()) observer.disconnect(); });
    observer.observe(document.body, { childList: true, subtree: true });
    const timeout = window.setTimeout(() => observer.disconnect(), 10000);
    return () => { observer.disconnect(); window.clearTimeout(timeout); };
  }, [pathname, hash]);
  return (
    <Suspense fallback={<MainLayout compact><div className="flex min-h-[55dvh] items-center justify-center"><LoadingSpinner text={uiText("Opening page…")} /></div></MainLayout>}><Routes>
      {/* Public Routes */}
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/forgot-password" element={<AccountActionPage />} />
      <Route path="/account-action" element={<AccountActionPage />} />
      <Route path="/doctors" element={<DoctorDiscoveryPage />} />
      <Route path="/directory/:id" element={<DirectoryDetailPage />} />
      <Route path="/doctors/:id" element={<DoctorProfileDetailPage />} />
      <Route path="/ai-triage" element={<AITriagePage />} />
      <Route path="/privacy" element={<LegalPage document="privacy" />} />
      <Route path="/terms" element={<LegalPage document="terms" />} />
      <Route path="/medical-disclaimer" element={<LegalPage document="medical" />} />

      {/* Patient Routes */}
      <Route path="/dashboard/patient/home" element={<ProtectedRoute roles={['patient']}><PatientHomePage /></ProtectedRoute>} />
      <Route path="/dashboard/patient/records" element={<ProtectedRoute roles={['patient']}><HealthRecordsPage /></ProtectedRoute>} />
      <Route path="/dashboard/patient/appointments/:appointmentId" element={<ProtectedRoute roles={['patient']}><AppointmentDetailsPage key={pathname} /></ProtectedRoute>} />
      <Route path="/dashboard/doctor/today" element={<ProtectedRoute roles={['doctor']}><TodayPage /></ProtectedRoute>} />
      <Route path="/dashboard/patient/payments" element={<ProtectedRoute roles={['patient']}><PaymentsPage /></ProtectedRoute>} />
      <Route path="/dashboard/:role/tools" element={<ProtectedRoute><ToolsPage /></ProtectedRoute>} />
      <Route path="/dashboard/doctor/patients/:appointmentId" element={<ProtectedRoute roles={['doctor']}><PatientRecordsPage /></ProtectedRoute>} />
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
      <Route path="/dashboard/admin/queue" element={<ProtectedRoute roles={['administrator']}><LiveQueueConsolePage /></ProtectedRoute>} />
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
    </Routes></Suspense>
  );
};

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30000 } } });
function SupportAssistant() {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <Suspense fallback={null}><EnglishOnly><ChatAssistant /></EnglishOnly></Suspense> : null;
}
export const App: React.FC = () => {
  return (
    <AppErrorBoundary><QueryClientProvider client={queryClient}><AuthProvider>
      <BrowserRouter>
        <AppRoutes />
        <SupportAssistant />
      </BrowserRouter>
    </AuthProvider></QueryClientProvider></AppErrorBoundary>
  );
};

export default App;
