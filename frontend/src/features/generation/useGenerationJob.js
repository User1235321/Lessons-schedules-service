import { useEffect, useState } from "react";

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
      setCancelRequested(!isFinal(next.status));
    } catch (error) {
      setCancelError(error);
      if (error.code === "JOB_NOT_CANCELLABLE") {
        try {
          setJob(await generationApi.get(job.id));
        } catch {
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
          storeJobId(projectId, null);
          setJob(null);
          setPollError(error);
        } else {
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
