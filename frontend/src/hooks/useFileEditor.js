import { useState, useCallback } from 'react';
import { getContent, saveContent, getTree } from '../services/fileApi';

/**
 * useFileEditor — manages active file selection, content, and save operations.
 *
 * @param {object|null} currentProject  The active project object.
 * @param {function}    showToast        Toast callback from useToast.
 */
export function useFileEditor(currentProject, showToast) {
  const [fileTree, setFileTree] = useState([]);
  const [activeFilePath, setActiveFilePath] = useState('');
  const [activeFileContent, setActiveFileContent] = useState('');
  const [activeFileLanguage, setActiveFileLanguage] = useState('plaintext');
  const [highlightRange, setHighlightRange] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoadingTree, setIsLoadingTree] = useState(false);

  const loadFileTree = useCallback(async (projId) => {
    if (!projId) { setFileTree([]); return; }
    setIsLoadingTree(true);
    try {
      const data = await getTree(projId);
      setFileTree(data.tree || []);
    } catch (err) {
      console.error('Failed to fetch file tree:', err);
    } finally {
      setIsLoadingTree(false);
    }
  }, []);

  const selectFile = useCallback(async (path) => {
    if (!currentProject) return;
    try {
      const data = await getContent(currentProject.id, path);
      setActiveFilePath(data.path);
      setActiveFileContent(data.content);
      setActiveFileLanguage(data.language);
      setHighlightRange(null);
    } catch (err) {
      showToast('Failed to open file: ' + err.message, 'error');
    }
  }, [currentProject, showToast]);

  const jumpToCitation = useCallback(async (filePath, startLine, endLine) => {
    if (!currentProject) return;
    if (activeFilePath !== filePath) {
      try {
        const data = await getContent(currentProject.id, filePath);
        setActiveFilePath(data.path);
        setActiveFileContent(data.content);
        setActiveFileLanguage(data.language);
        setTimeout(() => setHighlightRange({ start_line: startLine, end_line: endLine }), 150);
      } catch (err) {
        showToast(`Could not open ${filePath}: ${err.message}`, 'error');
      }
    } else {
      setHighlightRange({ start_line: startLine, end_line: endLine });
    }
  }, [currentProject, activeFilePath, showToast]);

  const saveFile = useCallback(async (newContent) => {
    if (!currentProject || !activeFilePath) return;
    setIsSaving(true);
    try {
      await saveContent(currentProject.id, activeFilePath, newContent);
      setActiveFileContent(newContent);
      showToast(`Saved ${activeFilePath}`, 'success');
    } catch (err) {
      showToast('Failed to save file: ' + err.message, 'error');
    } finally {
      setIsSaving(false);
    }
  }, [currentProject, activeFilePath, showToast]);

  const clearEditor = useCallback(() => {
    setActiveFilePath('');
    setActiveFileContent('');
    setHighlightRange(null);
  }, []);

  return {
    fileTree,
    activeFilePath,
    activeFileContent,
    activeFileLanguage,
    highlightRange,
    isSaving,
    isLoadingTree,
    loadFileTree,
    selectFile,
    jumpToCitation,
    saveFile,
    clearEditor,
  };
}
