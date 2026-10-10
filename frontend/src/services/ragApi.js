import api from './api';

export const ragApi = {
  /**
   * Submit a question to the project RAG engine.
   */
  askQuestion: async (projectId, question, conversationId = null, topK = 5) => {
    const res = await api.post(`/rag/${projectId}/query`, {
      question,
      conversation_id: conversationId,
      top_k: topK,
    });
    return res.data;
  },

  /**
   * Search indexed code snippets using vector embeddings.
   */
  searchCodebase: async (projectId, query, topK = 8) => {
    const res = await api.post(`/rag/${projectId}/search`, {
      query,
      top_k: topK,
    });
    return res.data;
  },

  /**
   * Reindex project codebase for RAG vector search.
   */
  reindexCodebase: async (projectId) => {
    const res = await api.post(`/rag/${projectId}/index`);
    return res.data;
  },

  /**
   * List all saved conversations for a project.
   */
  listConversations: async (projectId) => {
    const res = await api.get(`/rag/${projectId}/conversations`);
    return res.data;
  },

  /**
   * Create a new conversation thread for a project.
   */
  createConversation: async (projectId, title = 'Codebase Discussion') => {
    const res = await api.post(`/rag/${projectId}/conversations`, { title });
    return res.data;
  },

  /**
   * Get full message history and citations for a conversation.
   */
  getConversation: async (projectId, convId) => {
    const res = await api.get(`/rag/${projectId}/conversations/${convId}`);
    return res.data;
  },

  /**
   * Rename a conversation title.
   */
  renameConversation: async (projectId, convId, title) => {
    const res = await api.patch(`/rag/${projectId}/conversations/${convId}`, { title });
    return res.data;
  },

  /**
   * Delete a conversation thread.
   */
  deleteConversation: async (projectId, convId) => {
    const res = await api.delete(`/rag/${projectId}/conversations/${convId}`);
    return res.data;
  },

  explainCode: async (projectId, code, filePath = '', language = '') => {
    const res = await api.post(`/rag/${projectId}/explain`, {
      code,
      file_path: filePath,
      language,
    });
    return res.data;
  },

  debugCode: async (projectId, code, errorMessage = '', filePath = '') => {
    const res = await api.post(`/rag/${projectId}/debug`, {
      code,
      error_message: errorMessage,
      file_path: filePath,
    });
    return res.data;
  },

  reviewCode: async (projectId, params) => {
    const payload = typeof params === 'string' 
      ? { code: params, file_path: arguments[2] || '' } 
      : {
          code: params.code || '',
          file_path: params.filePath || params.file_path || '',
          review_type: params.reviewType || params.review_type || 'comprehensive',
        };
    const res = await api.post(`/rag/${projectId}/review`, payload);
    return res.data;
  },

  generateTests: async (projectId, params) => {
    const payload = typeof params === 'string'
      ? { code: params, file_path: arguments[2] || '', language: arguments[3] || '' }
      : {
          code: params.code || '',
          file_path: params.filePath || params.file_path || '',
          function_name: params.functionName || params.function_name || '',
          framework: params.framework || '',
        };
    const res = await api.post(`/rag/${projectId}/generate-tests`, payload);
    return res.data;
  },

  /**
   * Generates a grounded README and project documentation.
   */
  generateDocs: async (projectId, customInstructions = '') => {
    const res = await api.post(`/rag/${projectId}/generate-docs`, {
      custom_instructions: customInstructions,
    });
    return res.data;
  },

  /**
   * Saves previewed documentation to project repository as a source file.
   */
  saveDocs: async (projectId, filename = 'README.md', content = '') => {
    const res = await api.post(`/rag/${projectId}/save-docs`, {
      filename,
      content,
    });
    return res.data;
  },
};

export default ragApi;

