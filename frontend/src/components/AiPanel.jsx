/**
 * AiPanel — thin wrapper that re-exports the existing ChatPanel
 * under the new workspace architecture.
 *
 * This keeps the AI panel isolated so WorkspacePage imports a
 * single <AiPanel> component, while the full ChatPanel
 * implementation lives in ChatPanel.jsx unchanged.
 */
import React from 'react';
import ChatPanel from './ChatPanel';

export default function AiPanel({ project, activeFile, activeFileContent, onJumpToCitation, showToast, onRefreshFileTree }) {
  return (
    <ChatPanel
      project={project}
      activeFile={activeFile}
      activeCodeSnippet={activeFileContent}
      onJumpToCitation={onJumpToCitation}
      showToast={showToast}
      onRefreshFileTree={onRefreshFileTree}
    />
  );
}
