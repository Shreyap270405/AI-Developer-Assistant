import { createContext, useContext, useState, useCallback } from 'react';
import { createProject, listProjects, deleteProject, updateProject } from '../services/projectApi';

const ProjectContext = createContext(null);

export function ProjectProvider({ children }) {
  const [projects, setProjects] = useState([]);
  const [activeProject, setActiveProject] = useState(null);
  const [loadingProjects, setLoadingProjects] = useState(false);

  const fetchProjects = useCallback(async () => {
    setLoadingProjects(true);
    try {
      const data = await listProjects();
      const list = data.projects || [];
      setProjects(list);

      let savedId = null;
      try {
        savedId = localStorage.getItem('activeProjectId');
      } catch (_) {}

      setActiveProject((current) => {
        if (current) {
          const fresh = list.find((p) => p.id === current.id);
          if (fresh) return fresh;
        }
        if (savedId) {
          const matched = list.find((p) => p.id === Number(savedId));
          if (matched) return matched;
        }
        return list[0] ?? null;
      });
      return list;
    } catch (err) {
      console.warn('Could not fetch projects:', err.message);
      return [];
    } finally {
      setLoadingProjects(false);
    }
  }, []);

  const addProject = useCallback(async (name, description) => {
    const data = await createProject(name, description);
    setProjects((prev) => [data.project, ...prev.filter((p) => p.id !== data.project.id)]);
    return data.project;
  }, []);

  const removeProject = useCallback(async (projectId) => {
    await deleteProject(projectId);
    setProjects((prev) => prev.filter((p) => p.id !== projectId));
    setActiveProject((current) => {
      if (current?.id === projectId) {
        try {
          localStorage.removeItem('activeProjectId');
        } catch (_) {}
        return null;
      }
      return current;
    });
  }, []);

  const renameProject = useCallback(async (projectId, newName) => {
    const data = await updateProject(projectId, { name: newName });
    setProjects((prev) =>
      prev.map((p) => (p.id === projectId ? { ...p, name: newName } : p))
    );
    setActiveProject((current) => {
      if (current?.id === projectId) return { ...current, name: newName };
      return current;
    });
    return data.project;
  }, []);

  const selectProject = useCallback((projectOrId) => {
    if (!projectOrId) {
      setActiveProject(null);
      try {
        localStorage.removeItem('activeProjectId');
      } catch (_) {}
      return;
    }
    if (typeof projectOrId === 'object') {
      setActiveProject(projectOrId);
      try {
        localStorage.setItem('activeProjectId', String(projectOrId.id));
      } catch (_) {}
    } else {
      setProjects((prev) => {
        const found = prev.find((p) => p.id === Number(projectOrId));
        if (found) {
          setActiveProject(found);
          try {
            localStorage.setItem('activeProjectId', String(found.id));
          } catch (_) {}
        }
        return prev;
      });
    }
  }, []);

  return (
    <ProjectContext.Provider
      value={{
        projects,
        activeProject,
        loadingProjects,
        fetchProjects,
        addProject,
        removeProject,
        renameProject,
        selectProject,
      }}
    >
      {children}
    </ProjectContext.Provider>
  );
}

export function useProject() {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error('useProject must be used inside ProjectProvider');
  return ctx;
}
