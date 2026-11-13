import { api } from "../../api/client.js";

// Контракт из HLD 10.7. Запуск отвечает 202 с { job_id, status: "QUEUED" },
// состояние и отмена — Job: { id, project_id, job_type, status, progress, error_message }
export const generationApi = {
  start: (projectId, { resultMode, topN }) =>
    api.post(`/projects/${encodeURIComponent(projectId)}/generation-jobs`, {
      result_mode: resultMode,
      top_n: resultMode === "TOP_N" ? topN : null
    }),
  get: (jobId) => api.get(`/generation-jobs/${encodeURIComponent(jobId)}`),
  cancel: (jobId) => api.post(`/generation-jobs/${encodeURIComponent(jobId)}/cancel`)
};
