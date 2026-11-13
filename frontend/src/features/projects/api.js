import { api } from "../../api/client.js";

// Контракт из HLD 10. Проект в ответе: { id, name, cycle, time_mode, duration_mode, created_at, updated_at }.
// В PATCH присланный блок настроек заменяется целиком, отсутствующий не меняется
export const projectsApi = {
  list: () => api.get("/projects"),
  get: (projectId) => api.get(`/projects/${encodeURIComponent(projectId)}`),
  create: ({ name }) => api.post("/projects", { name }),
  update: (projectId, changes) => api.patch(`/projects/${encodeURIComponent(projectId)}`, changes),
  remove: (projectId) => api.delete(`/projects/${encodeURIComponent(projectId)}`)
};
