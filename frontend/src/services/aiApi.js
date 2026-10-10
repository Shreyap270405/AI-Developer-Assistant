import api from './api';

export const aiApi = {
  /**
   * Check if Gemini API is configured and get active model information.
   */
  getStatus: async () => {
    const res = await api.get('/ai/status');
    return res.data;
  },

  /**
   * Request Gemini to explain a code snippet.
   */
  explainCode: async ({ code, language = '', filePath = '', context = '' }) => {
    const res = await api.post('/ai/explain', {
      code,
      language,
      file_path: filePath,
      context,
    });
    return res.data;
  },

  /**
   * Request Gemini to debug an issue or code snippet.
   */
  debugCode: async ({ code, errorMessage = '', language = '', filePath = '', context = '' }) => {
    const res = await api.post('/ai/debug', {
      code,
      error_message: errorMessage,
      language,
      file_path: filePath,
      context,
    });
    return res.data;
  },

  /**
   * Request Gemini to generate code from a natural language specification.
   */
  generateCode: async ({ prompt, language = 'javascript', context = '' }) => {
    const res = await api.post('/ai/generate', {
      prompt,
      language,
      context,
    });
    return res.data;
  },

  /**
   * Request Gemini to suggest optimizations and refactoring improvements.
   */
  improveCode: async ({ code, focus = 'all', language = '', filePath = '', context = '' }) => {
    const res = await api.post('/ai/improve', {
      code,
      focus,
      language,
      file_path: filePath,
      context,
    });
    return res.data;
  },
};

export default aiApi;
