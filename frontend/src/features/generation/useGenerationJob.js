import { useEffect, useState } from "react";

import { generationApi } from "./api.js";
import { isFinal } from "./jobStatus.js";

// Состояние обновляется не реже раза в 2 с (F_Gen_9, NF_Perf_3)
export const POLL_INTERVAL_MS = 2000;

// Расчёт идёт долго, а страница размонтируется при переключении вкладок проекта,
// поэтому id задания хранится в sessionStorage: отдельно для каждого проекта и до закрытия вкладки
const storageKey = (projectId) => `generation-job:${projectId}`;

function readStoredJobId(projectId) {
  try {
    return sessionStorage.getItem(storageKey(projectId));
  } catch {
    return null;
  }
}

function storeJobId(projectId, jobId) {
  try {
    if (jobId === null) {
      sessionStorage.removeItem(storageKey(projectId));
    } else {
      sessionStorage.setItem(storageKey(projectId), jobId);
    }
  } catch {
    // Без хранилища расчёт работает, но после смены вкладки его состояние придётся запустить заново
  }
}

// Задание расчёта текущего проекта: запуск, состояние, отмена и восстановление после возврата
export function useGenerationJob(projectId) {
  const [job, setJob] = useState(null);
  const [restoring, setRestoring] = useState(() => readStoredJobId(projectId) !== null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState(null);
  const [pollError, setPollError] = useState(null);
  const [cancelling, setCancelling] = useState(false);
  const [cancelRequested, setCancelRequested] = useState(false);
  const [cancelError, setCancelError] = useState(null);
  // Растёт после неудачного опроса, чтобы эффект запланировал следующий
  const [attempt, setAttempt] = useState(0);

  const start = async (options) => {
    setStartError(null);
    setPollError(null);
    setCancelError(null);
    setCancelRequested(false);
    setStarting(true);
    try {
      const { job_id: id, status } = await generationApi.start(projectId, options);
      storeJobId(projectId, id);
      setJob({ id, status, progress: null, error_message: null });
    } catch (error) {
      setStartError(error);
    } finally {
      setStarting(false);
    }
  };

  useEffect(() => {
    const id = readStoredJobId(projectId);
    if (id === null) {
      return undefined;
    }

    let stopped = false;
    generationApi
      .get(id)
      .then((restored) => {
        if (!stopped) {
          setJob(restored);
        }
      })
      .catch((error) => {
        if (stopped) {
          return;
        }
        if (error.code === "NOT_FOUND") {
          storeJobId(projectId, null);
        } else {
          // Сеть недоступна: задание, скорее всего, есть. Следим за ним, пока не ответит сервер
          setJob({ id, status: "UNKNOWN", progress: null, error_message: null });
          setPollError(error);
        }
      })
      .finally(() => {
        if (!stopped) {
          setRestoring(false);
        }
      });

    return () => {
      stopped = true;
    };
  }, [projectId]);

  const cancel = async () => {
    setCancelError(null);
    setCancelling(true);
    try {
      const next = await generationApi.cancel(job.id);
      setJob(next);
      // Воркер может остановиться не сразу: пока статус не конечный, отмена только запрошена
      setCancelRequested(!isFinal(next.status));
    } catch (error) {
      setCancelError(error);
      if (error.code === "JOB_NOT_CANCELLABLE") {
        // Расчёт успел закончиться: показываем его итог вместо устаревшего статуса
        try {
          setJob(await generationApi.get(job.id));
        } catch {
          // Итог подтянет обычный опрос
        }
      }
    } finally {
      setCancelling(false);
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
          storeJobId(projectId, null);
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

  return {
    job,
    restoring,
    starting,
    startError,
    pollError,
    cancelling,
    cancelRequested,
    cancelError,
    start,
    cancel
  };
}
