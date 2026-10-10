import React, { useState } from 'react';
import {
  Folder,
  FolderOpen,
  FileCode,
  FileText,
  FileJson,
  Search,
  ChevronRight,
  ChevronDown,
  RefreshCw,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react';

// ─── Language / icon helpers ──────────────────────────────────────────────────

function getFileIcon(filename) {
  const ext = filename.split('.').pop().toLowerCase();
  switch (ext) {
    case 'js':
    case 'jsx':
    case 'ts':
    case 'tsx':
    case 'py':
    case 'java':
    case 'cpp':
    case 'c':
    case 'go':
    case 'rs':
    case 'rb':
    case 'php':
      return <FileCode size={14} style={{ color: '#38bdf8', flexShrink: 0 }} />;
    case 'json':
    case 'yaml':
    case 'yml':
      return <FileJson size={14} style={{ color: '#f59e0b', flexShrink: 0 }} />;
    case 'md':
    case 'txt':
    case 'rst':
      return <FileText size={14} style={{ color: '#a855f7', flexShrink: 0 }} />;
    default:
      return <FileCode size={14} style={{ color: 'var(--text-dim)', flexShrink: 0 }} />;
  }
}

// ─── TreeNode — recursive ─────────────────────────────────────────────────────

function TreeNode({ node, level = 0, activeFile, onSelectFile, filterText }) {
  const [isOpen, setIsOpen] = useState(level === 0); // root dirs open by default

  if (node.type === 'directory') {
    // If filtering, only render directory if it (or its descendants) match
    const hasChildren = node.children && node.children.length > 0;
    if (!hasChildren) return null;

    const indent = 8 + level * 14;

    return (
      <div role="treeitem" aria-expanded={isOpen}>
        <button
          className="file-tree-node file-tree-dir"
          style={{ paddingLeft: `${indent}px` }}
          onClick={() => setIsOpen(o => !o)}
          aria-label={`${isOpen ? 'Collapse' : 'Expand'} directory ${node.name}`}
        >
          <span className="tree-chevron" aria-hidden="true">
            {isOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
          </span>
          {isOpen
            ? <FolderOpen size={15} style={{ color: '#eab308', flexShrink: 0 }} />
            : <Folder size={15} style={{ color: '#eab308', flexShrink: 0 }} />}
          <span className="tree-name">{node.name}</span>
        </button>

        {isOpen && node.children.map((child, idx) => (
          <TreeNode
            key={child.path || idx}
            node={child}
            level={level + 1}
            activeFile={activeFile}
            onSelectFile={onSelectFile}
            filterText={filterText}
          />
        ))}
      </div>
    );
  }

  // ── File node ───────────────────────────────────────────────────────────────
  if (filterText && !node.name.toLowerCase().includes(filterText.toLowerCase())) {
    return null;
  }

  const isActive = activeFile === node.path;
  const indent = 22 + level * 14;

  return (
    <button
      role="treeitem"
      aria-selected={isActive}
      className={`file-tree-node file-tree-file${isActive ? ' active' : ''}`}
      style={{ paddingLeft: `${indent}px` }}
      onClick={() => onSelectFile(node.path)}
      title={node.path}
    >
      {getFileIcon(node.name)}
      <span className="tree-name">{node.name}</span>
    </button>
  );
}

// ─── FileTree — panel wrapper ─────────────────────────────────────────────────

export default function FileTree({ tree, activeFile, onSelectFile, onRefresh, project, isLoading }) {
  const [filterText, setFilterText] = useState('');
  const [collapsed, setCollapsed] = useState(false);

  if (collapsed) {
    return (
      <aside className="file-tree-panel file-tree-panel--collapsed" aria-label="File explorer (collapsed)">
        <button
          className="tree-collapse-btn"
          onClick={() => setCollapsed(false)}
          title="Expand file explorer"
          aria-label="Expand file explorer"
        >
          <PanelLeftOpen size={18} />
        </button>
      </aside>
    );
  }

  return (
    <aside className="file-tree-panel" aria-label="File explorer">
      {/* Panel header */}
      <div className="file-tree-header">
        <span className="file-tree-title">
          EXPLORER
          {project?.file_count > 0 && (
            <span className="file-count-badge">{project.file_count}</span>
          )}
        </span>
        <div style={{ display: 'flex', gap: '4px' }}>
          <button
            className="icon-btn"
            onClick={onRefresh}
            title="Refresh file tree"
            aria-label="Refresh file tree"
          >
            <RefreshCw size={13} />
          </button>
          <button
            className="icon-btn"
            onClick={() => setCollapsed(true)}
            title="Collapse panel"
            aria-label="Collapse file explorer"
          >
            <PanelLeftClose size={13} />
          </button>
        </div>
      </div>

      {/* Search bar */}
      <div className="file-tree-search">
        <Search size={13} className="search-icon" aria-hidden="true" />
        <input
          type="search"
          placeholder="Search files…"
          value={filterText}
          onChange={e => setFilterText(e.target.value)}
          className="tree-search-input"
          aria-label="Filter files"
        />
      </div>

      {/* Tree body */}
      <div className="file-tree-body" role="tree" aria-label="Project files">
        {isLoading ? (
          <div className="tree-empty">
            <span className="spinner" style={{ width: '20px', height: '20px', borderWidth: '2px' }} />
            <span>Loading files…</span>
          </div>
        ) : (!tree || tree.length === 0) ? (
          <div className="tree-empty">
            <Folder size={32} style={{ opacity: 0.3 }} aria-hidden="true" />
            <p style={{ margin: '8px 0 4px', fontWeight: 500 }}>No files yet</p>
            <p style={{ fontSize: '11px', color: 'var(--text-dim)', lineHeight: 1.5 }}>
              Upload a .zip archive or import a GitHub repository to index this project.
            </p>
          </div>
        ) : (
          tree.map((node, i) => (
            <TreeNode
              key={node.path || i}
              node={node}
              activeFile={activeFile}
              onSelectFile={onSelectFile}
              filterText={filterText}
            />
          ))
        )}
      </div>
    </aside>
  );
}
