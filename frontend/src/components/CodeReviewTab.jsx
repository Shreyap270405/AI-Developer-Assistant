import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  AlertCircle,
  Info,
  CheckCircle2,
  FileCode,
  ArrowRight,
  Copy,
  Check,
  RefreshCw,
  SlidersHorizontal,
  ChevronDown,
  Sparkles,
} from 'lucide-react';
import { ragApi } from '../services/ragApi';

const REVIEW_TYPES = [
  { value: 'comprehensive', label: '⭐ Comprehensive (All 5 Pillars)' },
  { value: 'security', label: '🛡️ Security & Vulnerabilities' },
  { value: 'performance', label: '⚡ Performance & Resource Leaks' },
  { value: 'correctness', label: '🎯 Logic & Correctness Bugs' },
  { value: 'error_handling', label: '⚠️ Error Handling & Edge Cases' },
  { value: 'maintainability', label: '📖 Maintainability & Clean Code' },
];

export default function CodeReviewTab({ project, activeFile, activeCodeSnippet, onJumpToCitation, showToast }) {
  const [reviewMode, setReviewMode] = useState('active_file'); // 'active_file' | 'custom_snippet'
  const [targetFile, setTargetFile] = useState(activeFile || '');
  const [customSnippet, setCustomSnippet] = useState(activeCodeSnippet || '');
  const [reviewType, setReviewType] = useState('comprehensive');
  const [isLoading, setIsLoading] = useState(false);
  const [reviewResult, setReviewResult] = useState(null);
  const [severityFilter, setSeverityFilter] = useState('all');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [copiedFixId, setCopiedFixId] = useState(null);

  // Sync when active file changes
  useEffect(() => {
    if (activeFile && reviewMode === 'active_file') {
      setTargetFile(activeFile);
    }
  }, [activeFile, reviewMode]);

  const handleUseActiveFile = () => {
    setReviewMode('active_file');
    setTargetFile(activeFile || '');
    if (activeCodeSnippet) setCustomSnippet(activeCodeSnippet);
  };

  const handleRunReview = async (e) => {
    e.preventDefault();
    if (!project) return;

    if (reviewMode === 'active_file' && !targetFile.trim()) {
      showToast?.('Please specify a file path or select a file in the editor', 'warning');
      return;
    }

    if (reviewMode === 'custom_snippet' && !customSnippet.trim()) {
      showToast?.('Please paste or write code to review', 'warning');
      return;
    }

    setIsLoading(true);
    try {
      const payload = {
        review_type: reviewType,
        file_path: reviewMode === 'active_file' ? targetFile.trim() : (targetFile.trim() || 'snippet'),
        code: reviewMode === 'custom_snippet' ? customSnippet.trim() : '',
      };
      const res = await ragApi.reviewCode(project.id, payload);
      setReviewResult(res);
      showToast?.(`Review completed: ${res.findings?.length || 0} findings recorded`, 'success');
    } catch (err) {
      const msg = err.response?.data?.error || err.message;
      showToast?.('Code review failed: ' + msg, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  const copyFixToClipboard = (fixText, findingId) => {
    if (!fixText) return;
    navigator.clipboard.writeText(fixText).then(() => {
      setCopiedFixId(findingId);
      setTimeout(() => setCopiedFixId(null), 2000);
      showToast?.('Copied remediation snippet to clipboard', 'success');
    });
  };

  // Filter findings
  const filteredFindings = (reviewResult?.findings || []).filter((f) => {
    if (severityFilter !== 'all' && f.severity !== severityFilter) return false;
    if (categoryFilter !== 'all' && f.category !== categoryFilter) return false;
    return true;
  });

  return (
    <div className="dev-tool-tab-container">
      {/* Header */}
      <div className="dev-tool-header">
        <h3 className="dev-tool-title">
          <ShieldAlert size={16} className="text-accent" />
          AI Code Review
        </h3>
        <p className="dev-tool-subtitle">
          Grounded architectural review distinguishing verified observations from possible risks. Files are never modified automatically.
        </p>
      </div>

      {/* Target & Options Form */}
      <form onSubmit={handleRunReview} className="dev-tool-config-card">
        <div className="review-mode-toggle-group">
          <button
            type="button"
            className={`btn btn-xs ${reviewMode === 'active_file' ? 'btn-primary' : 'btn-ghost'}`}
            onClick={handleUseActiveFile}
          >
            <FileCode size={13} /> Active Editor File ({activeFile ? activeFile.split('/').pop() : 'None'})
          </button>
          <button
            type="button"
            className={`btn btn-xs ${reviewMode === 'custom_snippet' ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setReviewMode('custom_snippet')}
          >
            Custom Snippet
          </button>
        </div>

        {reviewMode === 'active_file' ? (
          <div className="form-group" style={{ marginTop: '10px' }}>
            <label className="form-label">Target File Path</label>
            <input
              type="text"
              className="form-input"
              value={targetFile}
              onChange={(e) => setTargetFile(e.target.value)}
              placeholder="e.g. backend/app/routes/auth_routes.py"
            />
          </div>
        ) : (
          <div className="form-group" style={{ marginTop: '10px' }}>
            <label className="form-label">Code Snippet to Review</label>
            <textarea
              className="form-textarea"
              rows={5}
              value={customSnippet}
              onChange={(e) => setCustomSnippet(e.target.value)}
              placeholder="Paste code snippet here..."
            />
          </div>
        )}

        <div className="form-group" style={{ marginTop: '10px' }}>
          <label className="form-label">Review Focus</label>
          <select
            className="form-select"
            value={reviewType}
            onChange={(e) => setReviewType(e.target.value)}
          >
            {REVIEW_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>

        <button
          type="submit"
          className="btn btn-primary btn-sm btn-block"
          style={{ marginTop: '12px' }}
          disabled={isLoading || !project}
        >
          {isLoading ? <RefreshCw size={14} className="spin" /> : <ShieldCheck size={14} />}
          <span>{isLoading ? 'Analyzing Codebase...' : 'Run Grounded Review'}</span>
        </button>
      </form>

      {/* Review Results Scroll Area */}
      <div className="dev-tool-content-scroll">
        {isLoading && (
          <div className="search-loading-box">
            <div className="loading-header">
              <Sparkles size={15} className="pulse-icon text-accent" />
              <span>Evaluating security, correctness, and performance with Gemini...</span>
            </div>
            <div className="loading-shimmer-line" style={{ width: '85%' }} />
            <div className="loading-shimmer-line" style={{ width: '92%' }} />
            <div className="loading-shimmer-line" style={{ width: '70%' }} />
          </div>
        )}

        {reviewResult && !isLoading && (
          <div className="review-results-container">
            {/* Score & Summary Card */}
            <div className="review-score-card">
              <div className="score-gauge-box">
                <span className={`score-number ${reviewResult.score >= 80 ? 'good' : reviewResult.score >= 60 ? 'fair' : 'bad'}`}>
                  {reviewResult.score}
                </span>
                <span className="score-label">Health Score</span>
              </div>
              <div className="score-summary-details">
                <div className="score-badges-row">
                  <span className="badge badge-verified">
                    <CheckCircle2 size={11} /> {reviewResult.verified_count || 0} Verified Observations
                  </span>
                  <span className="badge badge-potential">
                    <AlertTriangle size={11} /> {reviewResult.potential_risks_count || 0} Possible Risks
                  </span>
                </div>
                <p className="score-summary-text">{reviewResult.summary}</p>
              </div>
            </div>

            {/* Filter Pills */}
            <div className="review-filters-bar">
              <div className="filter-group">
                <span className="filter-label">Severity:</span>
                {['all', 'critical', 'warning', 'suggestion', 'info'].map((s) => (
                  <button
                    key={s}
                    type="button"
                    className={`filter-pill ${severityFilter === s ? 'active' : ''}`}
                    onClick={() => setSeverityFilter(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {/* Findings List */}
            {filteredFindings.length === 0 ? (
              <div className="empty-results-box" style={{ padding: '24px 16px' }}>
                <CheckCircle2 size={24} className="text-emerald" style={{ margin: '0 auto 8px' }} />
                <p className="empty-results-title">No matching findings</p>
                <p className="empty-results-desc">
                  No issues matched the current filter ({severityFilter}).
                </p>
              </div>
            ) : (
              filteredFindings.map((finding) => (
                <div key={finding.id} className={`finding-card finding-severity-${finding.severity}`}>
                  <div className="finding-header">
                    <div className="finding-header-left">
                      <span className={`finding-severity-badge badge-${finding.severity}`}>
                        {finding.severity.toUpperCase()}
                      </span>
                      <span className="finding-category-pill">{finding.category}</span>
                      <span className={`finding-verified-tag ${finding.is_verified ? 'verified' : 'unverified'}`}>
                        {finding.is_verified ? '✓ Verified Observation' : '? Possible Risk'}
                      </span>
                    </div>

                    {finding.line_range && (
                      <button
                        type="button"
                        className="finding-line-jump-btn"
                        onClick={() =>
                          onJumpToCitation?.(
                            finding.file_path,
                            finding.line_range.start_line,
                            finding.line_range.end_line
                          )
                        }
                        title="Highlight lines in Monaco Editor"
                      >
                        <FileCode size={12} />
                        <span>
                          {finding.file_path?.split('/').pop() || 'file'}: L{finding.line_range.start_line}–
                          {finding.line_range.end_line}
                        </span>
                        <ArrowRight size={11} />
                      </button>
                    )}
                  </div>

                  <h4 className="finding-title">{finding.title}</h4>
                  <p className="finding-explanation">{finding.explanation}</p>

                  {finding.suggested_remediation && (
                    <div className="finding-remediation-box">
                      <div className="remediation-header">
                        <span className="remediation-title">Suggested Remediation:</span>
                        <button
                          type="button"
                          className="btn btn-ghost btn-xs"
                          onClick={() => copyFixToClipboard(finding.suggested_remediation, finding.id)}
                        >
                          {copiedFixId === finding.id ? <Check size={12} /> : <Copy size={12} />}
                          <span>{copiedFixId === finding.id ? 'Copied!' : 'Copy Fix'}</span>
                        </button>
                      </div>
                      <pre className="remediation-code">
                        <code>{finding.suggested_remediation}</code>
                      </pre>
                      <span className="remediation-disclaimer">
                        *Suggestions are static recommendations and are not applied automatically.
                      </span>
                    </div>
                  )}
                </div>
              ))
            )}

            {/* Assumptions & Warnings */}
            {reviewResult.assumptions_warnings?.length > 0 && (
              <div className="alert-card alert-info" style={{ marginTop: '16px' }}>
                <Info size={16} className="alert-icon text-accent" />
                <div className="alert-body">
                  <strong>Assumptions &amp; Notes:</strong>
                  <ul className="bullet-list-sm">
                    {reviewResult.assumptions_warnings.map((w, idx) => (
                      <li key={idx}>{w}</li>
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
