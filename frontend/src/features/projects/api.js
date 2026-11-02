import { api } from "../../api/client.js";

// Контракт из HLD 10. Проект в ответе: { id, name, created_at, updated_at }
export const projectsApi = {
  list: () => api.get("/projects"),
  get: (projectId) => api.get(`/projects/${encodeURIComponent(projectId)}`),
  create: ({ name }) => api.post("/projects", { name }),
  remove: (projectId) => api.delete(`/projects/${encodeURIComponent(projectId)}`)
};
