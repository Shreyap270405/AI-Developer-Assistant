import React, { useState, useEffect, useCallback } from 'react';

// Context providers
import { AuthProvider, useAuth } from './context/AuthContext';
import { ProjectProvider, useProject } from './context/ProjectContext';

// Pages
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import ProjectsPage from './pages/ProjectsPage';
import WorkspacePage from './pages/WorkspacePage';

// Layouts
import AuthLayout from './layouts/AuthLayout';
import DashboardLayout from './layouts/DashboardLayout';

// Shared components
import ProjectModal from './components/ProjectModal';
import Toast from './components/Toast';

// Hooks & services
import { useToast } from './hooks/useToast';

// ─── Inner app — runs inside contexts ────────────────────────────────────────
function WorkspaceApp() {
  const { user, loading: authLoading } = useAuth();
  const { activeProject, selectProject, fetchProjects } = useProject();
  const { toast, showToast, closeToast } = useToast();

  const [authView, setAuthView] = useState('landing'); // 'landing' | 'login' | 'register'

  // Hash-based routing to support refresh and back/forward navigation
  const getInitialView = () => {
    try {
      const hash = window.location.hash.replace(/^#\/?/, '').toLowerCase();
      if (['dashboard', 'projects', 'workspace'].includes(hash)) {
        return hash;
      }
    } catch (_) {}
    return 'dashboard';
  };

  const [currentView, setCurrentViewState] = useState(getInitialView);
  const [modalConfig, setModalConfig] = useState({ isOpen: false, tab: 'create' });

  const navigateTo = useCallback((view) => {
    setCurrentViewState(view);
    try {
      window.location.hash = `#${view}`;
    } catch (_) {}
  }, []);

  // Listen for browser forward/back buttons
  useEffect(() => {
    const handleHashChange = () => {
      try {
        const hash = window.location.hash.replace(/^#\/?/, '').toLowerCase();
        if (['dashboard', 'projects', 'workspace'].includes(hash)) {
          setCurrentViewState(hash);
        }
      } catch (_) {}
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  // Load projects once auth is resolved
  useEffect(() => {
    if (!authLoading && user) fetchProjects();
  }, [authLoading, user, fetchProjects]);

  // ── Loading ──────────────────────────────────────────────────────────────────
  if (authLoading) {
    return (
      <div className="loading-screen" aria-label="Loading">
        <span className="spinner" aria-label="Loading…" />
      </div>
    );
  }

  // ── Unauthenticated ──────────────────────────────────────────────────────────
  if (!user) {
    if (authView === 'landing') {
      return <LandingPage onNavigate={setAuthView} />;
    }
    return (
      <AuthLayout>
        {authView === 'login'
          ? <LoginPage onSwitchToRegister={() => setAuthView('register')} />
          : <RegisterPage onSwitchToLogin={() => setAuthView('login')} />
        }
      </AuthLayout>
    );
  }

  // ── Dashboard ────────────────────────────────────────────────────────────────
  if (currentView === 'dashboard') {
    return (
      <>
        <DashboardLayout currentView="dashboard" onNavigate={navigateTo}>
          <DashboardPage
            onOpenProject={(proj) => {
              selectProject(proj);
              navigateTo('workspace');
            }}
            onNewProject={() => setModalConfig({ isOpen: true, tab: 'create' })}
          />
        </DashboardLayout>

        <ProjectModal
          isOpen={modalConfig.isOpen}
          initialTab={modalConfig.tab}
          activeProject={activeProject}
          onClose={() => setModalConfig({ isOpen: false, tab: 'create' })}
          onProjectReady={async (proj) => {
            selectProject(proj);
            await fetchProjects();
            navigateTo('workspace');
          }}
          showToast={showToast}
        />
        <Toast toast={toast} onClose={closeToast} />
      </>
    );
  }

  // ── Projects Page ────────────────────────────────────────────────────────────
  if (currentView === 'projects') {
    return (
      <>
        <DashboardLayout currentView="projects" onNavigate={navigateTo}>
          <ProjectsPage
            onOpenProject={(proj) => {
              selectProject(proj);
              navigateTo('workspace');
            }}
            onNewProject={() => setModalConfig({ isOpen: true, tab: 'create' })}
          />
        </DashboardLayout>

        <ProjectModal
          isOpen={modalConfig.isOpen}
          initialTab={modalConfig.tab}
          activeProject={activeProject}
          onClose={() => setModalConfig({ isOpen: false, tab: 'create' })}
          onProjectReady={async (proj) => {
            selectProject(proj);
            await fetchProjects();
            navigateTo('workspace');
          }}
          showToast={showToast}
        />
        <Toast toast={toast} onClose={closeToast} />
      </>
    );
  }

  // ── Workspace ────────────────────────────────────────────────────────────────
  return (
    <>
      <WorkspacePage
        onBackToDashboard={() => navigateTo('dashboard')}
        onNavigateToProjects={() => navigateTo('projects')}
      />
      <Toast toast={toast} onClose={closeToast} />
    </>
  );
}

// ─── Root ─────────────────────────────────────────────────────────────────────
export default function App() {
  return (
    <AuthProvider>
      <ProjectProvider>
        <WorkspaceApp />
      </ProjectProvider>
    </AuthProvider>
  );
}
