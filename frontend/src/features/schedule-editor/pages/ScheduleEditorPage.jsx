import { useEffect, useRef, useState } from "react";
import { Alert, Button, Stack, Typography } from "@mui/material";
import { Link as RouterLink, useParams } from "react-router";

import { paths } from "../../../app/paths.js";
import ErrorState from "../../../components/ErrorState.jsx";
import LoadingState from "../../../components/LoadingState.jsx";
import { resourceApi } from "../../project-editor/api.js";
import EntryTable from "../EntryTable.jsx";
import EntryDialog from "../EntryDialog.jsx";
import { scheduleEditorApi } from "../api.js";

function Editor({ projectId, scheduleId }) {
  const [data, setData] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const [editing, setEditing] = useState(null);
  const [saved, setSaved] = useState(false);
  const [conflicts, setConflicts] = useState(null);
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState(null);
  const [checkAttempt, setCheckAttempt] = useState(0);
  const validation = useRef(null);
  const entries = data?.entries;

  useEffect(() => {
    if (!entries) return;
    const controller = new AbortController();
    validation.current = controller;
    setChecking(true);
    setCheckError(null);
    scheduleEditorApi.validate(scheduleId, controller.signal)
      .then((result) => { if (!controller.signal.aborted) setConflicts(result.conflicts); })
      .catch((error) => { if (!controller.signal.aborted) setCheckError(error); })
      .finally(() => { if (!controller.signal.aborted) setChecking(false); });
    return () => controller.abort();
  }, [scheduleId, entries, checkAttempt]);

  useEffect(() => {
    const controller = new AbortController();
    setLoadError(null);
    async function load() {
      const [schedule, rooms, teachers] = await Promise.all([
        scheduleEditorApi.get(scheduleId, controller.signal),
        resourceApi(projectId, "rooms").list(),
        resourceApi(projectId, "teachers").list()
      ]);
      if (controller.signal.aborted) return;
      if (schedule.project_id !== projectId.toLowerCase()) throw new Error("Расписание не найдено в этом проекте.");
      setData({ entries: schedule.entries, rooms, teachers });
    }
    load().catch((error) => { if (!controller.signal.aborted) setLoadError(error); });
    return () => controller.abort();
  }, [projectId, scheduleId, attempt]);

  async function save(changes) {
    const { entry, conflicts: found } = await scheduleEditorApi.updateEntry(scheduleId, editing.id, changes);
    validation.current?.abort();
    setConflicts(found);
    setData((current) => ({
      ...current, entries: current.entries.map((item) => item.id === entry.id ? entry : item)
    }));
    setEditing(null);
    setSaved(true);
  }

  return (
    <Stack spacing={2} sx={{ py: 2 }}>
      <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between", gap: 2, flexWrap: "wrap" }}>
        <Typography component="h2" variant="h5">Редактирование расписания</Typography>
        <Button component={RouterLink} to={paths.schedule(projectId, scheduleId)}>Вернуться к просмотру</Button>
      </Stack>
      {loadError ? (
        <ErrorState title="Не удалось открыть редактор" message={loadError.message} onRetry={() => setAttempt((n) => n + 1)} />
      ) : !data ? <LoadingState label="Загружаем занятия" /> : (
        <>
          {saved && <Alert role="status" severity="success">Изменения сохранены.</Alert>}
          <Stack direction="row" sx={{ alignItems: "center", flexWrap: "wrap", gap: 1 }}>
            <Button variant="outlined" disabled={checking} onClick={() => setCheckAttempt((n) => n + 1)}>
              Проверить расписание
            </Button>
            {checking && <Typography role="status">Проверяем расписание…</Typography>}
            {!checking && !checkError && conflicts?.length === 0 && (
              <Typography role="status">Конфликтов нет.</Typography>
            )}
          </Stack>
          {checkError && <Alert severity="error">Не удалось проверить расписание. {checkError.message}</Alert>}
          {conflicts?.length > 0 && (
            <Alert severity="warning">
              Обнаружено конфликтов: {conflicts.length}
              {conflicts.filter((item) => !item.entry_ids.length).map((item, index) =>
                <div key={index}>{item.message}</div>)}
            </Alert>
          )}
          {data.entries.length === 0 ? <Typography>В расписании пока нет занятий.</Typography> : (
            <EntryTable entries={entries} conflicts={conflicts} onEdit={(item) => {
              setSaved(false);
              setEditing(item);
            }} />
          )}
          {editing && <EntryDialog key={editing.id} entry={editing} rooms={data.rooms} teachers={data.teachers}
            onSave={save} onClose={() => setEditing(null)} />}
        </>
      )}
    </Stack>
  );
}

export default function ScheduleEditorPage() {
  const { projectId, scheduleId } = useParams();
  return <Editor key={scheduleId} projectId={projectId} scheduleId={scheduleId} />;
}
