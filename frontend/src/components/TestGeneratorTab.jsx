import React, { useState, useEffect } from 'react';
import {
  FlaskConical,
  FileCode,
  Copy,
  Check,
  Download,
  AlertTriangle,
  Sparkles,
  CheckCircle2,
  RefreshCw,
  Tag,
  ShieldAlert,
} from 'lucide-react';
import { ragApi } from '../services/ragApi';

const FRAMEWORK_OPTIONS = [
  { value: '', label: '✨ Auto-Detect from Project Manifest' },
  { value: 'pytest', label: 'pytest (Python)' },
  { value: 'unittest', label: 'unittest (Python)' },
  { value: 'jest', label: 'Jest (JavaScript / TypeScript)' },
  { value: 'vitest', label: 'Vitest (JavaScript / TypeScript)' },
  { value: 'mocha', label: 'Mocha (JavaScript)' },
  { value: 'testing', label: 'Go testing package' },
];

export default function TestGeneratorTab({ project, activeFile, activeCodeSnippet, showToast }) {
  const [targetFile, setTargetFile] = useState(activeFile || '');
  const [targetFunction, setTargetFunction] = useState('');
  const [customCode, setCustomCode] = useState(activeCodeSnippet || '');
  const [framework, setFramework] = useState('');
  const [useCustomCode, setUseCustomCode] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [copiedCode, setCopiedCode] = useState(false);

  useEffect(() => {
    if (activeFile && !useCustomCode) {
      setTargetFile(activeFile);
    }
  }, [activeFile, useCustomCode]);

  const handleUseActiveFile = () => {
    setUseCustomCode(false);
    setTargetFile(activeFile || '');
    if (activeCodeSnippet) setCustomCode(activeCodeSnippet);
  };

  const handleGenerateTests = async (e) => {
    e.preventDefault();
    if (!project) return;

    if (!useCustomCode && !targetFile.trim()) {
      showToast?.('Please specify a file path or select a file in the editor', 'warning');
      return;
    }

    if (useCustomCode && !customCode.trim()) {
      showToast?.('Please paste or write code to test', 'warning');
      return;
    }

    setIsLoading(true);
    try {
      const payload = {
        file_path: !useCustomCode ? targetFile.trim() : (targetFile.trim() || 'code'),
        code: useCustomCode ? customCode.trim() : '',
        function_name: targetFunction.trim(),
        framework: framework.trim(),
      };
      const res = await ragApi.generateTests(project.id, payload);
      setTestResult(res);
      showToast?.(`Generated test suite using ${res.framework || 'detected framework'}!`, 'success');
    } catch (err) {
      const msg = err.response?.data?.error || err.message;
      showToast?.('Test generation failed: ' + msg, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  const copyTestCode = () => {
    if (!testResult?.test_code) return;
    navigator.clipboard.writeText(testResult.test_code).then(() => {
      setCopiedCode(true);
      setTimeout(() => setCopiedCode(false), 2000);
      showToast?.('Copied test code to clipboard', 'success');
    });
  };

  const downloadTestFile = () => {
    if (!testResult?.test_code) return;
    const filename = testResult.suggested_file_name || 'generated_test.py';
    const blob = new Blob([testResult.test_code], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast?.(`Downloaded ${filename}`, 'success');
  };

  const getTypeBadgeClass = (type) => {
    switch (type) {
      case 'happy_path': return 'badge-happy-path';
      case 'edge_case': return 'badge-edge-case';
      case 'invalid_input': return 'badge-invalid-input';
      case 'failure_scenario': return 'badge-failure-scenario';
      default: return 'badge-neutral';
    }
  };

  const getTypeLabel = (type) => {
    switch (type) {
      case 'happy_path': return 'Happy Path';
      case 'edge_case': return 'Edge Case';
      case 'invalid_input': return 'Invalid Input';
      case 'failure_scenario': return 'Failure Scenario';
      default: return type;
    }
  };

  return (
    <div className="dev-tool-tab-container">
      {/* Header */}
      <div className="dev-tool-header">
        <h3 className="dev-tool-title">
          <FlaskConical size={16} className="text-accent" />
          Test-Case Generator
        </h3>
        <p className="dev-tool-subtitle">
          Synthesize unit and edge-case tests matching project framework. Tests are static drafts and are never executed automatically.
        </p>
      </div>

      {/* Configuration Form */}
      <form onSubmit={handleGenerateTests} className="dev-tool-config-card">
        <div className="review-mode-toggle-group">
          <button
            type="button"
            className={`btn btn-xs ${!useCustomCode ? 'btn-primary' : 'btn-ghost'}`}
            onClick={handleUseActiveFile}
          >
            <FileCode size={13} /> Active File ({activeFile ? activeFile.split('/').pop() : 'None'})
          </button>
          <button
            type="button"
            className={`btn btn-xs ${useCustomCode ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setUseCustomCode(true)}
          >
            Custom Code
          </button>
        </div>

        {!useCustomCode ? (
          <>
            <div className="form-group" style={{ marginTop: '10px' }}>
              <label className="form-label">Source File Path</label>
              <input
                type="text"
                className="form-input"
                value={targetFile}
                onChange={(e) => setTargetFile(e.target.value)}
                placeholder="e.g. backend/app/services/auth_service.py"
              />
            </div>
            <div className="form-group" style={{ marginTop: '8px' }}>
              <label className="form-label">Specific Function / Class (Optional)</label>
              <input
                type="text"
                className="form-input"
                value={targetFunction}
                onChange={(e) => setTargetFunction(e.target.value)}
                placeholder="e.g. authenticate_user"
              />
            </div>
          </>
        ) : (
          <div className="form-group" style={{ marginTop: '10px' }}>
            <label className="form-label">Code to Test</label>
            <textarea
              className="form-textarea"
              rows={5}
              value={customCode}
              onChange={(e) => setCustomCode(e.target.value)}
              placeholder="Paste functions or methods to generate test cases for..."
            />
          </div>
        )}

        <div className="form-group" style={{ marginTop: '10px' }}>
          <label className="form-label">Target Test Framework</label>
          <select
            className="form-select"
            value={framework}
            onChange={(e) => setFramework(e.target.value)}
          >
            {FRAMEWORK_OPTIONS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
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
          {isLoading ? <RefreshCw size={14} className="spin" /> : <FlaskConical size={14} />}
          <span>{isLoading ? 'Generating Test Suite...' : 'Generate Comprehensive Tests'}</span>
        </button>
      </form>

      {/* Results Scroll Area */}
      <div className="dev-tool-content-scroll">
        {isLoading && (
          <div className="search-loading-box">
            <div className="loading-header">
              <Sparkles size={15} className="pulse-icon text-accent" />
              <span>Analyzing edge cases and synthesizing test suites...</span>
            </div>
            <div className="loading-shimmer-line" style={{ width: '85%' }} />
            <div className="loading-shimmer-line" style={{ width: '95%' }} />
            <div className="loading-shimmer-line" style={{ width: '70%' }} />
          </div>
        )}

        {testResult && !isLoading && (
          <div className="test-results-container">
            {/* Meta bar */}
            <div className="test-meta-banner">
              <div className="test-meta-left">
                <span className="test-framework-pill">
                  Framework: <strong>{testResult.framework?.toUpperCase()}</strong>
                </span>
                <span className="test-filename-pill">
                  File: <code>{testResult.suggested_file_name}</code>
                </span>
              </div>
              <div className="test-actions-group">
                <button
                  type="button"
                  className="btn btn-secondary btn-xs"
                  onClick={copyTestCode}
                  title="Copy generated tests"
                >
                  {copiedCode ? <Check size={12} /> : <Copy size={12} />}
                  <span>{copiedCode ? 'Copied' : 'Copy'}</span>
                </button>
                <button
                  type="button"
                  className="btn btn-primary btn-xs"
                  onClick={downloadTestFile}
                  title="Download test file"
                >
                  <Download size={12} />
                  <span>Download</span>
                </button>
              </div>
            </div>

            {/* Test Cases Category Overview */}
            {testResult.test_cases?.length > 0 && (
              <div className="test-cases-card">
                <h4 className="test-cases-card-title">
                  <Tag size={13} /> Generated Test Scenarios ({testResult.test_cases.length})
                </h4>
                <div className="test-cases-grid">
                  {testResult.test_cases.map((tc, idx) => (
                    <div key={idx} className="test-scenario-item">
                      <div className="scenario-top">
                        <span className={`scenario-type-badge ${getTypeBadgeClass(tc.type)}`}>
                          {getTypeLabel(tc.type)}
                        </span>
                        <code className="scenario-name">{tc.name}</code>
                      </div>
                      <p className="scenario-desc">{tc.description}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Generated Code Display */}
            <div className="test-code-card">
              <div className="test-code-header">
                <FileCode size={14} className="text-accent" />
                <span className="test-code-title">Generated Test Code (Separate from source files)</span>
              </div>
              <pre className="test-code-block">
                <code>{testResult.test_code}</code>
              </pre>
            </div>

            {/* Mandatory Safety Notice */}
            <div className="alert-card alert-warning" style={{ marginTop: '12px' }}>
              <ShieldAlert size={16} className="alert-icon text-amber" />
              <div className="alert-body">
                <strong>Execution Safety Notice</strong>
                <p>
                  These tests are AI-generated suggestions and have <strong>not</strong> been automatically executed.
                  Copy or download them to run in your local test environment.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
