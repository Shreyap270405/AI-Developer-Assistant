import React, { useState } from 'react';
import { useProject } from '../context/ProjectContext';
import FileTree from '../components/FileTree';
import EditorView from '../components/EditorView';
import AiPanel from '../components/AiPanel';
import UploadPanel from '../components/UploadPanel';
import GitHubImportPanel from '../components/GitHubImportPanel';
import { useFileEditor } from '../hooks/useFileEditor';
import { useToast } from '../hooks/useToast';
import Toast from '../components/Toast';
import {
  ArrowLeft,
  Code2,
  Upload,
  GitBranch,
  PanelRightClose,
  PanelRightOpen,
  Sparkles,
  AlertCircle,
  FolderUp,
} from 'lucide-react';

export default function WorkspacePage({ onBackToDashboard, onNavigateToProjects }) {
  const { activeProject, selectProject, fetchProjects } = useProject();
  const { toast, showToast, closeToast } = useToast();

  const [aiPanelOpen, setAiPanelOpen] = useState(true);
  const [uploadPanelOpen, setUploadPanelOpen] = useState(false);
  const [githubPanelOpen, setGithubPanelOpen] = useState(false);

  const {
    fileTree,
    activeFilePath,
    activeFileContent,
    activeFileLanguage,
    highlightRange,
    isSaving,
    loadFileTree,
    selectFile,
    jumpToCitation,
    saveFile,
    clearEditor,
    isLoadingTree,
  } = useFileEditor(activeProject, showToast);

  // Load tree when project is available
  React.useEffect(() => {
    if (activeProject?.id) {
      loadFileTree(activeProject.id);
      clearEditor();
    }
  }, [activeProject?.id, loadFileTree, clearEditor]);

  // After a successful upload or GitHub import, refresh tree
  const handleUploadComplete = () => {
    if (activeProject?.id) {
      fetchProjects();
      loadFileTree(activeProject.id);
      showToast('Project files updated', 'success');
    }
  };

  const handleGithubImportComplete = () => {
    if (activeProject?.id) {
      fetchProjects();
      loadFileTree(activeProject.id);
      showToast('GitHub repository imported and indexed', 'success');
    }
  };

  const openUploadPanel = () => {
    setUploadPanelOpen(true);
    setGithubPanelOpen(false);
  };

  const openGithubPanel = () => {
    setGithubPanelOpen(true);
    setUploadPanelOpen(false);
  };

  // ── No project selected ──
  if (!activeProject) {
    return (
      <div className="workspace-shell">
        <div className="workspace-no-project">
          <Sparkles size={52} strokeWidth={1.2} aria-hidden="true" style={{ opacity: 0.25 }} />
          <p className="workspace-empty-title">No project selected</p>
          <p className="workspace-empty-subtitle">
            Go back to the dashboard or projects page to open a workspace.
          </p>
          <div style={{ display: 'flex', gap: '10px', marginTop: '8px' }}>
            <button className="btn btn-primary" onClick={onBackToDashboard}>
              <ArrowLeft size={16} /> Back to Dashboard
            </button>
            {onNavigateToProjects && (
              <button className="btn btn-secondary" onClick={onNavigateToProjects}>
                All Projects
              </button>
            )}
          </div>
        </div>
        <Toast toast={toast} onClose={closeToast} />
      </div>
    );
  }

  return (
    <div className="workspace-shell">
      {/* ── Top bar ── */}
      <header className="workspace-topbar">
        <div className="workspace-topbar-left">
          <button
            className="btn btn-ghost btn-sm"
            onClick={onBackToDashboard}
            aria-label="Back to dashboard"
          >
            <ArrowLeft size={16} />
            <span>Dashboard</span>
          </button>
          {onNavigateToProjects && (
            <button
              className="btn btn-ghost btn-sm"
              onClick={onNavigateToProjects}
              aria-label="Back to projects"
            >
              <span>Projects</span>
            </button>
          )}
          <span className="topbar-divider" aria-hidden="true">/</span>
          <div className="topbar-brand">
            <Code2 size={16} aria-hidden="true" />
            <span className="topbar-project-name">{activeProject.name}</span>
            <span
              className={`topbar-status-dot ${activeProject.status === 'ready' ? 'ready' : 'pending'}`}
              title={`Status: ${activeProject.status}`}
              aria-label={`Project status: ${activeProject.status}`}
            />
          </div>
        </div>

        <div className="workspace-topbar-right">
          {activeProject.status === 'error' && (
            <span className="topbar-badge topbar-badge--error">
              <AlertCircle size={13} /> Index Error
            </span>
          )}

          <button
            className={`btn btn-sm ${uploadPanelOpen ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => uploadPanelOpen ? setUploadPanelOpen(false) : openUploadPanel()}
            title={uploadPanelOpen ? 'Hide upload panel' : 'Upload project archive'}
            aria-expanded={uploadPanelOpen}
            aria-label={uploadPanelOpen ? 'Close upload panel' : 'Upload ZIP archive'}
          >
            <FolderUp size={14} />
            <span>Upload</span>
          </button>

          <button
            className={`btn btn-sm ${githubPanelOpen ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => githubPanelOpen ? setGithubPanelOpen(false) : openGithubPanel()}
            title={githubPanelOpen ? 'Hide GitHub import panel' : 'Import from GitHub'}
            aria-expanded={githubPanelOpen}
            aria-label={githubPanelOpen ? 'Close GitHub import panel' : 'Import GitHub repository'}
          >
            <GitBranch size={14} />
            <span>GitHub</span>
          </button>

          <button
            className={`btn btn-sm ${aiPanelOpen ? 'btn-secondary' : 'btn-secondary'}`}
            onClick={() => setAiPanelOpen(o => !o)}
            title={aiPanelOpen ? 'Hide AI panel' : 'Show AI panel'}
            aria-expanded={aiPanelOpen}
            aria-label={aiPanelOpen ? 'Hide AI assistant panel' : 'Show AI assistant panel'}
          >
            {aiPanelOpen ? <PanelRightClose size={16} /> : <PanelRightOpen size={16} />}
          </button>
        </div>
      </header>

      {/* ── Three-pane body ── */}
      <div className="workspace-body">
        {/* Left: File explorer */}
        <FileTree
          tree={fileTree}
          activeFile={activeFilePath}
          onSelectFile={selectFile}
          onRefresh={() => loadFileTree(activeProject.id)}
          project={activeProject}
          isLoading={isLoadingTree}
        />

        {/* Upload Panel */}
        {uploadPanelOpen && (
          <UploadPanel
            project={activeProject}
            onUploadComplete={handleUploadComplete}
            onClose={() => setUploadPanelOpen(false)}
          />
        )}

        {/* GitHub Import Panel */}
        {githubPanelOpen && (
          <GitHubImportPanel
            project={activeProject}
            onImportComplete={handleGithubImportComplete}
            onClose={() => setGithubPanelOpen(false)}
          />
        )}

        {/* Centre: Monaco editor */}
        {!uploadPanelOpen && !githubPanelOpen && (
          <EditorView
            filePath={activeFilePath}
            content={activeFileContent}
            language={activeFileLanguage}
            onSave={saveFile}
            highlightRange={highlightRange}
            isSaving={isSaving}
          />
        )}

        {/* Right: AI assistant panel */}
        {aiPanelOpen && !uploadPanelOpen && !githubPanelOpen && (
          <AiPanel
            project={activeProject}
            activeFile={activeFilePath}
            activeFileContent={activeFileContent}
            onJumpToCitation={jumpToCitation}
            showToast={showToast}
            onRefreshFileTree={() => activeProject?.id && loadFileTree(activeProject.id)}
          />
        )}
      </div>

      <Toast toast={toast} onClose={closeToast} />
    </div>
  );
}
