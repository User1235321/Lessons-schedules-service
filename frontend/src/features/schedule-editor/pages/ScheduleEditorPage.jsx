import { useEffect, useState } from "react";
import {
  Alert, Button, Paper, Stack, Table, TableBody, TableCell, TableContainer, TableHead,
  TableRow, Typography
} from "@mui/material";
import { Link as RouterLink, useParams } from "react-router";

import { paths } from "../../../app/paths.js";
import ErrorState from "../../../components/ErrorState.jsx";
import LoadingState from "../../../components/LoadingState.jsx";
import { resourceApi } from "../../project-editor/api.js";
import { formatInterval, lessonFormatLabel, WEEKDAYS } from "../../project-editor/intervals.js";
import EntryDialog from "../EntryDialog.jsx";
import { scheduleEditorApi } from "../api.js";

const days = WEEKDAYS.map(({ value }) => value);

function compareEntries(a, b) {
  return (a.week === "EVEN") - (b.week === "EVEN") ||
    days.indexOf(a.weekday) - days.indexOf(b.weekday) || a.start_time.localeCompare(b.start_time);
}

function Editor({ projectId, scheduleId }) {
  const [data, setData] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const [editing, setEditing] = useState(null);
  const [saved, setSaved] = useState(false);

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
    const { entry } = await scheduleEditorApi.updateEntry(scheduleId, editing.id, changes);
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
          {data.entries.length === 0 ? <Typography>В расписании пока нет занятий.</Typography> : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small" aria-label="Занятия для редактирования">
                <TableHead><TableRow>
                  {["День и время", "Занятие", "Формат и аудитория", "Преподаватели", "Действие"].map((label) =>
                    <TableCell key={label}>{label}</TableCell>)}
                </TableRow></TableHead>
                <TableBody>
                  {[...data.entries].sort(compareEntries).map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>{formatInterval({ week: item.week, day: item.weekday, start: item.start_time, end: item.end_time })}</TableCell>
                      <TableCell>
                        <Typography variant="body2">{item.subject_name || "Без названия"}</Typography>
                        {item.participant_label}
                      </TableCell>
                      <TableCell>{[lessonFormatLabel(item.lesson_format), item.room_name].filter(Boolean).join(" · ") || "—"}</TableCell>
                      <TableCell>{item.teachers.map((teacher) => teacher.display_name).join(", ") || "—"}</TableCell>
                      <TableCell>
                        <Button onClick={() => { setSaved(false); setEditing(item); }}>Изменить</Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
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
