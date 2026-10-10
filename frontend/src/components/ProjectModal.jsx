import React, { useState, useEffect } from 'react';
import { X, Upload, GitBranch, FolderPlus, Loader2 } from 'lucide-react';
import { projectApi } from '../services/projectApi';
import { fileApi } from '../services/fileApi';
import { githubApi } from '../services/githubApi';

export default function ProjectModal({
  isOpen,
  initialTab = 'create', // 'create' | 'upload' | 'github'
  activeProject,
  onClose,
  onProjectReady,
  showToast,
}) {
  const [tab, setTab] = useState(initialTab);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [githubUrl, setGithubUrl] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');

  // Sync tab when parent changes which type to open (Create vs Upload vs GitHub)
  useEffect(() => {
    if (isOpen) setTab(initialTab);
  }, [isOpen, initialTab]);

  // Reset form fields when modal opens
  useEffect(() => {
    if (isOpen) {
      setName('');
      setDescription('');
      setGithubUrl('');
      setSelectedFile(null);
      setStatusMessage('');
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleCreateEmpty = async (e) => {
    e.preventDefault();
    if (isLoading) return;
    if (!name.trim()) return;

    setIsLoading(true);
    setStatusMessage('Creating project workspace...');
    try {
      const res = await projectApi.create(name.trim(), description.trim());
      showToast?.('Project created successfully!', 'success');
      onProjectReady(res.project);
      onClose();
    } catch (err) {
      const msg = err.response?.data?.error || err.message;
      showToast?.('Failed to create project: ' + msg, 'error');
    } finally {
      setIsLoading(false);
      setStatusMessage('');
    }
  };

  const handleUploadZip = async (e) => {
    e.preventDefault();
    if (isLoading) return;
    if (!selectedFile) {
      showToast?.('Please select a .zip file', 'warning');
      return;
    }

    setIsLoading(true);
    try {
      setStatusMessage('Creating project workspace...');
      const projName = name.trim() || selectedFile.name.replace(/\.zip$/i, '');
      const projDesc = description.trim() || 'Uploaded from zip archive';
      const pRes = await projectApi.create(projName, projDesc);
      const targetProj = pRes.project;

      setStatusMessage('Extracting files and generating FAISS vector index...');
      const uploadRes = await fileApi.uploadZip(targetProj.id, selectedFile);

      showToast?.(
        `Indexed ${uploadRes.file_count} files (${uploadRes.chunk_count} code chunks)!`,
        'success'
      );
      const fresh = await projectApi.get(targetProj.id);
      onProjectReady(fresh.project);
      onClose();
    } catch (err) {
      const msg = err.response?.data?.error || err.message;
      showToast?.('Upload failed: ' + msg, 'error');
    } finally {
      setIsLoading(false);
      setStatusMessage('');
    }
  };

  const handleImportGithub = async (e) => {
    e.preventDefault();
    if (isLoading) return;
    if (!githubUrl.trim()) {
      showToast?.('Please enter a GitHub repository URL', 'warning');
      return;
    }

    setIsLoading(true);
    try {
      setStatusMessage('Creating project workspace...');
      const defaultName =
        githubUrl.trim().split('/').pop().replace(/\.git$/i, '') || 'github-repo';
      const projName = name.trim() || defaultName;
      const projDesc = description.trim() || `Imported from ${githubUrl.trim()}`;
      const pRes = await projectApi.create(projName, projDesc);
      const targetProj = pRes.project;

      setStatusMessage('Downloading repository & building vector embeddings...');
      const importRes = await githubApi.importRepo(targetProj.id, githubUrl.trim());

      showToast?.(
        `Imported ${importRes.repo}: ${importRes.file_count} files, ${importRes.chunk_count} chunks indexed!`,
        'success'
      );
      const fresh = await projectApi.get(targetProj.id);
      onProjectReady(fresh.project);
      onClose();
    } catch (err) {
      const msg = err.response?.data?.error || err.message;
      showToast?.('GitHub import failed: ' + msg, 'error');
    } finally {
      setIsLoading(false);
      setStatusMessage('');
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">
            {tab === 'create' && 'Create New Project'}
            {tab === 'upload' && 'Upload Codebase Archive (.zip)'}
            {tab === 'github' && 'Import from GitHub'}
          </h2>
          <button className="btn-ghost" onClick={onClose} disabled={isLoading} aria-label="Close">
            <X size={18} />
          </button>
        </div>

        {/* Modal Tabs */}
        <div
          style={{
            display: 'flex',
            borderBottom: '1px solid var(--border-subtle)',
            background: 'var(--bg-subtle)',
          }}
        >
          {[
            { id: 'create', icon: <FolderPlus size={14} />, label: 'New Project' },
            { id: 'upload', icon: <Upload size={14} />, label: 'Upload ZIP' },
            { id: 'github', icon: <GitBranch size={14} />, label: 'GitHub Import' },
          ].map(({ id, icon, label }) => (
            <button
              key={id}
              className={`btn-ghost ${tab === id ? 'btn-primary' : ''}`}
              style={{
                flex: 1,
                borderRadius: 0,
                padding: '10px 8px',
                fontSize: '13px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px',
              }}
              onClick={() => setTab(id)}
              disabled={isLoading}
            >
              {icon} {label}
            </button>
          ))}
        </div>

        <div className="modal-body">
          {tab === 'create' && (
            <form onSubmit={handleCreateEmpty} id="create-proj-form">
              <div className="form-group">
                <label className="form-label">Project Name *</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. ecommerce-backend"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  disabled={isLoading}
                  autoFocus
                />
              </div>
              <div className="form-group" style={{ marginTop: '12px' }}>
                <label className="form-label">Description (Optional)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Short summary of this codebase..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  disabled={isLoading}
                />
              </div>
            </form>
          )}

          {tab === 'upload' && (
            <form onSubmit={handleUploadZip} id="upload-zip-form">
              <div className="form-group" style={{ marginBottom: '12px' }}>
                <label className="form-label">Project Name (Optional)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder={selectedFile ? selectedFile.name.replace(/\.zip$/i, '') : 'Auto-derived from ZIP filename'}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={isLoading}
                />
              </div>
              <div
                className="dropzone"
                onClick={() => document.getElementById('zip-file-input').click()}
              >
                <Upload size={32} style={{ color: 'var(--primary)', margin: '0 auto 10px' }} />
                <p style={{ fontWeight: 500, color: 'var(--text-main)' }}>
                  {selectedFile ? selectedFile.name : 'Click to select project .zip file'}
                </p>
                <p style={{ fontSize: '12px', color: 'var(--text-dim)', marginTop: '4px' }}>
                  Max 50MB. node_modules, .git, venv, and secrets are excluded automatically.
                </p>
                <input
                  id="zip-file-input"
                  type="file"
                  accept=".zip"
                  style={{ display: 'none' }}
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      setSelectedFile(e.target.files[0]);
                      if (!name) {
                        setName(e.target.files[0].name.replace(/\.zip$/i, ''));
                      }
                    }
                  }}
                  disabled={isLoading}
                />
              </div>
            </form>
          )}

          {tab === 'github' && (
            <form onSubmit={handleImportGithub} id="github-form">
              <div className="form-group">
                <label className="form-label">GitHub Repository URL *</label>
                <input
                  type="url"
                  className="form-input"
                  placeholder="https://github.com/owner/repository"
                  value={githubUrl}
                  onChange={(e) => {
                    setGithubUrl(e.target.value);
                    if (!name) {
                      const extracted = e.target.value.trim().split('/').pop().replace(/\.git$/i, '');
                      if (extracted) setName(extracted);
                    }
                  }}
                  required
                  disabled={isLoading}
                  autoFocus
                />
                <p style={{ fontSize: '12px', color: 'var(--text-dim)', marginTop: '4px' }}>
                  Downloads via GitHub REST API — no git CLI required on the host.
                </p>
              </div>
              <div className="form-group" style={{ marginTop: '12px' }}>
                <label className="form-label">Project Name (Optional)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Auto-derived from repository name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={isLoading}
                />
              </div>
            </form>
          )}

          {isLoading && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '12px',
                background: 'var(--primary-subtle)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-accent)',
                fontSize: '13px',
              }}
            >
              <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
              <span>{statusMessage}</span>
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </button>
          {tab === 'create' && (
            <button
              type="submit"
              form="create-proj-form"
              className="btn btn-primary"
              disabled={isLoading || !name.trim()}
            >
              {isLoading ? 'Creating...' : 'Create Project'}
            </button>
          )}
          {tab === 'upload' && (
            <button
              type="submit"
              form="upload-zip-form"
              className="btn btn-primary"
              disabled={isLoading || !selectedFile}
            >
              {isLoading ? 'Processing...' : 'Upload & Index'}
            </button>
          )}
          {tab === 'github' && (
            <button
              type="submit"
              form="github-form"
              className="btn btn-primary"
              disabled={isLoading || !githubUrl.trim()}
            >
              {isLoading ? 'Importing...' : 'Import & Index'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
