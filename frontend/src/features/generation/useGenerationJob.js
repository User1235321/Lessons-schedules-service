import { useEffect, useState } from "react";

import { generationApi } from "./api.js";
import { isFinal } from "./jobStatus.js";

// Состояние обновляется не реже раза в 2 с (F_Gen_9, NF_Perf_3)
export const POLL_INTERVAL_MS = 2000;

// Задание расчёта текущего проекта: запуск и состояние
export function useGenerationJob(projectId) {
  const [job, setJob] = useState(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState(null);
  const [pollError, setPollError] = useState(null);
  // Растёт после неудачного опроса, чтобы эффект запланировал следующий
  const [attempt, setAttempt] = useState(0);

  const start = async (options) => {
    setStartError(null);
    setPollError(null);
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

  useEffect(() => {
    if (!job || isFinal(job.status)) {
      return undefined;
    }

    let stopped = false;
    const timer = setTimeout(async () => {
      try {
        const next = await generationApi.get(job.id);
        if (!stopped) {
          setPollError(null);
          setJob(next);
        }
      } catch (error) {
        if (stopped) {
          return;
        }
        if (error.code === "NOT_FOUND") {
          // Задание исчезло на сервере: следить больше не за чем
          setJob(null);
          setPollError(error);
        } else {
          // Сеть или сервер недоступны ненадолго: показываем и пробуем снова
          setPollError(error);
          setAttempt((count) => count + 1);
        }
      }
    }, POLL_INTERVAL_MS);

    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [job, attempt]);

  return { job, starting, startError, pollError, start };
}
