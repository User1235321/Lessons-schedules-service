import { api } from "../../api/client.js";

export function resourceApi(projectId, resource) {
  const base = `/projects/${encodeURIComponent(projectId)}/${resource}`;
  const item = (id) => `${base}/${encodeURIComponent(id)}`;

  return {
    list: () => api.get(base),
    create: (values) => api.post(base, values),
    update: (id, changes) => api.patch(item(id), changes),
    remove: (id) => api.delete(item(id))
  };
}
