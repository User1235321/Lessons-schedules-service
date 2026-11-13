import { useCallback, useEffect, useState } from "react";

import { resourceApi } from "./api.js";

// Коллекция проекта, на которую ссылаются формы другого раздела. items === null, пока грузится
export function useResourceList(projectId, resource) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setItems(await resourceApi(projectId, resource).list());
    } catch (loadError) {
      setError(loadError);
    }
  }, [projectId, resource]);

  useEffect(() => {
    load();
  }, [load]);

  return { items, error, reload: load };
}

// Дисциплины проекта: на них ссылаются возможности преподавателей и аудиторий, а также нагрузка
export function useSubjects(projectId) {
  const { items, error, reload } = useResourceList(projectId, "subjects");
  return { subjects: items, error, reload };
}
