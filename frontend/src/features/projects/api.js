import { api } from "../../api/client.js";

export const projectsApi = {
  list: () => api.get("/projects"),
  get: (projectId) => api.get(`/projects/${encodeURIComponent(projectId)}`),
  create: ({ name }) => api.post("/projects", { name }),
  update: (projectId, changes) => api.patch(`/projects/${encodeURIComponent(projectId)}`, changes),
  remove: (projectId) => api.delete(`/projects/${encodeURIComponent(projectId)}`)
};
