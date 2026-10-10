import React from 'react';
import { useAuth } from '../context/AuthContext';
import { useProject } from '../context/ProjectContext';
import { Code2, LayoutDashboard, Folder, MessageSquare, Settings, LogOut, ChevronDown } from 'lucide-react';

export default function DashboardLayout({ children, currentView, onNavigate }) {
  const { user, logout } = useAuth();
  const [userMenuOpen, setUserMenuOpen] = React.useState(false);
  const menuRef = React.useRef(null);

  React.useEffect(() => {
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
    <div className="dashboard-shell">
      {/* Sidebar Navigation */}
      <aside className="dashboard-sidebar">
        <div className="sidebar-brand">
          <div className="brand-icon"><Code2 size={20} /></div>
          <span className="brand-title">AI Assistant</span>
        </div>
        
        <nav className="sidebar-nav">
          <button 
            className={`nav-item ${currentView === 'dashboard' ? 'active' : ''}`}
            onClick={() => onNavigate('dashboard')}
          >
            <LayoutDashboard size={18} />
            Dashboard
          </button>
          <button 
            className={`nav-item ${currentView === 'projects' ? 'active' : ''}`}
            onClick={() => onNavigate('projects')}
          >
            <Folder size={18} />
            Projects
          </button>
          <button 
            className={`nav-item ${currentView === 'workspace' ? 'active' : ''}`}
            onClick={() => onNavigate('workspace')}
          >
            <MessageSquare size={18} />
            AI Workspace
          </button>
        </nav>

        <div className="sidebar-bottom">
          <button className="nav-item">
            <Settings size={18} />
            Settings
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="dashboard-main">
        {/* Top Navigation */}
        <header className="dashboard-header">
          <h2 className="page-title">
            {currentView === 'dashboard' ? 'Dashboard' : currentView === 'projects' ? 'Projects' : 'AI Workspace'}
          </h2>
          
          <div className="header-actions">
            {user && (
              <div className="user-menu-wrapper" ref={menuRef}>
                <button
                  className="user-avatar-btn"
                  onClick={() => setUserMenuOpen((v) => !v)}
                  title={user.full_name || user.email}
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
                        logout();
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

        {/* Content */}
        <div className="dashboard-content-scroll">
          {children}
        </div>
      </div>
    </div>
  );
}
