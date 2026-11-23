import { api } from "../../api/client.js";

export const generationApi = {
  start: (projectId, { resultMode, topN }) =>
    api.post(`/projects/${encodeURIComponent(projectId)}/generation-jobs`, {
      result_mode: resultMode,
      top_n: resultMode === "TOP_N" ? topN : null
    }),
  get: (jobId) => api.get(`/generation-jobs/${encodeURIComponent(jobId)}`),
  schedules: (jobId, options) => api.get(`/generation-jobs/${encodeURIComponent(jobId)}/schedules`, options),
  cancel: (jobId) => api.post(`/generation-jobs/${encodeURIComponent(jobId)}/cancel`)
};
