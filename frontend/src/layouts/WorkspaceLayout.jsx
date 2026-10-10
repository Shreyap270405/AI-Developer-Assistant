import React from 'react';
import { useAuth } from '../context/AuthContext';
import { useProject } from '../context/ProjectContext';
import Header from '../components/Header';

/**
 * WorkspaceLayout wraps the authenticated workspace shell.
 * It passes auth and project state down to Header and renders
 * the three-panel layout as children.
 */
export default function WorkspaceLayout({
  children,
  systemStatus,
  onOpenCreateModal,
  onOpenUploadModal,
  onOpenGithubModal,
}) {
  const { user, logout } = useAuth();
  const { projects, activeProject, selectProject } = useProject();

  return (
    <div className="app-shell">
      <Header
        user={user}
        projects={projects}
        currentProject={activeProject}
        onSelectProject={selectProject}
        onOpenCreateModal={onOpenCreateModal}
        onOpenUploadModal={onOpenUploadModal}
        onOpenGithubModal={onOpenGithubModal}
        onLogout={logout}
        systemStatus={systemStatus}
      />
      <main className="workspace-layout">
        {children}
      </main>
    </div>
  );
}
