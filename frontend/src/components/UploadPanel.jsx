import React, { useState, useRef, useCallback } from 'react';
import {
  Upload,
  FileCode,
  CheckCircle2,
  XCircle,
  Loader2,
  FolderArchive,
  AlertCircle,
  X,
  RefreshCw,
  FileText,
} from 'lucide-react';
import { uploadZip, listFiles } from '../services/fileApi';

// Format bytes to human-readable
function fmtBytes(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function FileRow({ file }) {
  return (
    <div className="upload-file-row">
      <FileCode size={14} style={{ color: '#38bdf8', flexShrink: 0 }} />
      <span className="upload-file-path">{file.file_path}</span>
      <span className="upload-file-meta">
        {file.file_type || 'text'} · {fmtBytes(file.file_size)} · {file.line_count} lines
      </span>
    </div>
  );
}

export default function UploadPanel({ project, onUploadComplete, onClose }) {
  const [dragOver, setDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const inputRef = useRef(null);

  const MAX_SIZE_MB = 50;
  const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;

  // Validate file selection
  const validateFile = (file) => {
    if (!file.name.toLowerCase().endsWith('.zip')) {
      return 'Only .zip archives are supported.';
    }
    if (file.size > MAX_SIZE_BYTES) {
      return `File exceeds the ${MAX_SIZE_MB} MB limit (got ${fmtBytes(file.size)}).`;
    }
    return null;
  };

  const handleFileSelect = (file) => {
    setError('');
    setSuccess('');
    const validationError = validateFile(file);
    if (validationError) {
      setError(validationError);
      setSelectedFile(null);
      return;
    }
    setSelectedFile(file);
  };

  // Drag-and-drop handlers
  const onDragOver = useCallback((e) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const onDragLeave = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
  }, []);

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFileSelect(file);
  }, []);

  const loadFileList = async () => {
    if (!project?.id) return;
    setLoadingFiles(true);
    try {
      const res = await listFiles(project.id);
      setUploadedFiles(res.files || []);
    } catch {
      // Non-critical — don't block UI
    } finally {
      setLoadingFiles(false);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile || !project?.id) return;
    setError('');
    setSuccess('');
    setUploading(true);
    setUploadProgress(0);
    setStatusMessage('Uploading archive…');

    try {
      const result = await uploadZip(project.id, selectedFile, (evt) => {
        if (evt.total) {
          const pct = Math.round((evt.loaded / evt.total) * 100);
          setUploadProgress(pct);
          if (pct < 100) setStatusMessage(`Uploading… ${pct}%`);
          else setStatusMessage('Extracting and parsing files…');
        }
      });

      setUploadProgress(100);
      setSuccess(
        `Successfully processed ${result.file_count} files.`
      );
      setStatusMessage('');
      setSelectedFile(null);

      // Refresh file list
      await loadFileList();
      onUploadComplete?.();
    } catch (err) {
      const msg =
        err.response?.data?.error ||
        err.message ||
        'Upload failed. Please try again.';
      setError(msg);
      setStatusMessage('');
    } finally {
      setUploading(false);
    }
  };

  // Load existing files on first render
  React.useEffect(() => {
    loadFileList();
  }, [project?.id]);

  const hasFiles = uploadedFiles.length > 0;

  return (
    <div className="upload-panel">
      <div className="upload-panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <FolderArchive size={18} />
          <span>Upload Project Archive</span>
        </div>
        {onClose && (
          <button className="icon-btn" onClick={onClose} title="Close upload panel" aria-label="Close upload panel">
            <X size={16} />
          </button>
        )}
      </div>

      <div className="upload-panel-body">
        {/* ── Drop zone ── */}
        <div
          className={`upload-dropzone${dragOver ? ' dragover' : ''}${selectedFile ? ' selected' : ''}`}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          onClick={() => !uploading && inputRef.current?.click()}
          role="button"
          aria-label="Upload ZIP file area. Click or drag and drop."
          tabIndex={0}
          onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".zip"
            style={{ display: 'none' }}
            aria-label="Select ZIP file"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFileSelect(f);
              e.target.value = '';
            }}
            disabled={uploading}
          />

          {selectedFile ? (
            <>
              <CheckCircle2 size={32} style={{ color: 'var(--emerald)' }} aria-hidden="true" />
              <p className="dropzone-filename">{selectedFile.name}</p>
              <p className="dropzone-hint">{fmtBytes(selectedFile.size)} · ready to upload</p>
              {!uploading && (
                <button
                  className="dropzone-clear"
                  onClick={(e) => { e.stopPropagation(); setSelectedFile(null); setError(''); }}
                  aria-label="Remove selected file"
                >
                  <X size={14} /> Remove
                </button>
              )}
            </>
          ) : (
            <>
              <Upload size={32} style={{ color: 'var(--accent-primary)', opacity: 0.7 }} aria-hidden="true" />
              <p className="dropzone-title">Drop .zip archive here</p>
              <p className="dropzone-hint">or click to browse · max {MAX_SIZE_MB} MB</p>
              <p className="dropzone-hint" style={{ marginTop: 4, fontSize: 11 }}>
                node_modules, .git, venv, secrets, and binaries are excluded automatically
              </p>
            </>
          )}
        </div>

        {/* ── Progress bar ── */}
        {uploading && (
          <div className="upload-progress-wrap" role="status" aria-label={statusMessage}>
            <div className="upload-progress-bar-track">
              <div
                className="upload-progress-bar-fill"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
            <div className="upload-progress-label">
              <Loader2 size={13} className="spin" aria-hidden="true" />
              <span>{statusMessage}</span>
              <span>{uploadProgress}%</span>
            </div>
          </div>
        )}

        {/* ── Error ── */}
        {error && (
          <div className="upload-alert upload-alert--error" role="alert">
            <XCircle size={15} aria-hidden="true" />
            <span>{error}</span>
          </div>
        )}

        {/* ── Success ── */}
        {success && (
          <div className="upload-alert upload-alert--success" role="status">
            <CheckCircle2 size={15} aria-hidden="true" />
            <span>{success}</span>
          </div>
        )}

        {/* ── Upload button ── */}
        <button
          className="btn btn-primary"
          style={{ width: '100%' }}
          onClick={handleUpload}
          disabled={!selectedFile || uploading}
          aria-busy={uploading}
        >
          {uploading ? (
            <><Loader2 size={15} className="spin" aria-hidden="true" /> Processing…</>
          ) : (
            <><Upload size={15} aria-hidden="true" /> Upload &amp; Process Archive</>
          )}
        </button>

        {/* ── File list ── */}
        <div className="upload-file-list-header">
          <span>
            {hasFiles
              ? `${uploadedFiles.length} files indexed`
              : 'No files uploaded yet'}
          </span>
          <button
            className="icon-btn"
            onClick={loadFileList}
            disabled={loadingFiles}
            title="Refresh file list"
            aria-label="Refresh file list"
          >
            <RefreshCw size={13} className={loadingFiles ? 'spin' : ''} />
          </button>
        </div>

        {loadingFiles ? (
          <div className="upload-file-loading" role="status">
            <Loader2 size={18} className="spin" aria-hidden="true" />
            <span>Loading files…</span>
          </div>
        ) : !hasFiles ? (
          <div className="upload-empty-files" role="status">
            <FileText size={28} style={{ opacity: 0.25 }} aria-hidden="true" />
            <p>Upload a .zip archive to index your project files.</p>
          </div>
        ) : (
          <div className="upload-file-list" role="list" aria-label="Indexed project files">
            {uploadedFiles.map((f) => (
              <FileRow key={f.id} file={f} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
