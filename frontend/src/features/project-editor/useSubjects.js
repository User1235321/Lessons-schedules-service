import { useCallback, useEffect, useState } from "react";

import { resourceApi } from "./api.js";

export function useSubjects(projectId) {
  const [subjects, setSubjects] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setSubjects(await resourceApi(projectId, "subjects").list());
    } catch (loadError) {
      setError(loadError);
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  return { subjects, error, reload: load };
}
