import { api } from "../../api/client.js";

const path = (id) => `/schedules/${encodeURIComponent(id)}`;

export const scheduleEditorApi = {
  get: (id, signal) => api.get(path(id), { signal }),
  updateEntry: (id, entryId, changes) =>
    api.patch(`${path(id)}/entries/${encodeURIComponent(entryId)}`, changes)
};
