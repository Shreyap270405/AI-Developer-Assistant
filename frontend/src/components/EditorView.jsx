import React, { useRef, useEffect, useState } from 'react';
import Editor from '@monaco-editor/react';
import { Save, FileCode, Check, Loader2, Info } from 'lucide-react';

// Derives Monaco language identifier from a file path / extension
function getMonacoLanguage(lang) {
  const map = {
    python: 'python',
    javascript: 'javascript',
    typescript: 'typescript',
    jsx: 'javascript',
    tsx: 'typescript',
    java: 'java',
    cpp: 'cpp',
    c: 'c',
    go: 'go',
    rust: 'rust',
    ruby: 'ruby',
    php: 'php',
    html: 'html',
    css: 'css',
    scss: 'scss',
    json: 'json',
    yaml: 'yaml',
    markdown: 'markdown',
    md: 'markdown',
    sh: 'shell',
    bash: 'shell',
    sql: 'sql',
    plaintext: 'plaintext',
  };
  if (!lang) return 'plaintext';
  return map[lang.toLowerCase()] || lang.toLowerCase() || 'plaintext';
}

// Friendly display label for language
function languageLabel(lang) {
  if (!lang || lang === 'plaintext') return 'Plain Text';
  return lang.charAt(0).toUpperCase() + lang.slice(1);
}

// ─── Empty state shown when no file is selected ───────────────────────────────
function EditorEmptyState() {
  return (
    <div className="editor-empty" role="status" aria-label="No file selected">
      <FileCode size={52} strokeWidth={1.2} aria-hidden="true" />
      <p className="editor-empty-title">Select a file to view it</p>
      <p className="editor-empty-hint">
        Click any file in the explorer, or click a citation in the AI chat to jump to its source line.
      </p>
    </div>
  );
}

// ─── Main EditorView component ────────────────────────────────────────────────
export default function EditorView({
  filePath,
  content,
  language,
  onSave,
  highlightRange,
  isSaving,
  readOnly = false,
}) {
  const editorRef = useRef(null);
  const decorationsRef = useRef([]);
  const [editorContent, setEditorContent] = useState(content || '');
  const [hasChanges, setHasChanges] = useState(false);
  const [isMounted, setIsMounted] = useState(false);

  // Sync content prop → local state on file switch
  useEffect(() => {
    setEditorContent(content || '');
    setHasChanges(false);
  }, [content, filePath]);

  const monacoLang = getMonacoLanguage(language);

  const handleEditorDidMount = (editor, monaco) => {
    editorRef.current = editor;
    setIsMounted(true);

    // Ctrl+S / Cmd+S → save
    if (!readOnly) {
      editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
        if (filePath) {
          onSave(editor.getValue());
          setHasChanges(false);
        }
      });
    }
  };

  // Citation range highlighting
  useEffect(() => {
    if (!editorRef.current || !highlightRange) return;
    const { start_line, end_line } = highlightRange;
    if (!start_line) return;

    const editor = editorRef.current;
    editor.revealLineInCenter(start_line);

    const newDecorations = [{
      range: {
        startLineNumber: start_line,
        startColumn: 1,
        endLineNumber: end_line || start_line,
        endColumn: 1,
      },
      options: {
        isWholeLine: true,
        className: 'monaco-citation-highlight',
        linesDecorationsClassName: 'monaco-citation-gutter',
      },
    }];
    decorationsRef.current = editor.deltaDecorations(decorationsRef.current, newDecorations);

    const timer = setTimeout(() => {
      editorRef.current?.deltaDecorations(decorationsRef.current, []);
    }, 6000);
    return () => clearTimeout(timer);
  }, [highlightRange]);

  if (!filePath) {
    return (
      <main className="editor-panel" aria-label="Code editor">
        <EditorEmptyState />
      </main>
    );
  }

  const fileName = filePath.split('/').pop();
  const lineCount = (editorContent || '').split('\n').length;

  return (
    <main className="editor-panel" aria-label={`Editing ${fileName}`}>
      {/* Toolbar */}
      <div className="editor-toolbar" role="toolbar" aria-label="Editor toolbar">
        {/* File tab */}
        <div className="editor-tabs">
          <div className="editor-tab active" title={filePath}>
            <FileCode size={13} style={{ color: '#38bdf8' }} aria-hidden="true" />
            <span className="tab-name">{fileName}</span>
            {hasChanges && (
              <span className="tab-dirty" title="Unsaved changes" aria-label="Unsaved changes" />
            )}
          </div>
        </div>

        {/* Right-side info + save */}
        <div className="editor-toolbar-right">
          {highlightRange && (
            <span className="editor-badge editor-badge--info" role="status">
              <Info size={11} aria-hidden="true" />
              Lines {highlightRange.start_line}–{highlightRange.end_line}
            </span>
          )}
          {readOnly && (
            <span className="editor-badge" role="status">Read-only</span>
          )}
          <span className="editor-stat">{languageLabel(language)}</span>
          <span className="editor-stat">{lineCount} lines</span>
          {!readOnly && (
            <button
              className="btn btn-primary btn-sm"
              onClick={() => {
                onSave(editorContent);
                setHasChanges(false);
              }}
              disabled={isSaving || !hasChanges}
              title="Save file (Ctrl+S)"
              aria-label="Save file"
            >
              {isSaving
                ? <><Loader2 size={13} className="spin" aria-hidden="true" /> Saving…</>
                : hasChanges
                  ? <><Save size={13} aria-hidden="true" /> Save</>
                  : <><Check size={13} aria-hidden="true" /> Saved</>
              }
            </button>
          )}
        </div>
      </div>

      {/* Monaco Editor */}
      <div className="monaco-wrapper">
        <Editor
          height="100%"
          language={monacoLang}
          value={editorContent}
          theme="vs-dark"
          onChange={readOnly ? undefined : (val) => {
            setEditorContent(val || '');
            setHasChanges(true);
          }}
          onMount={handleEditorDidMount}
          loading={
            <div className="editor-loading" aria-label="Loading editor">
              <Loader2 size={24} className="spin" />
              <span>Loading editor…</span>
            </div>
          }
          options={{
            readOnly,
            fontSize: 13,
            fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
            fontLigatures: true,
            minimap: { enabled: true, maxColumn: 80 },
            scrollBeyondLastLine: false,
            automaticLayout: true,
            tabSize: 2,
            wordWrap: 'on',
            lineNumbers: 'on',
            renderWhitespace: 'selection',
            smoothScrolling: true,
            cursorBlinking: 'smooth',
            bracketPairColorization: { enabled: true },
            guides: { bracketPairs: true },
            padding: { top: 12, bottom: 12 },
            scrollbar: { verticalScrollbarSize: 6, horizontalScrollbarSize: 6 },
          }}
        />
      </div>

      <style>{`
        .monaco-citation-highlight {
          background: rgba(56, 189, 248, 0.15) !important;
          border-left: 3px solid #38bdf8 !important;
        }
        .monaco-citation-gutter {
          background: #38bdf8 !important;
          width: 4px !important;
        }
      `}</style>
    </main>
  );
}
