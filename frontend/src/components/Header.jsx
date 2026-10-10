import React, { useState, useRef, useEffect } from 'react';
import {
  Code2,
  FolderPlus,
  GitBranch,
  Upload,
  ChevronDown,
  LogOut,
  User,
} from 'lucide-react';

export default function Header({
  user,
  projects,
  currentProject,
  onSelectProject,
  onOpenCreateModal,
  onOpenUploadModal,
  onOpenGithubModal,
  onLogout,
  systemStatus,
}) {
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const menuRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const initials = user?.full_name
    ? user.full_name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2)
    : user?.email?.[0]?.toUpperCase() || '?';

  return (
    <header className="app-header">
      <div className="header-brand">
        <div className="brand-icon">
          <Code2 size={18} />
        </div>
        <div>
          <h1 className="brand-title">AI Developer Assistant</h1>
        </div>
      </div>

      <div className="header-actions">
        {/* Project Selector */}
        <div className="project-badge">
          <span style={{ color: 'var(--text-dim)', fontSize: '12px' }}>Project:</span>
          <select
            value={currentProject?.id || ''}
            onChange={(e) => {
              const selected = projects.find((p) => p.id === parseInt(e.target.value));
              if (selected) onSelectProject(selected);
            }}
            style={{
              background: 'transparent',
              color: 'var(--text-main)',
              border: 'none',
              outline: 'none',
              fontWeight: 500,
              cursor: 'pointer',
              maxWidth: '180px',
            }}
          >
            {projects.length === 0 && <option value="">No Projects Yet</option>}
            {projects.map((p) => (
              <option key={p.id} value={p.id} style={{ background: 'var(--bg-panel)' }}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        {/* Action Buttons */}
        <button className="btn btn-secondary btn-sm" onClick={onOpenCreateModal} title="Create New Project">
          <FolderPlus size={15} />
          <span>New Project</span>
        </button>

        {currentProject && (
          <>
            <button className="btn btn-secondary btn-sm" onClick={onOpenUploadModal} title="Upload Codebase ZIP">
              <Upload size={15} />
              <span>Upload ZIP</span>
            </button>

            <button className="btn btn-secondary btn-sm" onClick={onOpenGithubModal} title="Import from GitHub">
              <GitBranch size={15} />
              <span>Import GitHub</span>
            </button>
          </>
        )}

        {/* Gemini Status Indicator */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '12px',
            color: 'var(--text-muted)',
          }}
          title={
            systemStatus?.gemini_configured
              ? 'Gemini API Connected & Ready'
              : 'Gemini API key not configured in backend/.env'
          }
        >
          <div className={`status-dot ${systemStatus?.gemini_configured ? '' : 'warning'}`} />
          <span>{systemStatus?.gemini_configured ? 'Gemini Ready' : 'Gemini Offline'}</span>
        </div>

        {/* User Avatar + Dropdown Menu */}
        {user && (
          <div className="user-menu-wrapper" ref={menuRef}>
            <button
              className="user-avatar-btn"
              onClick={() => setUserMenuOpen((v) => !v)}
              title={user.full_name || user.email}
              aria-expanded={userMenuOpen}
            >
              <span className="user-avatar">{initials}</span>
              <ChevronDown size={14} style={{ color: 'var(--text-dim)' }} />
            </button>

            {userMenuOpen && (
              <div className="user-dropdown">
                <div className="user-dropdown-header">
                  <div className="user-dropdown-name">{user.full_name || 'Developer'}</div>
                  <div className="user-dropdown-email">{user.email}</div>
                </div>
                <div className="user-dropdown-divider" />
                <button
                  className="user-dropdown-item user-dropdown-item--danger"
                  onClick={() => {
                    setUserMenuOpen(false);
                    onLogout?.();
                  }}
                >
                  <LogOut size={14} />
                  Sign Out
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
