import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useProject } from '../context/ProjectContext';
import { Folder, Clock, FileText, CheckCircle2, AlertCircle, Plus, MoreVertical, Trash2, Edit2, Play } from 'lucide-react';

export default function DashboardPage({ onOpenProject, onNewProject }) {
  const { user } = useAuth();
  const { projects, loadingProjects, removeProject, renameProject, fetchProjects } = useProject();
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState('');

  React.useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const handleRenameSubmit = async (e, id) => {
    e.preventDefault();
    if (editName.trim()) {
      await renameProject(id, editName);
    }
    setEditingId(null);
  };

  const handleDelete = async (id, name) => {
    if (window.confirm(`Are you sure you want to delete "${name}"? This action cannot be undone.`)) {
      await removeProject(id);
    }
  };

  const getStatusIcon = (status) => {
    switch(status) {
      case 'ready': return <CheckCircle2 size={14} className="text-emerald-400" />;
      case 'pending':
      case 'indexing': return <Clock size={14} className="text-amber-400" />;
      case 'error': return <AlertCircle size={14} className="text-rose-400" />;
      default: return <Clock size={14} />;
    }
  };

  const totalFiles = projects.reduce((acc, p) => acc + (p.file_count || 0), 0);

  return (
    <div>
      <div className="dashboard-welcome">
        <h2>Welcome, {user?.full_name || user?.email?.split('@')[0]}!</h2>
        <p>Here's what's happening with your projects today.</p>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon"><Folder size={24} /></div>
          <div className="stat-content">
            <h4>Total Projects</h4>
            <div className="stat-value">{projects.length}</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon"><FileText size={24} /></div>
          <div className="stat-content">
            <h4>Indexed Files</h4>
            <div className="stat-value">{totalFiles}</div>
          </div>
        </div>
      </div>

      <div className="projects-section-header">
        <h3>Your Projects</h3>
        <button className="btn btn-primary" onClick={onNewProject}>
          <Plus size={16} /> New Project
        </button>
      </div>

      {loadingProjects ? (
        <div className="empty-projects">
          <span className="spinner" />
          <p style={{ marginTop: '16px', color: 'var(--text-muted)' }}>Loading projects...</p>
        </div>
      ) : projects.length === 0 ? (
        <div className="empty-projects">
          <div className="empty-projects-icon">
            <Folder size={28} />
          </div>
          <h4>No projects yet</h4>
          <p style={{ color: 'var(--text-muted)', marginBottom: '16px', marginTop: '8px' }}>
            Get started by creating a new project or importing a repository.
          </p>
          <button className="btn btn-primary" onClick={onNewProject}>
            Create your first project
          </button>
        </div>
      ) : (
        <div className="projects-grid">
          {projects.map((p) => (
            <div className="project-card" key={p.id}>
              <div className="project-card-header">
                {editingId === p.id ? (
                  <form onSubmit={(e) => handleRenameSubmit(e, p.id)} style={{ display: 'flex', gap: '8px', width: '100%' }}>
                    <input 
                      type="text" 
                      className="field-input" 
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      autoFocus
                      onBlur={(e) => handleRenameSubmit(e, p.id)}
                      style={{ padding: '4px 8px', fontSize: '1rem' }}
                    />
                  </form>
                ) : (
                  <h4 className="project-card-title">{p.name}</h4>
                )}
              </div>
              <p className="project-card-desc">{p.description || 'No description provided.'}</p>
              
              <div className="project-card-meta">
                <div className="project-card-meta-item">
                  {getStatusIcon(p.status)}
                  <span style={{ textTransform: 'capitalize' }}>{p.status}</span>
                </div>
                <div className="project-card-meta-item">
                  <FileText size={14} />
                  <span>{p.file_count || 0} files</span>
                </div>
                <div className="project-card-meta-item">
                  <Clock size={14} />
                  <span>{new Date(p.created_at).toLocaleDateString()}</span>
                </div>
              </div>

              <div className="project-card-actions">
                <button className="btn btn-primary btn-sm" style={{ flex: 1 }} onClick={() => onOpenProject(p)}>
                  <Play size={14} /> Open
                </button>
                <button 
                  className="btn btn-secondary btn-sm" 
                  onClick={() => {
                    setEditName(p.name);
                    setEditingId(p.id);
                  }}
                  title="Rename Project"
                >
                  <Edit2 size={14} />
                </button>
                <button 
                  className="btn btn-secondary btn-sm" 
                  onClick={() => handleDelete(p.id, p.name)}
                  title="Delete Project"
                  style={{ color: 'var(--rose)' }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
