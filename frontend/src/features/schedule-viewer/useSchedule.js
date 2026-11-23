import { useEffect, useState } from "react";

import { api } from "../../api/client.js";
import { generationApi } from "../generation/api.js";

export function useSchedule(projectId, scheduleId) {
  const [opened, setOpened] = useState(null);
  const [variants, setVariants] = useState([]);
  const [failure, setFailure] = useState(null);
  const [variantError, setVariantError] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const [variantAttempt, setVariantAttempt] = useState(0);

  // API возвращает полные расписания для всех вариантов одного расчёта.
  const schedule = opened?.id === scheduleId ? opened : variants.find(({ id }) => id === scheduleId);
  const jobId = schedule?.job_id;

  useEffect(() => {
    if (schedule) return;
    const controller = new AbortController();
    setFailure(null);
    api.get(`/schedules/${encodeURIComponent(scheduleId)}`, { signal: controller.signal })
      .then((result) => {
        if (controller.signal.aborted) return;
        if (result.project_id !== projectId) throw new Error("Расписание не найдено в этом проекте.");
        setOpened(result);
      })
      .catch((error) => {
        if (!controller.signal.aborted) setFailure({ id: scheduleId, message: error.message });
      });
    return () => controller.abort();
  }, [projectId, scheduleId, schedule, attempt]);

  useEffect(() => {
    if (!jobId) return;
    const controller = new AbortController();
    setVariantError(null);
    generationApi.schedules(jobId, { signal: controller.signal })
      .then((results) => {
        if (!controller.signal.aborted) {
          setVariants(results.filter((item) => item.project_id === projectId && item.job_id === jobId)
            .sort((a, b) => a.result_index - b.result_index));
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) setVariantError({ jobId, message: error.message });
      });
    return () => controller.abort();
  }, [projectId, jobId, variantAttempt]);

  return {
    schedule,
    variants: jobId && variants[0]?.job_id === jobId ? variants : [],
    error: failure?.id === scheduleId ? failure.message : null,
    variantError: variantError && variantError.jobId === jobId ? variantError.message : null,
    retry: () => setAttempt((n) => n + 1),
    retryVariants: () => setVariantAttempt((n) => n + 1)
  };
}
