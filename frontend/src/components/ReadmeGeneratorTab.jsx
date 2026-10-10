import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  FileText,
  Sparkles,
  Download,
  Copy,
  Check,
  Save,
  Layers,
  ShieldCheck,
  AlertCircle,
  HelpCircle,
  RefreshCw,
} from 'lucide-react';
import { ragApi } from '../services/ragApi';

export default function ReadmeGeneratorTab({ project, onRefreshFileTree, showToast }) {
  const [customInstructions, setCustomInstructions] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [docResult, setDocResult] = useState(null);
  const [copiedDoc, setCopiedDoc] = useState(false);
  const [activeSubTab, setActiveSubTab] = useState('preview'); // 'preview' | 'raw'

  const handleGenerateDocs = async (e) => {
    e.preventDefault();
    if (!project) return;

    setIsGenerating(true);
    try {
      const res = await ragApi.generateDocs(project.id, customInstructions.trim());
      setDocResult(res);
      showToast?.('Project documentation generated successfully!', 'success');
    } catch (err) {
      const msg = err.response?.data?.error || err.message;
      showToast?.('Documentation generation failed: ' + msg, 'error');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCopyMarkdown = () => {
    if (!docResult?.markdown) return;
    navigator.clipboard.writeText(docResult.markdown).then(() => {
      setCopiedDoc(true);
      setTimeout(() => setCopiedDoc(false), 2000);
      showToast?.('Copied markdown to clipboard', 'success');
    });
  };

  const handleDownloadMarkdown = () => {
    if (!docResult?.markdown) return;
    const blob = new Blob([docResult.markdown], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'README.md';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast?.('Downloaded README.md', 'success');
  };

  const handleSaveToProject = async () => {
    if (!docResult?.markdown || !project) return;
    setIsSaving(true);
    try {
      const res = await ragApi.saveDocs(project.id, 'README.md', docResult.markdown);
      showToast?.(res.message || 'Saved README.md to project repository!', 'success');
      onRefreshFileTree?.();
    } catch (err) {
      const msg = err.response?.data?.error || err.message;
      showToast?.('Failed to save to project: ' + msg, 'error');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="dev-tool-tab-container">
      {/* Header */}
      <div className="dev-tool-header">
        <h3 className="dev-tool-title">
          <FileText size={16} className="text-accent" />
          README &amp; Documentation Generator
        </h3>
        <p className="dev-tool-subtitle">
          Generate accurate, evidence-grounded project documentation from repository manifests and retrieved source code. Secrets are always redacted.
        </p>
      </div>

      {/* Generator Configuration Form */}
      <form onSubmit={handleGenerateDocs} className="dev-tool-config-card">
        <div className="doc-project-banner">
          <span className="doc-banner-label">Active Project:</span>
          <span className="doc-banner-name">{project?.name}</span>
        </div>

        <div className="form-group" style={{ marginTop: '10px' }}>
          <label className="form-label">Custom Focus / Section Requests (Optional)</label>
          <input
            type="text"
            className="form-input"
            value={customInstructions}
            onChange={(e) => setCustomInstructions(e.target.value)}
            placeholder="e.g. Emphasize Docker deployment and database migration setup"
          />
        </div>

        <button
          type="submit"
          className="btn btn-primary btn-sm btn-block"
          style={{ marginTop: '12px' }}
          disabled={isGenerating || !project}
        >
          {isGenerating ? <RefreshCw size={14} className="spin" /> : <Sparkles size={14} />}
          <span>{isGenerating ? 'Synthesizing Documentation...' : 'Generate README.md'}</span>
        </button>
      </form>

      {/* Content Scroll Area */}
      <div className="dev-tool-content-scroll">
        {isGenerating && (
          <div className="search-loading-box">
            <div className="loading-header">
              <Sparkles size={15} className="pulse-icon text-accent" />
              <span>Analyzing manifests and architectural RAG context...</span>
            </div>
            <div className="loading-shimmer-line" style={{ width: '85%' }} />
            <div className="loading-shimmer-line" style={{ width: '95%' }} />
            <div className="loading-shimmer-line" style={{ width: '70%' }} />
          </div>
        )}

        {docResult && !isGenerating && (
          <div className="doc-results-container">
            {/* Tech Stack & Evidence Banner */}
            <div className="doc-evidence-card">
              <div className="doc-evidence-row">
                <span className="doc-evidence-title">
                  <Layers size={13} /> Detected Tech Stack:
                </span>
                <div className="doc-tags-group">
                  {docResult.detected_stack?.length > 0 ? (
                    docResult.detected_stack.map((item, idx) => (
                      <span key={idx} className="doc-tech-tag">{item}</span>
                    ))
                  ) : (
                    <span className="text-dim text-xs">[None identified in manifests]</span>
                  )}
                </div>
              </div>

              {docResult.evidence_files?.length > 0 && (
                <div className="doc-evidence-row" style={{ marginTop: '6px' }}>
                  <span className="doc-evidence-title">
                    <ShieldCheck size={13} /> Manifest Sources:
                  </span>
                  <div className="doc-tags-group">
                    {docResult.evidence_files.map((file, idx) => (
                      <span key={idx} className="doc-file-tag">{file}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Action Toolbar */}
            <div className="doc-actions-bar">
              <div className="doc-view-tabs">
                <button
                  type="button"
                  className={`btn btn-xs ${activeSubTab === 'preview' ? 'btn-primary' : 'btn-ghost'}`}
                  onClick={() => setActiveSubTab('preview')}
                >
                  Preview
                </button>
                <button
                  type="button"
                  className={`btn btn-xs ${activeSubTab === 'raw' ? 'btn-primary' : 'btn-ghost'}`}
                  onClick={() => setActiveSubTab('raw')}
                >
                  Raw Markdown
                </button>
              </div>

              <div className="doc-buttons-right">
                <button
                  type="button"
                  className="btn btn-secondary btn-xs"
                  onClick={handleCopyMarkdown}
                  title="Copy markdown text"
                >
                  {copiedDoc ? <Check size={12} /> : <Copy size={12} />}
                  <span>{copiedDoc ? 'Copied' : 'Copy'}</span>
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-xs"
                  onClick={handleDownloadMarkdown}
                  title="Download as README.md"
                >
                  <Download size={12} />
                  <span>Download</span>
                </button>
                <button
                  type="button"
                  className="btn btn-primary btn-xs"
                  onClick={handleSaveToProject}
                  disabled={isSaving}
                  title="Save directly into project workspace"
                >
                  {isSaving ? <RefreshCw size={12} className="spin" /> : <Save size={12} />}
                  <span>{isSaving ? 'Saving...' : 'Save to Project'}</span>
                </button>
              </div>
            </div>

            {/* Documentation Preview */}
            <div className="doc-preview-wrapper">
              {activeSubTab === 'preview' ? (
                <div className="markdown-body doc-markdown-body">
                  <ReactMarkdown>{docResult.markdown}</ReactMarkdown>
                </div>
              ) : (
                <pre className="doc-raw-code">
                  <code>{docResult.markdown}</code>
                </pre>
              )}
            </div>

            {/* Unknown Items or Security Warnings Notice */}
            {((docResult.unknown_items && docResult.unknown_items.length > 0) ||
              (docResult.warnings && docResult.warnings.length > 0)) && (
              <div className="alert-card alert-info" style={{ marginTop: '12px' }}>
                <HelpCircle size={16} className="alert-icon text-accent" />
                <div className="alert-body">
                  <strong>Evidence Grounding &amp; Unknown Data:</strong>
                  <ul className="bullet-list-sm">
                    {docResult.unknown_items?.map((item, idx) => (
                      <li key={`u-${idx}`}>{item}</li>
                    ))}
                    {docResult.warnings?.map((w, idx) => (
                      <li key={`w-${idx}`}>{w}</li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
