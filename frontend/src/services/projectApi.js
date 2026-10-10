import api from './api';

// ─── Named function exports (used by ProjectContext) ─────────────────────────

export async function listProjects() {
  const { data } = await api.get('/projects');
  return data;
}

export async function createProject(name, description = '') {
  const { data } = await api.post('/projects', { name, description });
  return data;
}

export async function getProject(id) {
  const { data } = await api.get(`/projects/${id}`);
  return data;
}

export async function deleteProject(id) {
  const { data } = await api.delete(`/projects/${id}`);
  return data;
}

export async function updateProject(id, payload) {
  const { data } = await api.patch(`/projects/${id}`, payload);
  return data;
}

export async function healthCheck() {
  const { data } = await api.get('/health');
  return data;
}

export async function reindexProject(id) {
  const { data } = await api.post(`/projects/${id}/index`);
  return data;
}

// ─── Legacy object export for App.jsx compatibility ───────────────────────────

export const projectApi = {
  list: listProjects,
  create: createProject,
  get: getProject,
  update: updateProject,
  delete: deleteProject,
  health: healthCheck,
  reindex: reindexProject,
};
