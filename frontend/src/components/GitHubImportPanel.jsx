import React, { useState, useEffect, useCallback } from "react";
import {
  GitBranch,
  Download,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Loader2,
  AlertCircle,
  Clock,
  Star,
  GitCommit,
  ExternalLink,
  ChevronRight,
  X,
} from "lucide-react";
import { githubApi } from "../services/githubApi";

// --- helpers ------------------------------------------------------------------

function fmtStatus(status) {
  const map = {
    pending: "Pending",
    validating: "Validating repository\u2026",
    importing: "Downloading repository\u2026",
    indexing: "Building vector index\u2026",
    completed: "Indexed",
    failed: "Import failed",
    rate_limited: "GitHub rate limit reached",
    unsupported: "Unsupported repository",
  };
  return map[status] || status;
}

function StatusBadge({ status }) {
  const cfg = {
    completed: { cls: "gh-badge gh-badge--success", icon: <CheckCircle2 size={13} /> },
    failed: { cls: "gh-badge gh-badge--error", icon: <XCircle size={13} /> },
    rate_limited: { cls: "gh-badge gh-badge--warn", icon: <Clock size={13} /> },
    indexing: { cls: "gh-badge gh-badge--active", icon: <Loader2 size={13} className="spin" /> },
    importing: { cls: "gh-badge gh-badge--active", icon: <Loader2 size={13} className="spin" /> },
    validating: { cls: "gh-badge gh-badge--active", icon: <Loader2 size={13} className="spin" /> },
  };
  const { cls = "gh-badge gh-badge--neutral", icon = <AlertCircle size={13} /> } = cfg[status] || {};
  return (
    <span className={cls}>
      {icon}
      {fmtStatus(status)}
    </span>
  );
}

function RepoCard({ importData }) {
  if (!importData) return null;
  return (
    <div className="gh-repo-card">
      <div className="gh-repo-card-header">
        <GitBranch size={15} style={{ color: "var(--accent-primary)" }} />
        <span className="gh-repo-name">{importData.full_name}</span>
        {importData.html_url && (
          <a
            href={importData.html_url}
            target="_blank"
            rel="noopener noreferrer"
            className="gh-repo-link"
            aria-label="Open repository on GitHub"
          >
            <ExternalLink size={12} />
          </a>
        )}
      </div>
      {importData.description && (
        <p className="gh-repo-desc">{importData.description}</p>
      )}
      <div className="gh-repo-meta">
        {importData.language && (
          <span className="gh-meta-pill">{importData.language}</span>
        )}
        {importData.stars > 0 && (
          <span className="gh-meta-pill">
            <Star size={11} /> {importData.stars}
          </span>
        )}
        {importData.commit_sha && (
          <span className="gh-meta-pill">
            <GitCommit size={11} /> {importData.commit_sha.slice(0, 8)}
          </span>
        )}
        {importData.default_branch && (
          <span className="gh-meta-pill">
            <GitBranch size={11} /> {importData.default_branch}
          </span>
        )}
      </div>
      {(importData.extracted_files > 0 || importData.indexed_chunks > 0) && (
        <div className="gh-repo-stats">
          <span>{importData.extracted_files} files</span>
          <ChevronRight size={10} />
          <span>{importData.indexed_chunks} chunks indexed</span>
        </div>
      )}
    </div>
  );
}

// --- main component -----------------------------------------------------------

export default function GitHubImportPanel({ project, onImportComplete, onClose }) {
  const [repoUrl, setRepoUrl] = useState("");
  const [phase, setPhase] = useState("idle"); // idle | validating | previewing | importing | done | error
  const [importStatus, setImportStatus] = useState(null); // import_status string from API
  const [repoMeta, setRepoMeta] = useState(null); // validate response
  const [importRecord, setImportRecord] = useState(null); // from status or import response
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  // Load existing import status on mount / project change
  const loadStatus = useCallback(async () => {
    if (!project?.id) return;
    try {
      const data = await githubApi.getStatus(project.id);
      if (data.has_github_import) {
        setImportRecord(data.import);
        setImportStatus(data.import.import_status);
        if (data.import.repo_url) setRepoUrl(data.import.repo_url);
        if (data.import.import_status === "completed") setPhase("done");
        else if (["failed", "rate_limited"].includes(data.import.import_status)) setPhase("error");
      }
    } catch {
      // non-critical
    }
  }, [project?.id]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const reset = () => {
    setPhase("idle");
    setRepoMeta(null);
    setErrorMsg("");
    setSuccessMsg("");
    setImportStatus(null);
  };

  // Step 1: validate
  const handleValidate = async (e) => {
    e.preventDefault();
    if (!repoUrl.trim()) return;
    setPhase("validating");
    setErrorMsg("");
    setRepoMeta(null);
    try {
      const data = await githubApi.validateRepo(project.id, repoUrl.trim());
      if (data.valid) {
        setRepoMeta(data.repository);
        setPhase("previewing");
      } else {
        setErrorMsg(data.error || "Repository validation failed.");
        setPhase("error");
      }
    } catch (err) {
      const msg = err.response?.data?.error || err.message || "Validation failed.";
      setErrorMsg(msg);
      setPhase("error");
    }
  };

  // Step 2: import
  const handleImport = async () => {
    setPhase("importing");
    setImportStatus("importing");
    setErrorMsg("");
    setSuccessMsg("");
    try {
      const data = await githubApi.importRepo(project.id, repoUrl.trim());
      setImportRecord(data.import || null);
      setImportStatus(data.import_status || "completed");
      if (data.skipped) {
        setSuccessMsg(
          `Already indexed at commit ${data.import?.commit_sha || ""}. No changes detected.`
        );
        setPhase("done");
      } else {
        setSuccessMsg(
          `Imported ${data.file_count} files, ${data.chunk_count} code chunks indexed.`
        );
        setPhase("done");
      }
      onImportComplete?.();
    } catch (err) {
      const d = err.response?.data || {};
      const errStatus = d.import_status || "failed";
      setImportStatus(errStatus);
      setErrorMsg(d.error || err.message || "Import failed.");
      setPhase("error");
      if (d.import) setImportRecord(d.import);
    }
  };

  // Refresh (re-import same repo)
  const handleRefresh = async () => {
    setPhase("importing");
    setImportStatus("importing");
    setErrorMsg("");
    setSuccessMsg("");
    try {
      const data = await githubApi.refreshRepo(project.id);
      setImportRecord(data.import || null);
      setImportStatus("completed");
      setSuccessMsg(`Refreshed: ${data.file_count} files, ${data.chunk_count} chunks.`);
      setPhase("done");
      onImportComplete?.();
    } catch (err) {
      const d = err.response?.data || {};
      setImportStatus(d.import_status || "failed");
      setErrorMsg(d.error || err.message || "Refresh failed.");
      setPhase("error");
    }
  };

  const isLoading = ["validating", "importing"].includes(phase);

  return (
    <div className="gh-import-panel">
      <div className="gh-panel-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <GitBranch size={16} />
          <span>GitHub Repository Import</span>
          {importStatus && importStatus !== "pending" && (
            <StatusBadge status={importStatus} />
          )}
        </div>
        {onClose && (
          <button className="icon-btn" onClick={onClose} title="Close GitHub panel" aria-label="Close GitHub import panel">
            <X size={16} />
          </button>
        )}
      </div>

      <div className="gh-panel-body">
        {/* ── URL input ── */}
        <form onSubmit={handleValidate} id="gh-import-form">
          <label className="form-label" htmlFor="gh-repo-url-input">
            GitHub Repository URL
          </label>
          <div className="gh-url-row">
            <input
              id="gh-repo-url-input"
              type="text"
              className="form-input gh-url-input"
              placeholder="https://github.com/owner/repository"
              value={repoUrl}
              onChange={(e) => {
                setRepoUrl(e.target.value);
                if (phase !== "idle") reset();
              }}
              disabled={isLoading}
              autoComplete="url"
              aria-label="GitHub repository URL"
            />
            <button
              type="submit"
              className="btn btn-secondary btn-sm gh-validate-btn"
              disabled={isLoading || !repoUrl.trim()}
              aria-label="Validate repository"
            >
              {phase === "validating" ? (
                <Loader2 size={14} className="spin" />
              ) : (
                "Validate"
              )}
            </button>
          </div>
          <p className="gh-hint">
            Public repositories only. Downloads via GitHub REST API — no git CLI required.
            node_modules, .git, secrets, and binaries are excluded automatically.
          </p>
        </form>

        {/* ── Repository preview (after validation) ── */}
        {phase === "previewing" && repoMeta && (
          <div className="gh-preview-section" role="region" aria-label="Repository preview">
            <p className="gh-section-label">Repository confirmed</p>
            <RepoCard importData={repoMeta} />
            <button
              className="btn btn-primary"
              style={{ width: "100%", marginTop: 12 }}
              onClick={handleImport}
              id="gh-import-btn"
            >
              <Download size={15} />
              Import &amp; Index Repository
            </button>
          </div>
        )}

        {/* ── Loading indicator ── */}
        {isLoading && (
          <div className="gh-progress-block" role="status" aria-live="polite">
            <Loader2 size={20} className="spin" />
            <div>
              <p className="gh-progress-title">{fmtStatus(importStatus || "importing")}</p>
              <p className="gh-progress-sub">
                {importStatus === "importing"
                  ? "Downloading repository from GitHub API\u2026"
                  : importStatus === "indexing"
                  ? "Generating embeddings and building FAISS index\u2026"
                  : "Connecting to GitHub API\u2026"}
              </p>
            </div>
          </div>
        )}

        {/* ── Success ── */}
        {successMsg && (
          <div className="gh-alert gh-alert--success" role="status">
            <CheckCircle2 size={15} />
            <span>{successMsg}</span>
          </div>
        )}

        {/* ── Error ── */}
        {errorMsg && (
          <div className="gh-alert gh-alert--error" role="alert">
            <XCircle size={15} />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* ── Completed repo card ── */}
        {phase === "done" && importRecord && (
          <div className="gh-done-section">
            <RepoCard importData={importRecord} />
            <button
              className="btn btn-secondary"
              style={{ width: "100%", marginTop: 10 }}
              onClick={handleRefresh}
              disabled={isLoading}
              id="gh-refresh-btn"
              aria-label="Refresh repository"
            >
              <RefreshCw size={14} />
              Refresh / Re-import
            </button>
          </div>
        )}

        {/* ── Error-state refresh ── */}
        {phase === "error" && importRecord && (
          <div className="gh-done-section">
            <button
              className="btn btn-secondary"
              style={{ width: "100%", marginTop: 8 }}
              onClick={() => {
                reset();
                setRepoUrl(importRecord.repo_url || repoUrl);
              }}
              id="gh-retry-btn"
            >
              <RefreshCw size={14} />
              Try Again
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
