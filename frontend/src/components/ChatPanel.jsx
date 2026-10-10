import React, { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  Send,
  Sparkles,
  Search,
  MessageSquare,
  FileCode,
  ExternalLink,
  Copy,
  Check,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Wand2,
  Bug,
  Lightbulb,
  ArrowRight,
  RefreshCw,
  Zap,
  ShieldAlert,
  ChevronDown,
  Plus,
  Trash2,
  Edit2,
  History,
  RotateCcw,
  FlaskConical,
  FileText,
} from 'lucide-react';
import { ragApi } from '../services/ragApi';
import { aiApi } from '../services/aiApi';
import SemanticSearchTab from './SemanticSearchTab';
import CodeReviewTab from './CodeReviewTab';
import TestGeneratorTab from './TestGeneratorTab';
import ReadmeGeneratorTab from './ReadmeGeneratorTab';

const LANGUAGES = [
  { value: 'javascript', label: 'JavaScript' },
  { value: 'typescript', label: 'TypeScript' },
  { value: 'python', label: 'Python' },
  { value: 'sql', label: 'SQL' },
  { value: 'html', label: 'HTML / JSX' },
  { value: 'css', label: 'CSS' },
  { value: 'go', label: 'Go' },
  { value: 'rust', label: 'Rust' },
  { value: 'java', label: 'Java' },
  { value: 'cpp', label: 'C++' },
  { value: 'bash', label: 'Shell / Bash' },
  { value: 'json', label: 'JSON' },
];

const IMPROVE_FOCUS_OPTIONS = [
  { value: 'all', label: '⭐ All Improvements (Quality, Speed, Security)' },
  { value: 'performance', label: '⚡ Performance & Computational Efficiency' },
  { value: 'readability', label: '📖 Clean Code, Modularity & Readability' },
  { value: 'security', label: '🛡️ Security Hardening & Input Validation' },
];

const STARTER_PROMPTS = [
  {
    icon: '🏗️',
    title: 'Architecture Overview',
    prompt: 'Explain the overall architecture, core modules, and entry point of this project.',
  },
  {
    icon: '🔐',
    title: 'Authentication & Security',
    prompt: 'How is user authentication, token verification, and data protection implemented in this codebase?',
  },
  {
    icon: '🗄️',
    title: 'Data & Database Schema',
    prompt: 'Where are database models, connection pools, and migration queries defined?',
  },
  {
    icon: '🧪',
    title: 'Testing & Error Handling',
    prompt: 'What testing frameworks are used, and how are errors and edge cases handled across services?',
  },
];

export default function ChatPanel({
  project,
  activeFile,
  activeCodeSnippet,
  onJumpToCitation,
  showToast,
  onRefreshFileTree,
}) {
  // Main view tabs: 'chat' | 'search' | 'review' | 'tests' | 'docs' | 'operations'
  const [activeTab, setActiveTab] = useState('chat');

  // Gemini service configuration state
  const [geminiStatus, setGeminiStatus] = useState({
    checked: false,
    configured: false,
    model: 'gemini-2.5-flash',
  });

  // Conversations State
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [isLoadingConversations, setIsLoadingConversations] = useState(false);
  const [showConvDropdown, setShowConvDropdown] = useState(false);

  // Conversational Chat State
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [lastErrorPrompt, setLastErrorPrompt] = useState(null);

  // AI Operations Tab State
  const [selectedOp, setSelectedOp] = useState('explain'); // 'explain' | 'debug' | 'generate' | 'improve'
  const [opCode, setOpCode] = useState('');
  const [opPrompt, setOpPrompt] = useState('');
  const [opErrorMessage, setOpErrorMessage] = useState('');
  const [opLanguage, setOpLanguage] = useState('python');
  const [opImproveFocus, setOpImproveFocus] = useState('all');
  const [opContext, setOpContext] = useState('');
  const [opLoading, setOpLoading] = useState(false);
  const [opResult, setOpResult] = useState(null);
  const [opError, setOpError] = useState(null);
  const [copiedSection, setCopiedSection] = useState(null);

  // Search tab state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);

  const messagesEndRef = useRef(null);

  // Fetch Gemini configuration status on mount
  useEffect(() => {
    let mounted = true;
    aiApi
      .getStatus()
      .then((data) => {
        if (mounted) {
          setGeminiStatus({
            checked: true,
            configured: Boolean(data.configured),
            model: data.model || 'gemini-2.5-flash',
          });
        }
      })
      .catch(() => {
        if (mounted) {
          setGeminiStatus({
            checked: true,
            configured: false,
            model: 'gemini-2.5-flash',
          });
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  // Fetch conversations for the active project
  const loadConversations = useCallback(
    async (projId, autoSelectFirst = false) => {
      if (!projId) {
        setConversations([]);
        return;
      }
      setIsLoadingConversations(true);
      try {
        const data = await ragApi.listConversations(projId);
        const list = data.conversations || [];
        setConversations(list);
        if (autoSelectFirst && list.length > 0) {
          loadConversationHistory(projId, list[0].id);
        }
      } catch (err) {
        console.warn('Failed to load conversations:', err);
      } finally {
        setIsLoadingConversations(false);
      }
    },
    []
  );

  // Load specific conversation history
  const loadConversationHistory = async (projId, convId) => {
    if (!projId || !convId) return;
    setIsLoading(true);
    try {
      const data = await ragApi.getConversation(projId, convId);
      setActiveConversationId(convId);
      setMessages(data.messages || []);
      setShowConvDropdown(false);
    } catch (err) {
      showToast?.('Failed to load conversation history: ' + err.message, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  // Switch project -> reset conversation state & reload
  useEffect(() => {
    if (project?.id) {
      loadConversations(project.id, true);
    } else {
      setConversations([]);
      setActiveConversationId(null);
      setMessages([]);
    }
  }, [project?.id, loadConversations]);

  // Update default language based on active file extension
  useEffect(() => {
    if (activeFile) {
      const ext = activeFile.split('.').pop()?.toLowerCase();
      const extMap = {
        py: 'python',
        js: 'javascript',
        jsx: 'javascript',
        ts: 'typescript',
        tsx: 'typescript',
        go: 'go',
        rs: 'rust',
        java: 'java',
        cpp: 'cpp',
        c: 'cpp',
        sql: 'sql',
        html: 'html',
        css: 'css',
        sh: 'bash',
      };
      if (ext && extMap[ext]) {
        setOpLanguage(extMap[ext]);
      }
    }
  }, [activeFile]);

  // Auto-scroll chat messages
  useEffect(() => {
    if (activeTab === 'chat') {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isLoading, activeTab]);

  // Copy helper with visual checkmark timeout
  const copyToClipboard = async (text, sectionKey = 'code') => {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopiedSection(sectionKey);
      showToast?.('Copied to clipboard!', 'success');
      setTimeout(() => setCopiedSection(null), 2200);
    } catch (err) {
      showToast?.('Failed to copy: ' + err.message, 'error');
    }
  };

  // Create a brand new conversation thread
  const handleStartNewConversation = () => {
    setActiveConversationId(null);
    setMessages([]);
    setLastErrorPrompt(null);
    setShowConvDropdown(false);
    showToast?.('Started new conversation thread', 'info');
  };

  // Rename current conversation
  const handleRenameConversation = async (convId) => {
    const current = conversations.find((c) => c.id === convId);
    const newTitle = window.prompt('Enter new conversation title:', current?.title || '');
    if (!newTitle || !newTitle.trim() || newTitle === current?.title) return;

    try {
      await ragApi.renameConversation(project.id, convId, newTitle.trim());
      setConversations((prev) =>
        prev.map((c) => (c.id === convId ? { ...c, title: newTitle.trim() } : c))
      );
      showToast?.('Conversation renamed', 'success');
    } catch (err) {
      showToast?.('Failed to rename: ' + err.message, 'error');
    }
  };

  // Delete current conversation
  const handleDeleteConversation = async (convId, e) => {
    if (e) e.stopPropagation();
    if (!window.confirm('Delete this conversation thread and its message history?')) return;

    try {
      await ragApi.deleteConversation(project.id, convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (activeConversationId === convId) {
        handleStartNewConversation();
      }
      showToast?.('Conversation deleted', 'success');
    } catch (err) {
      showToast?.('Failed to delete: ' + err.message, 'error');
    }
  };

  // Populate code input from active editor file
  const handleLoadFromActiveFile = () => {
    if (activeCodeSnippet) {
      setOpCode(activeCodeSnippet);
      showToast?.(`Loaded ${activeFile || 'active file'} into snippet editor`, 'info');
    } else {
      showToast?.('No active file content available in editor', 'warning');
    }
  };

  // Execute Gemini AI Operation
  const handleExecuteOperation = async (e) => {
    if (e) e.preventDefault();
    setOpLoading(true);
    setOpError(null);
    setOpResult(null);

    try {
      let data = null;
      if (selectedOp === 'explain') {
        if (!opCode.trim()) throw new Error('Please enter or load a code snippet to explain.');
        data = await aiApi.explainCode({
          code: opCode,
          language: opLanguage,
          filePath: activeFile || '',
          context: opContext,
        });
      } else if (selectedOp === 'debug') {
        if (!opCode.trim()) throw new Error('Please enter or load a code snippet to debug.');
        data = await aiApi.debugCode({
          code: opCode,
          errorMessage: opErrorMessage,
          language: opLanguage,
          filePath: activeFile || '',
          context: opContext,
        });
      } else if (selectedOp === 'generate') {
        if (!opPrompt.trim()) throw new Error('Please provide instructions/specifications for code generation.');
        data = await aiApi.generateCode({
          prompt: opPrompt,
          language: opLanguage,
          context: opContext,
        });
      } else if (selectedOp === 'improve') {
        if (!opCode.trim()) throw new Error('Please enter or load a code snippet to improve.');
        data = await aiApi.improveCode({
          code: opCode,
          focus: opImproveFocus,
          language: opLanguage,
          filePath: activeFile || '',
          context: opContext,
        });
      }

      setOpResult(data);
      showToast?.(`Operation '${selectedOp}' completed successfully!`, 'success');
    } catch (err) {
      const errMsg =
        err.response?.data?.error ||
        err.message ||
        'An error occurred while executing the AI operation.';
      setOpError(errMsg);
      showToast?.(errMsg, 'error');
    } finally {
      setOpLoading(false);
    }
  };

  // Conversational RAG Chat Handler
  const handleSendMessage = async (customPrompt = null) => {
    const text = (customPrompt || inputText).trim();
    if (!text || !project) return;

    if (!customPrompt) setInputText('');
    setLastErrorPrompt(null);

    const userMsg = { id: Date.now(), role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const data = await ragApi.askQuestion(project.id, text, activeConversationId);
      const assistantMsg = {
        id: data.message_id || Date.now() + 1,
        role: 'assistant',
        content: data.answer,
        citations: data.citations || [],
        metadata: {
          model: data.model,
          retrieved_chunks_count: data.retrieved_chunks_count,
        },
      };
      setMessages((prev) => [...prev, assistantMsg]);

      // If a new conversation was created on the backend, update state and list
      if (data.conversation_id && data.conversation_id !== activeConversationId) {
        setActiveConversationId(data.conversation_id);
        loadConversations(project.id, false);
      }
    } catch (err) {
      const errMsg = err.response?.data?.error || err.message || 'Failed to query codebase';
      setLastErrorPrompt(text);
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: 'assistant',
          content: `❌ **Error querying codebase**: ${errMsg}\n\nPlease verify that your project is indexed and that your Gemini API key is configured.`,
          citations: [],
          isError: true,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  // Search Handler
  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim() || !project) return;

    setIsSearching(true);
    try {
      const data = await ragApi.searchCodebase(project.id, searchQuery.trim());
      setSearchResults(data.results || []);
    } catch (err) {
      showToast?.('Search error: ' + err.message, 'error');
    } finally {
      setIsSearching(false);
    }
  };

  const activeConvObj = conversations.find((c) => c.id === activeConversationId);

  return (
    <aside className="chat-panel" aria-label="AI Assistant Panel">
      {/* ── Main Tab Navigation Bar ── */}
      <div className="chat-tabs" role="tablist">
        <button
          className={`chat-tab ${activeTab === 'chat' ? 'active' : ''}`}
          onClick={() => setActiveTab('chat')}
          role="tab"
          aria-selected={activeTab === 'chat'}
          id="tab-chat"
          title="Grounded codebase discussion and Q&A"
        >
          <MessageSquare size={13} /> Chat
        </button>
        <button
          className={`chat-tab ${activeTab === 'search' ? 'active' : ''}`}
          onClick={() => setActiveTab('search')}
          role="tab"
          aria-selected={activeTab === 'search'}
          id="tab-search"
          title="Semantic vector codebase search"
        >
          <Search size={13} /> Search
        </button>
        <button
          className={`chat-tab ${activeTab === 'review' ? 'active' : ''}`}
          onClick={() => setActiveTab('review')}
          role="tab"
          aria-selected={activeTab === 'review'}
          id="tab-review"
          title="AI Code Review with grounded findings"
        >
          <ShieldAlert size={13} /> Review
        </button>
        <button
          className={`chat-tab ${activeTab === 'tests' ? 'active' : ''}`}
          onClick={() => setActiveTab('tests')}
          role="tab"
          aria-selected={activeTab === 'tests'}
          id="tab-tests"
          title="Unit and edge-case test generator"
        >
          <FlaskConical size={13} /> Tests
        </button>
        <button
          className={`chat-tab ${activeTab === 'docs' ? 'active' : ''}`}
          onClick={() => setActiveTab('docs')}
          role="tab"
          aria-selected={activeTab === 'docs'}
          id="tab-docs"
          title="README and documentation generator"
        >
          <FileText size={13} /> Docs
        </button>
        <button
          className={`chat-tab ${activeTab === 'operations' ? 'active' : ''}`}
          onClick={() => setActiveTab('operations')}
          role="tab"
          aria-selected={activeTab === 'operations'}
          id="tab-operations"
          title="Explain, debug, generate, or improve code"
        >
          <Zap size={13} /> AI Ops
        </button>
      </div>

      {/* ── Configuration Status Notice Banner ── */}
      {geminiStatus.checked && !geminiStatus.configured && (
        <div className="gemini-config-warning">
          <AlertTriangle size={15} style={{ flexShrink: 0, color: 'var(--amber)' }} />
          <div style={{ flex: 1, fontSize: '11.5px', lineHeight: 1.4 }}>
            <strong>Gemini API Key Missing</strong>
            <div>
              Set <code>GEMINI_API_KEY</code> in <code>backend/.env</code> to enable live AI operations.
            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          TAB 1: CONVERSATIONAL RAG CHAT & GROUNDED Q&A
          ───────────────────────────────────────────────────────────── */}
      {activeTab === 'chat' && (
        <div className="rag-chat-container">
          {/* Conversation Selector Toolbar */}
          <div className="conv-toolbar">
            <div className="conv-selector-wrapper">
              <button
                type="button"
                className="conv-selector-btn"
                onClick={() => setShowConvDropdown((v) => !v)}
                title="Select conversation thread"
              >
                <History size={13} />
                <span className="conv-title-text">
                  {activeConvObj ? activeConvObj.title : 'New Conversation'}
                </span>
                <ChevronDown size={12} style={{ opacity: 0.7 }} />
              </button>

              {showConvDropdown && (
                <div className="conv-dropdown-menu">
                  <div className="conv-dropdown-header">
                    <span>Saved Conversations ({conversations.length})</span>
                    <button
                      type="button"
                      className="btn-link-xs"
                      onClick={handleStartNewConversation}
                    >
                      + New Thread
                    </button>
                  </div>
                  <div className="conv-dropdown-list">
                    {conversations.length === 0 ? (
                      <div className="conv-dropdown-empty">No saved threads yet</div>
                    ) : (
                      conversations.map((c) => (
                        <div
                          key={c.id}
                          className={`conv-item ${c.id === activeConversationId ? 'active' : ''}`}
                          onClick={() => loadConversationHistory(project.id, c.id)}
                        >
                          <MessageSquare size={12} className="conv-item-icon" />
                          <span className="conv-item-title" title={c.title}>
                            {c.title}
                          </span>
                          <div className="conv-item-actions">
                            <button
                              type="button"
                              className="conv-action-btn"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleRenameConversation(c.id);
                              }}
                              title="Rename"
                            >
                              <Edit2 size={11} />
                            </button>
                            <button
                              type="button"
                              className="conv-action-btn delete"
                              onClick={(e) => handleDeleteConversation(c.id, e)}
                              title="Delete"
                            >
                              <Trash2 size={11} />
                            </button>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>

            <button
              type="button"
              className="btn btn-ghost btn-xs new-chat-btn"
              onClick={handleStartNewConversation}
              title="Start a new conversation thread"
            >
              <Plus size={13} />
              <span>New Chat</span>
            </button>
          </div>

          {/* Messages Scroll Area */}
          <div className="chat-messages">
            {messages.length === 0 ? (
              <div className="chat-empty-state">
                <div className="empty-state-icon-wrapper">
                  <Sparkles size={32} className="empty-state-sparkle" />
                </div>
                <h3 className="empty-state-title">Project Codebase Assistant</h3>
                <p className="empty-state-subtitle">
                  Ask questions grounded directly in your uploaded source code. Every answer includes verifiable file and line citations.
                </p>

                <div className="starter-prompts-grid">
                  {STARTER_PROMPTS.map((item, idx) => (
                    <button
                      key={idx}
                      className="starter-card"
                      onClick={() => handleSendMessage(item.prompt)}
                      disabled={isLoading || !project}
                    >
                      <div className="starter-card-header">
                        <span className="starter-card-icon">{item.icon}</span>
                        <span className="starter-card-title">{item.title}</span>
                      </div>
                      <p className="starter-card-prompt">{item.prompt}</p>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg, mIdx) => (
                <div
                  key={msg.id || mIdx}
                  className={`message-bubble ${
                    msg.role === 'user' ? 'message-user' : 'message-assistant'
                  } ${msg.isError ? 'message-error' : ''}`}
                >
                  <div className="message-header">
                    {msg.role === 'user' ? (
                      <span>You</span>
                    ) : (
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                        <span style={{ display: 'flex', alignItems: 'center', gap: '5px', color: 'var(--text-accent)' }}>
                          <Sparkles size={13} /> AI Assistant
                        </span>
                        <button
                          type="button"
                          className="btn-link-xs"
                          onClick={() => copyToClipboard(msg.content, `msg-${msg.id || mIdx}`)}
                          title="Copy message"
                        >
                          {copiedSection === `msg-${msg.id || mIdx}` ? (
                            <><Check size={11} /> Copied</>
                          ) : (
                            <><Copy size={11} /> Copy</>
                          )}
                        </button>
                      </div>
                    )}
                  </div>

                  <div className="message-body">
                    <ReactMarkdown
                      components={{
                        a: ({ node, ...props }) => (
                          <a {...props} target="_blank" rel="noopener noreferrer" />
                        ),
                        code({ node, inline, className, children, ...props }) {
                          const match = /language-(\w+)/.exec(className || '');
                          const codeString = String(children).replace(/\n$/, '');
                          if (!inline && (match || codeString.includes('\n'))) {
                            const lang = match ? match[1] : '';
                            return (
                              <div className="chat-code-block">
                                <div className="chat-code-header">
                                  <span className="chat-code-lang">{lang || 'code'}</span>
                                  <button
                                    type="button"
                                    className="chat-code-copy-btn"
                                    onClick={() => copyToClipboard(codeString, `code-${codeString.slice(0, 10)}`)}
                                    title="Copy code snippet"
                                  >
                                    <Copy size={12} />
                                    <span>Copy</span>
                                  </button>
                                </div>
                                <pre className="chat-code-pre">
                                  <code>{codeString}</code>
                                </pre>
                              </div>
                            );
                          }
                          return (
                            <code className="chat-inline-code" {...props}>
                              {children}
                            </code>
                          );
                        },
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>

                    {/* Traceable Source Citations */}
                    {msg.citations && msg.citations.length > 0 && (
                      <div className="citation-container">
                        <div className="citation-label">
                          <FileCode size={13} />
                          <span>Verified Source References ({msg.citations.length}):</span>
                        </div>
                        <div className="citation-cards-grid">
                          {msg.citations.map((c, i) => (
                            <div
                              key={i}
                              className="citation-card"
                              onClick={() => onJumpToCitation(c.file_path, c.start_line, c.end_line)}
                              title={`Click to open ${c.file_path} at lines ${c.start_line}–${c.end_line} in editor`}
                            >
                              <div className="citation-card-header">
                                <div className="citation-path-group">
                                  <FileCode size={12} style={{ color: '#38bdf8' }} />
                                  <span className="citation-path">{c.file_path}</span>
                                </div>
                                <span className="citation-lines">
                                  Lines {c.start_line}–{c.end_line}
                                </span>
                                <ExternalLink size={11} className="citation-jump-icon" />
                              </div>
                              {c.snippet && (
                                <div className="citation-snippet-preview">
                                  <code>{c.snippet.trim()}</code>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}

            {/* Loading Indicator */}
            {isLoading && (
              <div className="message-bubble message-assistant">
                <div className="message-header" style={{ color: 'var(--text-accent)' }}>
                  <Sparkles size={13} className="pulse-icon" /> Retrieving codebase context &amp; analyzing with Gemini...
                </div>
                <div className="loading-shimmer-box" style={{ marginTop: '8px' }}>
                  <div className="loading-shimmer-line" style={{ width: '80%' }} />
                  <div className="loading-shimmer-line" style={{ width: '92%' }} />
                  <div className="loading-shimmer-line" style={{ width: '65%' }} />
                </div>
              </div>
            )}

            {lastErrorPrompt && !isLoading && (
              <div className="chat-retry-bar">
                <button
                  type="button"
                  className="btn btn-secondary btn-xs"
                  onClick={() => handleSendMessage(lastErrorPrompt)}
                >
                  <RotateCcw size={12} /> Retry Last Question
                </button>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Quick Suggestions & Input */}
          <div className="chat-input-container">
            <div className="prompt-suggestions">
              <button
                className="suggestion-chip"
                onClick={() => {
                  setSelectedOp('explain');
                  setActiveTab('operations');
                  if (activeCodeSnippet) setOpCode(activeCodeSnippet);
                }}
              >
                💡 Explain Snippet
              </button>
              <button
                className="suggestion-chip"
                onClick={() => {
                  setSelectedOp('debug');
                  setActiveTab('operations');
                  if (activeCodeSnippet) setOpCode(activeCodeSnippet);
                }}
              >
                🐞 Debug Snippet
              </button>
              <button
                className="suggestion-chip"
                onClick={() => {
                  setSelectedOp('generate');
                  setActiveTab('operations');
                }}
              >
                ⚡ Generate Code
              </button>
              <button
                className="suggestion-chip"
                onClick={() => {
                  setSelectedOp('improve');
                  setActiveTab('operations');
                  if (activeCodeSnippet) setOpCode(activeCodeSnippet);
                }}
              >
                🚀 Improve Code
              </button>
            </div>

            <form
              className="input-box-wrapper"
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage();
              }}
            >
              <textarea
                className="chat-input"
                placeholder={
                  project
                    ? 'Ask questions about this codebase...'
                    : 'Create or select a project first...'
                }
                value={inputText}
                disabled={!project || isLoading}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSendMessage();
                  }
                }}
              />
              <button
                type="submit"
                className="btn btn-primary"
                disabled={!inputText.trim() || !project || isLoading}
                style={{ padding: '0 16px', height: '44px', alignSelf: 'flex-end' }}
                title="Send message (Enter)"
              >
                <Send size={16} />
              </button>
            </form>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────
          TAB 2: AI DEVELOPER OPERATIONS (Explain, Debug, Generate, Improve)
          ───────────────────────────────────────────────────────────── */}
      {activeTab === 'operations' && (
        <div className="ai-ops-container">
          {/* Operation Selector Pills */}
          <div className="ai-ops-selector">
            <button
              className={`op-pill ${selectedOp === 'explain' ? 'active' : ''}`}
              onClick={() => {
                setSelectedOp('explain');
                setOpResult(null);
                setOpError(null);
              }}
              title="Explain Code: Purpose, Flow, and Edge Cases"
            >
              <Lightbulb size={13} />
              <span>Explain</span>
            </button>
            <button
              className={`op-pill ${selectedOp === 'debug' ? 'active' : ''}`}
              onClick={() => {
                setSelectedOp('debug');
                setOpResult(null);
                setOpError(null);
              }}
              title="Debug Code: Root Cause and Fix"
            >
              <Bug size={13} />
              <span>Debug</span>
            </button>
            <button
              className={`op-pill ${selectedOp === 'generate' ? 'active' : ''}`}
              onClick={() => {
                setSelectedOp('generate');
                setOpResult(null);
                setOpError(null);
              }}
              title="Generate Code: Create from Natural Language"
            >
              <Wand2 size={13} />
              <span>Generate</span>
            </button>
            <button
              className={`op-pill ${selectedOp === 'improve' ? 'active' : ''}`}
              onClick={() => {
                setSelectedOp('improve');
                setOpResult(null);
                setOpError(null);
              }}
              title="Improve Code: Refactor, Optimize, Harden"
            >
              <Sparkles size={13} />
              <span>Improve</span>
            </button>
          </div>

          <div className="ai-ops-scroll-area">
            {/* Active Operation Form */}
            <form onSubmit={handleExecuteOperation} className="ai-ops-form">
              <div className="ai-ops-form-header">
                <div className="op-title-row">
                  <span className="op-title">
                    {selectedOp === 'explain' && '💡 Explain Code Snippet'}
                    {selectedOp === 'debug' && '🐞 Debug & Fix Code'}
                    {selectedOp === 'generate' && '⚡ Generate New Code'}
                    {selectedOp === 'improve' && '🚀 Refactor & Optimize Code'}
                  </span>
                  <span className="op-model-tag" title={`Configured Model: ${geminiStatus.model}`}>
                    {geminiStatus.model}
                  </span>
                </div>
                <p className="op-desc">
                  {selectedOp === 'explain' &&
                    'Get architectural flow, key algorithms, inputs, outputs, and edge cases.'}
                  {selectedOp === 'debug' &&
                    'Diagnose runtime errors, race conditions, or unhandled exceptions and get corrected code.'}
                  {selectedOp === 'generate' &&
                    'Describe features or functions in plain English to generate production-ready code.'}
                  {selectedOp === 'improve' &&
                    'Apply modern clean-code principles, performance optimizations, and security mitigations.'}
                </p>
              </div>

              {/* Language Selector + Helper buttons */}
              <div className="ai-ops-row">
                <div className="form-group" style={{ flex: 1 }}>
                  <label className="form-label-sm">Language</label>
                  <select
                    className="form-select-sm"
                    value={opLanguage}
                    onChange={(e) => setOpLanguage(e.target.value)}
                  >
                    {LANGUAGES.map((lang) => (
                      <option key={lang.value} value={lang.value}>
                        {lang.label}
                      </option>
                    ))}
                  </select>
                </div>

                {selectedOp === 'improve' && (
                  <div className="form-group" style={{ flex: 1.5 }}>
                    <label className="form-label-sm">Optimization Focus</label>
                    <select
                      className="form-select-sm"
                      value={opImproveFocus}
                      onChange={(e) => setOpImproveFocus(e.target.value)}
                    >
                      {IMPROVE_FOCUS_OPTIONS.map((f) => (
                        <option key={f.value} value={f.value}>
                          {f.label}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>

              {/* Code Input (for Explain, Debug, Improve) */}
              {selectedOp !== 'generate' ? (
                <div className="form-group">
                  <div className="form-label-row">
                    <label className="form-label-sm">Source Code</label>
                    {activeCodeSnippet && (
                      <button
                        type="button"
                        className="btn-link-sm"
                        onClick={handleLoadFromActiveFile}
                        title="Load current file from Monaco Editor"
                      >
                        <FileCode size={12} /> Use Editor File ({activeFile ? activeFile.split('/').pop() : 'Active'})
                      </button>
                    )}
                  </div>
                  <textarea
                    className="form-textarea-code"
                    rows={6}
                    placeholder="Paste code snippet here, or click 'Use Editor File' above..."
                    value={opCode}
                    onChange={(e) => setOpCode(e.target.value)}
                    required
                  />
                  <div className="textarea-footer">
                    <span>{opCode.length} / 50,000 characters</span>
                    {opCode && (
                      <button
                        type="button"
                        className="btn-link-xs"
                        onClick={() => setOpCode('')}
                      >
                        Clear
                      </button>
                    )}
                  </div>
                </div>
              ) : (
                /* Natural Language Prompt Input (for Generate) */
                <div className="form-group">
                  <label className="form-label-sm">Specification / Prompt</label>
                  <textarea
                    className="form-textarea-code"
                    rows={5}
                    placeholder="Describe what code you want to build (e.g. 'Write a Python rate limiter middleware using Redis token buckets with unit tests')..."
                    value={opPrompt}
                    onChange={(e) => setOpPrompt(e.target.value)}
                    required
                  />
                </div>
              )}

              {/* Debug Specific: Error Message / Bug Details */}
              {selectedOp === 'debug' && (
                <div className="form-group">
                  <label className="form-label-sm">Reported Error / Stack Trace (Optional)</label>
                  <textarea
                    className="form-textarea-sm"
                    rows={2}
                    placeholder="e.g. TypeError: Cannot read property 'map' of undefined at line 42..."
                    value={opErrorMessage}
                    onChange={(e) => setOpErrorMessage(e.target.value)}
                  />
                </div>
              )}

              {/* Optional Context / Requirements */}
              <div className="form-group">
                <label className="form-label-sm">Additional Architectural Context (Optional)</label>
                <input
                  type="text"
                  className="form-input-sm"
                  placeholder="e.g. Target Node 20+, Flask 3.0, PostgreSQL, React 19..."
                  value={opContext}
                  onChange={(e) => setOpContext(e.target.value)}
                />
              </div>

              {/* Submit Button */}
              <div className="ai-ops-action-bar">
                <button
                  type="submit"
                  className="btn btn-primary btn-block"
                  disabled={
                    opLoading ||
                    (selectedOp === 'generate' ? !opPrompt.trim() : !opCode.trim())
                  }
                >
                  {opLoading ? (
                    <>
                      <RefreshCw size={14} className="spin-icon" />
                      <span>Gemini is Processing...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles size={14} />
                      <span>
                        {selectedOp === 'explain' && 'Explain Code'}
                        {selectedOp === 'debug' && 'Debug & Fix'}
                        {selectedOp === 'generate' && 'Generate Code'}
                        {selectedOp === 'improve' && 'Improve & Refactor'}
                      </span>
                    </>
                  )}
                </button>
              </div>
            </form>

            {/* Error Message Box */}
            {opError && (
              <div className="ai-ops-error-box">
                <AlertCircle size={16} style={{ flexShrink: 0 }} />
                <div style={{ flex: 1 }}>
                  <strong>Operation Error</strong>
                  <p>{opError}</p>
                </div>
              </div>
            )}

            {/* Loading Indicator with Animated Skeleton */}
            {opLoading && (
              <div className="ai-ops-loading-box">
                <div className="loading-header">
                  <Sparkles size={15} className="pulse-icon" />
                  <span>Synthesizing response with {geminiStatus.model}...</span>
                </div>
                <div className="loading-shimmer-line" style={{ width: '85%' }} />
                <div className="loading-shimmer-line" style={{ width: '95%' }} />
                <div className="loading-shimmer-line" style={{ width: '70%' }} />
              </div>
            )}

            {/* Structured AI Result View */}
            {opResult && !opLoading && (
              <div className="ai-ops-result-card">
                <div className="result-header">
                  <div className="result-title-group">
                    <CheckCircle2 size={16} style={{ color: 'var(--emerald)' }} />
                    <span className="result-badge op-badge">
                      {opResult.operation?.toUpperCase()}
                    </span>
                    <span className="result-model-badge">{opResult.model}</span>
                  </div>
                  <button
                    type="button"
                    className="btn btn-ghost btn-xs"
                    onClick={() =>
                      copyToClipboard(
                        `${opResult.summary}\n\n${opResult.code ? '```\n' + opResult.code + '\n```' : ''}`,
                        'all'
                      )
                    }
                    title="Copy full analysis"
                  >
                    {copiedSection === 'all' ? <Check size={12} /> : <Copy size={12} />}
                    <span>{copiedSection === 'all' ? 'Copied' : 'Copy All'}</span>
                  </button>
                </div>

                {/* Summary / Explanation Body */}
                <div className="result-section">
                  <h4 className="result-section-title">
                    {selectedOp === 'debug' ? '🔍 Root Cause Analysis' : '📋 Explanation & Overview'}
                  </h4>
                  <div className="result-markdown-body">
                    <ReactMarkdown>{opResult.summary}</ReactMarkdown>
                  </div>
                </div>

                {/* Generated / Corrected Code Block */}
                {opResult.code && (
                  <div className="result-section">
                    <div className="code-header-bar">
                      <h4 className="result-section-title" style={{ margin: 0 }}>
                        {selectedOp === 'debug'
                          ? '🛠️ Corrected Code Fix'
                          : selectedOp === 'improve'
                          ? '✨ Refactored Code'
                          : '⚡ Generated Code'}
                      </h4>
                      <button
                        type="button"
                        className="btn btn-secondary btn-xs"
                        onClick={() => copyToClipboard(opResult.code, 'code')}
                        title="Copy code to clipboard"
                      >
                        {copiedSection === 'code' ? <Check size={12} /> : <Copy size={12} />}
                        <span>{copiedSection === 'code' ? 'Copied!' : 'Copy Code'}</span>
                      </button>
                    </div>
                    <pre className="result-code-block">
                      <code>{opResult.code}</code>
                    </pre>
                  </div>
                )}

                {/* Suggested Improvements / Best Practices */}
                {opResult.improvements && opResult.improvements.length > 0 && (
                  <div className="result-section">
                    <h4 className="result-section-title">💡 Suggested Best Practices &amp; Next Steps</h4>
                    <ul className="result-list">
                      {opResult.improvements.map((imp, idx) => (
                        <li key={idx} className="result-list-item">
                          <CheckCircle2 size={13} style={{ color: 'var(--primary)', marginTop: '2px', flexShrink: 0 }} />
                          <span>{imp}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Assumptions & Safety Warnings (Clearly distinguished from verified facts) */}
                {opResult.assumptions_warnings && opResult.assumptions_warnings.length > 0 && (
                  <div className="result-section result-warning-section">
                    <div className="warning-header">
                      <ShieldAlert size={14} style={{ color: 'var(--amber)' }} />
                      <span className="warning-title">Assumptions &amp; Safety Warnings</span>
                    </div>
                    <ul className="warning-list">
                      {opResult.assumptions_warnings.map((w, idx) => (
                        <li key={idx} className="warning-item">
                          {w}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB: SEMANTIC CODEBASE SEARCH */}
      {activeTab === 'search' && (
        <SemanticSearchTab
          project={project}
          onJumpToCitation={onJumpToCitation}
          showToast={showToast}
        />
      )}

      {/* TAB: AI CODE REVIEW */}
      {activeTab === 'review' && (
        <CodeReviewTab
          project={project}
          activeFile={activeFile}
          activeCodeSnippet={activeCodeSnippet}
          onJumpToCitation={onJumpToCitation}
          showToast={showToast}
        />
      )}

      {/* TAB: TEST-CASE GENERATOR */}
      {activeTab === 'tests' && (
        <TestGeneratorTab
          project={project}
          activeFile={activeFile}
          activeCodeSnippet={activeCodeSnippet}
          showToast={showToast}
        />
      )}

      {/* TAB: README & DOCUMENTATION GENERATOR */}
      {activeTab === 'docs' && (
        <ReadmeGeneratorTab
          project={project}
          onRefreshFileTree={onRefreshFileTree}
          showToast={showToast}
        />
      )}

      {/* ── Scoped CSS Styles ── */}
      <style>{`
        .rag-chat-container {
          display: flex;
          flex-direction: column;
          height: calc(100% - 44px);
          overflow: hidden;
        }

        .conv-toolbar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 8px 12px;
          background: var(--bg-surface);
          border-bottom: 1px solid var(--border-subtle);
          position: relative;
        }

        .conv-selector-wrapper {
          position: relative;
          flex: 1;
          margin-right: 8px;
        }

        .conv-selector-btn {
          display: flex;
          align-items: center;
          gap: 6px;
          width: 100%;
          padding: 5px 8px;
          background: var(--bg-subtle);
          border: 1px solid var(--border-subtle);
          border-radius: var(--radius-sm);
          color: var(--text-main);
          font-size: 11.5px;
          cursor: pointer;
          transition: var(--trans-quick);
          text-align: left;
        }

        .conv-selector-btn:hover {
          border-color: var(--border-default);
          background: var(--bg-surface-hover);
        }

        .conv-title-text {
          flex: 1;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .conv-dropdown-menu {
          position: absolute;
          top: 100%;
          left: 0;
          width: 280px;
          max-height: 280px;
          margin-top: 4px;
          background: var(--bg-surface);
          border: 1px solid var(--border-default);
          border-radius: var(--radius-md);
          box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
          z-index: 50;
          display: flex;
          flex-direction: column;
          overflow: hidden;
        }

        .conv-dropdown-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 8px 10px;
          border-bottom: 1px solid var(--border-subtle);
          font-size: 11px;
          font-weight: 600;
          color: var(--text-muted);
        }

        .conv-dropdown-list {
          overflow-y: auto;
          flex: 1;
          padding: 4px;
        }

        .conv-dropdown-empty {
          padding: 16px;
          text-align: center;
          color: var(--text-dim);
          font-size: 11.5px;
        }

        .conv-item {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 6px 8px;
          border-radius: var(--radius-sm);
          cursor: pointer;
          font-size: 11.5px;
          color: var(--text-muted);
          transition: var(--trans-quick);
        }

        .conv-item:hover {
          background: var(--bg-subtle);
          color: var(--text-main);
        }

        .conv-item.active {
          background: rgba(56, 189, 248, 0.12);
          color: var(--text-accent);
          font-weight: 500;
        }

        .conv-item-title {
          flex: 1;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .conv-item-actions {
          display: flex;
          gap: 2px;
          opacity: 0;
          transition: var(--trans-quick);
        }

        .conv-item:hover .conv-item-actions {
          opacity: 1;
        }

        .conv-action-btn {
          background: transparent;
          border: none;
          padding: 3px;
          border-radius: 3px;
          color: var(--text-dim);
          cursor: pointer;
        }

        .conv-action-btn:hover {
          color: var(--text-main);
          background: var(--bg-surface);
        }

        .conv-action-btn.delete:hover {
          color: var(--rose);
        }

        .chat-empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 24px 16px;
          text-align: center;
        }

        .empty-state-icon-wrapper {
          width: 52px;
          height: 52px;
          border-radius: 50%;
          background: rgba(56, 189, 248, 0.1);
          display: flex;
          align-items: center;
          justify-content: center;
          margin-bottom: 12px;
        }

        .empty-state-sparkle {
          color: var(--primary);
        }

        .empty-state-title {
          font-size: 15px;
          font-weight: 600;
          margin-bottom: 6px;
          color: var(--text-main);
        }

        .empty-state-subtitle {
          font-size: 12px;
          color: var(--text-muted);
          line-height: 1.5;
          max-width: 320px;
          margin-bottom: 20px;
        }

        .starter-prompts-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: 8px;
          width: 100%;
          max-width: 360px;
        }

        .starter-card {
          background: var(--bg-subtle);
          border: 1px solid var(--border-subtle);
          border-radius: var(--radius-md);
          padding: 10px 12px;
          text-align: left;
          cursor: pointer;
          transition: var(--trans-quick);
        }

        .starter-card:hover {
          border-color: var(--border-default);
          background: var(--bg-surface-hover);
          transform: translateY(-1px);
        }

        .starter-card-header {
          display: flex;
          align-items: center;
          gap: 6px;
          margin-bottom: 3px;
        }

        .starter-card-title {
          font-size: 12px;
          font-weight: 600;
          color: var(--text-main);
        }

        .starter-card-prompt {
          font-size: 11px;
          color: var(--text-muted);
          line-height: 1.4;
          margin: 0;
        }

        .citation-container {
          margin-top: 12px;
          padding-top: 10px;
          border-top: 1px solid var(--border-subtle);
        }

        .citation-label {
          display: flex;
          align-items: center;
          gap: 5px;
          font-size: 11px;
          font-weight: 600;
          color: var(--text-dim);
          text-transform: uppercase;
          letter-spacing: 0.05em;
          margin-bottom: 8px;
        }

        .citation-cards-grid {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .citation-card {
          background: rgba(15, 23, 42, 0.6);
          border: 1px solid var(--border-subtle);
          border-radius: var(--radius-sm);
          padding: 8px 10px;
          cursor: pointer;
          transition: var(--trans-quick);
        }

        .citation-card:hover {
          background: rgba(56, 189, 248, 0.08);
          border-color: rgba(56, 189, 248, 0.4);
        }

        .citation-card-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          font-family: var(--font-mono);
          font-size: 11.5px;
        }

        .citation-path-group {
          display: flex;
          align-items: center;
          gap: 5px;
          color: var(--text-accent);
          font-weight: 500;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .citation-path {
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .citation-lines {
          font-size: 10.5px;
          color: var(--text-dim);
          background: rgba(255, 255, 255, 0.06);
          padding: 1px 5px;
          border-radius: 3px;
          margin: 0 6px;
          flex-shrink: 0;
        }

        .citation-jump-icon {
          color: var(--text-dim);
          flex-shrink: 0;
        }

        .citation-card:hover .citation-jump-icon {
          color: var(--text-accent);
        }

        .citation-snippet-preview {
          margin-top: 5px;
          background: #090d13;
          border-radius: 3px;
          padding: 4px 6px;
          font-size: 10.5px;
          font-family: var(--font-mono);
          color: var(--text-muted);
          max-height: 48px;
          overflow: hidden;
          line-height: 1.35;
          border-left: 2px solid var(--primary);
        }

        .chat-code-block {
          background: #0b0f17;
          border: 1px solid var(--border-subtle);
          border-radius: var(--radius-sm);
          margin: 8px 0;
          overflow: hidden;
        }

        .chat-code-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 4px 8px;
          background: rgba(255, 255, 255, 0.03);
          border-bottom: 1px solid var(--border-subtle);
        }

        .chat-code-lang {
          font-family: var(--font-mono);
          font-size: 10.5px;
          color: var(--text-dim);
          text-transform: lowercase;
        }

        .chat-code-copy-btn {
          display: flex;
          align-items: center;
          gap: 3px;
          background: transparent;
          border: none;
          color: var(--text-dim);
          font-size: 11px;
          cursor: pointer;
          padding: 2px 5px;
          border-radius: 3px;
        }

        .chat-code-copy-btn:hover {
          color: var(--text-main);
          background: rgba(255, 255, 255, 0.08);
        }

        .chat-code-pre {
          padding: 8px 10px;
          margin: 0;
          overflow-x: auto;
          font-family: var(--font-mono);
          font-size: 11.5px;
          line-height: 1.45;
          color: #e2e8f0;
        }

        .chat-inline-code {
          background: rgba(255, 255, 255, 0.08);
          padding: 1px 4px;
          border-radius: 3px;
          font-family: var(--font-mono);
          font-size: 11.5px;
          color: var(--text-accent);
        }

        .chat-retry-bar {
          display: flex;
          justify-content: center;
          padding: 8px 0;
        }

        .message-error {
          border-left: 3px solid var(--rose) !important;
          background: rgba(244, 63, 94, 0.06) !important;
        }
      `}</style>
    </aside>
  );
}
