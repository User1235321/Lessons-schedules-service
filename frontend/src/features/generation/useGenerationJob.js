import { useEffect, useRef, useState } from "react";

import { generationApi } from "./api.js";
import { isFinal } from "./jobStatus.js";

export const POLL_INTERVAL_MS = 2000;

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
    return;
  }
}

export function useGenerationJob(projectId) {
  const [job, setJob] = useState(null);
  const [restoring, setRestoring] = useState(() => readStoredJobId(projectId) !== null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState(null);
  const [pollError, setPollError] = useState(null);
  const [cancelling, setCancelling] = useState(false);
  const [cancelRequested, setCancelRequested] = useState(false);
  const [cancelError, setCancelError] = useState(null);
  const [schedules, setSchedules] = useState(null);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [resultsError, setResultsError] = useState(null);
  const [resultsAttempt, setResultsAttempt] = useState(0);
  const requestVersion = useRef(0);

  const start = async (options) => {
    requestVersion.current += 1;
    setStartError(null);
    setPollError(null);
    setCancelError(null);
    setCancelRequested(false);
    setSchedules(null);
    setResultsError(null);
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
    requestVersion.current += 1;
    setCancelError(null);
    setCancelling(true);
    try {
      const next = await generationApi.cancel(job.id);
      setJob(next);
      setCancelRequested(!isFinal(next.status));
    } catch (error) {
      setCancelError(error);
      if (error.code === "JOB_NOT_CANCELLABLE") {
        try {
          const next = await generationApi.get(job.id);
          setJob(next);
          setCancelRequested(false);
        } catch (refreshError) {
          setCancelError(refreshError);
        }
      }
    } finally {
      setCancelling(false);
    }
  };

  const shouldPoll = job !== null && !isFinal(job.status);

  useEffect(() => {
    if (!shouldPoll) {
      return undefined;
    }

    const jobId = job.id;
    let active = true;
    let timer;

    async function poll() {
      const startedAt = Date.now();
      const version = requestVersion.current;
      let keepPolling = true;

      try {
        const next = await generationApi.get(jobId);
        if (active && requestVersion.current === version) {
          setPollError(null);
          setJob(next);
          keepPolling = !isFinal(next.status);
        }
      } catch (error) {
        if (active && requestVersion.current === version) {
          if (error.code === "NOT_FOUND") {
            storeJobId(projectId, null);
            setJob(null);
            setPollError(error);
            keepPolling = false;
          } else {
            setPollError(error);
          }
        }
      } finally {
        if (active && keepPolling) {
          const elapsed = Date.now() - startedAt;
          timer = setTimeout(poll, Math.max(0, POLL_INTERVAL_MS - elapsed));
        }
      }
    }

    timer = setTimeout(poll, POLL_INTERVAL_MS);

    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [projectId, job?.id, shouldPoll]);

  useEffect(() => {
    if (job?.status !== "COMPLETED") {
      return undefined;
    }

    let active = true;
    setSchedules(null);
    setResultsError(null);
    setResultsLoading(true);

    generationApi
      .schedules(job.id)
      .then((next) => {
        if (active) {
          setSchedules(next);
        }
      })
      .catch((error) => {
        if (active) {
          setResultsError(error);
        }
      })
      .finally(() => {
        if (active) {
          setResultsLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [job?.id, job?.status, resultsAttempt]);

  return {
    job,
    restoring,
    starting,
    startError,
    pollError,
    cancelling,
    cancelRequested,
    cancelError,
    schedules,
    resultsLoading,
    resultsError,
    start,
    cancel,
    retryResults: () => setResultsAttempt((attempt) => attempt + 1)
  };
}
