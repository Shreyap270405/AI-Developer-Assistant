import React, { useState, useEffect, useMemo } from 'react';
import { useProject } from '../context/ProjectContext';
import {
  Folder,
  Clock,
  FileText,
  CheckCircle2,
  AlertCircle,
  Plus,
  Trash2,
  Edit2,
  Play,
  Search,
  RefreshCw,
  X,
  Layers,
} from 'lucide-react';

export default function ProjectsPage({ onOpenProject, onNewProject }) {
  const {
    projects,
    loadingProjects,
    removeProject,
    renameProject,
    fetchProjects,
  } = useProject();

  const [searchQuery, setSearchQuery] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState('');
  const [isDeletingId, setIsDeletingId] = useState(null);

  // Sync projects on mount to ensure fresh state
  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const handleRenameSubmit = async (e, id) => {
    e.preventDefault();
    if (editName.trim()) {
      try {
        await renameProject(id, editName.trim());
      } catch (err) {
        console.error('Failed to rename project:', err);
      }
    }
    setEditingId(null);
  };

  const handleDelete = async (id, name) => {
    if (window.confirm(`Are you sure you want to delete "${name}"? This action cannot be undone.`)) {
      setIsDeletingId(id);
      try {
        await removeProject(id);
      } catch (err) {
        console.error('Failed to delete project:', err);
      } finally {
        setIsDeletingId(null);
      }
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'ready':
        return <CheckCircle2 size={14} className="text-emerald-400" style={{ color: 'var(--emerald)' }} />;
      case 'pending':
      case 'indexing':
        return <Clock size={14} className="text-amber-400" style={{ color: 'var(--amber)' }} />;
      case 'error':
        return <AlertCircle size={14} className="text-rose-400" style={{ color: 'var(--rose)' }} />;
      default:
        return <Clock size={14} />;
    }
  };

  // Filter projects by search query
  const filteredProjects = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return projects;
    return projects.filter(
      (p) =>
        p.name?.toLowerCase().includes(q) ||
        p.description?.toLowerCase().includes(q)
    );
  }, [projects, searchQuery]);

  return (
    <div className="projects-page-container">
      {/* Header bar */}
      <div className="projects-page-header">
        <div className="projects-header-info">
          <h2>All Projects</h2>
          <p>Manage, inspect, and open all your workspace repositories.</p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => fetchProjects()}
            disabled={loadingProjects}
            title="Refresh project list"
          >
            <RefreshCw size={14} className={loadingProjects ? 'spin' : ''} />
            <span>Refresh</span>
          </button>
          <button className="btn btn-primary btn-sm" onClick={onNewProject}>
            <Plus size={16} />
            <span>New Project</span>
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="projects-filter-bar">
        <div className="projects-search-input">
          <Search size={15} style={{ color: 'var(--text-dim)', flexShrink: 0 }} />
          <input
            type="text"
            placeholder="Search projects by name or description..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              style={{ padding: 0, color: 'var(--text-dim)', cursor: 'pointer' }}
              title="Clear search"
            >
              <X size={14} />
            </button>
          )}
        </div>

        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          Showing <strong>{filteredProjects.length}</strong> of <strong>{projects.length}</strong> project{projects.length === 1 ? '' : 's'}
        </div>
      </div>

      {/* Loading state */}
      {loadingProjects && projects.length === 0 ? (
        <div className="empty-projects">
          <span className="spinner" />
          <p style={{ marginTop: '16px', color: 'var(--text-muted)' }}>Loading projects...</p>
        </div>
      ) : projects.length === 0 ? (
        /* Empty State: No projects at all */
        <div className="empty-projects">
          <div className="empty-projects-icon">
            <Folder size={32} />
          </div>
          <h4>No projects yet</h4>
          <p style={{ color: 'var(--text-muted)', marginBottom: '16px', marginTop: '8px', maxWidth: '380px' }}>
            Get started by creating a new empty project or importing a repository from a ZIP archive or GitHub.
          </p>
          <button className="btn btn-primary" onClick={onNewProject}>
            <Plus size={16} /> Create your first project
          </button>
        </div>
      ) : filteredProjects.length === 0 ? (
        /* Empty Search Filter Results */
        <div className="empty-projects">
          <div className="empty-projects-icon">
            <Search size={28} />
          </div>
          <h4>No matching projects</h4>
          <p style={{ color: 'var(--text-muted)', marginBottom: '16px', marginTop: '8px' }}>
            No projects matched &ldquo;{searchQuery}&rdquo;.
          </p>
          <button className="btn btn-secondary btn-sm" onClick={() => setSearchQuery('')}>
            Clear search filter
          </button>
        </div>
      ) : (
        /* Projects Grid */
        <div className="projects-grid">
          {filteredProjects.map((p) => (
            <div className="project-card" key={p.id}>
              <div className="project-card-header">
                {editingId === p.id ? (
                  <form
                    onSubmit={(e) => handleRenameSubmit(e, p.id)}
                    style={{ display: 'flex', gap: '8px', width: '100%' }}
                  >
                    <input
                      type="text"
                      className="field-input"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      autoFocus
                      onBlur={(e) => handleRenameSubmit(e, p.id)}
                      style={{ padding: '4px 8px', fontSize: '1rem', width: '100%' }}
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
                <button
                  className="btn btn-primary btn-sm"
                  style={{ flex: 1 }}
                  onClick={() => onOpenProject(p)}
                  title={`Open ${p.name} in AI Workspace`}
                >
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
                  disabled={isDeletingId === p.id}
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
