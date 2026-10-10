import React, { useState } from 'react';
import { Search, FileCode, ArrowRight, AlertTriangle, AlertCircle, Sparkles, CornerDownLeft } from 'lucide-react';
import { ragApi } from '../services/ragApi';

const SAMPLE_QUERIES = [
  'Where is user authentication handled?',
  'Which function validates uploaded files?',
  'Database models and connection pool',
  'Error handling and exception handlers',
];

export default function SemanticSearchTab({ project, onJumpToCitation, showToast }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchStatus, setSearchStatus] = useState('idle'); // 'idle' | 'success' | 'not_indexed' | 'no_results'
  const [statusMessage, setStatusMessage] = useState('');

  const executeSearch = async (queryText) => {
    const q = (queryText || searchQuery).trim();
    if (!q || !project) return;

    setIsSearching(true);
    setSearchStatus('idle');
    try {
      const data = await ragApi.searchCodebase(project.id, q);
      setSearchResults(data.results || []);
      setSearchStatus(data.status || (data.results && data.results.length > 0 ? 'success' : 'no_results'));
      setStatusMessage(data.message || '');
    } catch (err) {
      showToast?.('Search error: ' + (err.response?.data?.error || err.message), 'error');
      setSearchStatus('no_results');
      setStatusMessage('An error occurred during vector retrieval.');
    } finally {
      setIsSearching(false);
    }
  };

  const handleFormSubmit = (e) => {
    e.preventDefault();
    executeSearch();
  };

  const handleChipClick = (query) => {
    setSearchQuery(query);
    executeSearch(query);
  };

  return (
    <div className="dev-tool-tab-container">
      {/* Search Bar Header */}
      <div className="dev-tool-header">
        <h3 className="dev-tool-title">
          <Search size={16} className="text-accent" />
          Semantic Codebase Search
        </h3>
        <p className="dev-tool-subtitle">
          Search your codebase by meaning and intent using FAISS vector embeddings.
        </p>
      </div>

      <form onSubmit={handleFormSubmit} className="dev-tool-search-form">
        <div className="search-input-wrapper">
          <Search size={15} className="search-input-icon" />
          <input
            type="text"
            className="form-input search-input-field"
            placeholder="Ask a codebase question (e.g. 'Where is auth handled?')..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <button
            type="submit"
            className="btn btn-primary btn-sm search-submit-btn"
            disabled={isSearching || !project || !searchQuery.trim()}
          >
            {isSearching ? <span className="spinner-xs" /> : <CornerDownLeft size={14} />}
            <span>{isSearching ? 'Searching...' : 'Search'}</span>
          </button>
        </div>
      </form>

      {/* Suggested Query Chips */}
      <div className="search-chips-container">
        <span className="search-chips-label">Sample queries:</span>
        <div className="search-chips-row">
          {SAMPLE_QUERIES.map((q, idx) => (
            <button
              key={idx}
              type="button"
              className="search-chip-btn"
              onClick={() => handleChipClick(q)}
              disabled={isSearching || !project}
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Results Area */}
      <div className="dev-tool-content-scroll">
        {/* Unindexed Stale Index Warning */}
        {searchStatus === 'not_indexed' && (
          <div className="alert-card alert-warning">
            <AlertTriangle size={18} className="alert-icon text-amber" />
            <div className="alert-body">
              <strong>Codebase Not Indexed</strong>
              <p>
                {statusMessage ||
                  'This project does not have a vector index yet. Upload an archive or trigger indexing to enable semantic search.'}
              </p>
            </div>
          </div>
        )}

        {/* No Results State */}
        {searchStatus === 'no_results' && (
          <div className="empty-results-box">
            <AlertCircle size={24} className="text-muted" style={{ margin: '0 auto 8px' }} />
            <p className="empty-results-title">No matching code chunks</p>
            <p className="empty-results-desc">
              {statusMessage ||
                'No code snippets matched your query. Try asking with different terminology or function names.'}
            </p>
          </div>
        )}

        {/* Initial Idle State */}
        {searchStatus === 'idle' && searchResults.length === 0 && !isSearching && (
          <div className="empty-results-box">
            <Sparkles size={28} className="empty-state-sparkle" style={{ margin: '0 auto 10px' }} />
            <p className="empty-results-title">Natural-Language Code Retrieval</p>
            <p className="empty-results-desc">
              Ask questions about logic, functions, or architectural responsibilities. Results include exact line numbers and relevance scores.
            </p>
          </div>
        )}

        {/* Loading Skeleton */}
        {isSearching && (
          <div className="search-loading-box">
            <div className="loading-header">
              <Search size={15} className="pulse-icon text-accent" />
              <span>Scanning project vector store for relevant chunks...</span>
            </div>
            <div className="loading-shimmer-line" style={{ width: '90%' }} />
            <div className="loading-shimmer-line" style={{ width: '95%' }} />
            <div className="loading-shimmer-line" style={{ width: '75%' }} />
          </div>
        )}

        {/* Match Count Header */}
        {searchResults.length > 0 && !isSearching && (
          <div className="search-results-meta">
            <span>Found <strong>{searchResults.length}</strong> grounded match{searchResults.length === 1 ? '' : 'es'}</span>
          </div>
        )}

        {/* Results List */}
        {!isSearching &&
          searchResults.map((res, idx) => {
            const relPct = res.relevance_percentage ?? Math.max(10, Math.min(99, Math.round(((res.score || 0) + 1) * 50)));
            const filePath = res.file_path || res.metadata?.file_path || 'unknown';
            const startLine = res.start_line ?? res.metadata?.start_line ?? 1;
            const endLine = res.end_line ?? res.metadata?.end_line ?? 1;
            const snippet = res.snippet || res.content || '';

            return (
              <div
                key={idx}
                className="search-result-card"
                onClick={() => onJumpToCitation?.(filePath, startLine, endLine)}
                title="Click to view and highlight in Monaco Editor"
              >
                <div className="search-result-header">
                  <div className="search-result-file-info">
                    <FileCode size={14} className="text-accent" />
                    <span className="search-result-filepath">{filePath}</span>
                    <span className="search-result-lines">L{startLine}–{endLine}</span>
                  </div>
                  <span className={`search-relevance-pill ${relPct >= 75 ? 'high' : relPct >= 50 ? 'medium' : 'low'}`}>
                    {relPct}% match
                  </span>
                </div>

                <pre className="search-result-snippet">
                  <code>{snippet}</code>
                </pre>

                <div className="search-result-footer">
                  <span className="search-jump-hint">
                    Jump to location in editor <ArrowRight size={11} />
                  </span>
                </div>
              </div>
            );
          })}
      </div>
    </div>
  );
}
