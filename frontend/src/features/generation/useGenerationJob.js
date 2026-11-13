import { useState } from "react";

import { generationApi } from "./api.js";

// Задание расчёта текущего проекта: запуск и состояние
export function useGenerationJob(projectId) {
  const [job, setJob] = useState(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState(null);

  const start = async (options) => {
    setStartError(null);
    setStarting(true);
    try {
      const { job_id: id, status } = await generationApi.start(projectId, options);
      setJob({ id, status, progress: null, error_message: null });
    } catch (error) {
      setStartError(error);
    } finally {
      setStarting(false);
    }
  };

  return { job, starting, startError, start };
}
