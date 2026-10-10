import api from './api';

// ─── Named function exports (used by hooks) ───────────────────────────────────

export async function uploadZip(projectId, file, onUploadProgress) {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await api.post(`/files/${projectId}/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress,
  });
  return data;
}

export async function getTree(projectId) {
  const { data } = await api.get(`/files/${projectId}/tree`);
  return data;
}

export async function getContent(projectId, filePath) {
  const { data } = await api.get(`/files/${projectId}/content`, {
    params: { path: filePath },
  });
  return data;
}

export async function saveContent(projectId, filePath, content) {
  const { data } = await api.post(`/files/${projectId}/save`, {
    path: filePath,
    content,
  });
  return data;
}

export async function listFiles(projectId) {
  const { data } = await api.get(`/files/${projectId}/files`);
  return data;
}

// ─── Legacy object export for App.jsx / ProjectModal compatibility ────────────

export const fileApi = {
  uploadZip,
  listFiles,
  getTree,
  getContent,
  saveContent,
};
