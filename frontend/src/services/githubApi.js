import api from './api';

export const githubApi = {
  /**
   * Validates a GitHub repository URL and returns metadata.
   * Does NOT download or index anything.
   */
  validateRepo: async (projectId, repoUrl) => {
    const res = await api.post(`/github/${projectId}/validate`, { repo_url: repoUrl });
    return res.data;
  },

  /**
   * Downloads, extracts, chunks, embeds, and FAISS-indexes a GitHub repository.
   * @param {boolean} force  – skip SHA-match optimization and always re-index
   */
  importRepo: async (projectId, repoUrl, force = false) => {
    const res = await api.post(`/github/${projectId}/import`, {
      repo_url: repoUrl,
      force,
    });
    return res.data;
  },

  /**
   * Returns the current import status and metadata for the project.
   * Safe to poll; returns has_github_import:false if no import has run yet.
   */
  getStatus: async (projectId) => {
    const res = await api.get(`/github/${projectId}/status`);
    return res.data;
  },

  /**
   * Re-imports (refreshes) the previously linked GitHub repository.
   * Stale/deleted files are cleaned up automatically.
   * @param {string} repoUrl  – optional override; uses stored URL if omitted
   */
  refreshRepo: async (projectId, repoUrl = '') => {
    const body = repoUrl ? { repo_url: repoUrl } : {};
    const res = await api.post(`/github/${projectId}/refresh`, body);
    return res.data;
  },
};
