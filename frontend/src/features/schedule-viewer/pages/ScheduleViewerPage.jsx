import { useEffect, useState } from "react";
import { Box, Button, Stack, ToggleButton, ToggleButtonGroup, Typography } from "@mui/material";
import { Link as RouterLink, useParams } from "react-router";

import { api } from "../../../api/client.js";
import { paths } from "../../../app/paths.js";
import ErrorState from "../../../components/ErrorState.jsx";
import LoadingState from "../../../components/LoadingState.jsx";
import ScheduleTable from "../components/ScheduleTable.jsx";

export default function ScheduleViewerPage() {
  const { projectId, scheduleId: routeScheduleId } = useParams();
  const scheduleId = routeScheduleId.toLowerCase();
  const [week, setWeek] = useState("ODD");
  const [opened, setOpened] = useState(null);
  const [failure, setFailure] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const schedule = opened?.id === scheduleId ? opened : null;

  useEffect(() => {
    if (schedule) return;
    const controller = new AbortController();
    api.get(`/schedules/${encodeURIComponent(scheduleId)}`, { signal: controller.signal })
      .then((result) => {
        if (controller.signal.aborted) return;
        if (result.project_id !== projectId.toLowerCase()) {
          throw new Error("Расписание не найдено в этом проекте.");
        }
        setOpened(result);
      })
      .catch((error) => {
        if (!controller.signal.aborted) setFailure({ id: scheduleId, message: error.message });
      });
    return () => controller.abort();
  }, [projectId, scheduleId, schedule, attempt]);

  if (!schedule) {
    if (failure?.id === scheduleId) {
      return <ErrorState title="Не удалось открыть расписание" message={failure.message} onRetry={() => {
        setFailure(null);
        setAttempt((value) => value + 1);
      }} />;
    }
    return <LoadingState label="Открываем расписание" />;
  }

  return (
    <Stack spacing={2} sx={{ py: 2 }}>
      <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between", gap: 2, flexWrap: "wrap" }}>
        <Typography component="h2" variant="h5">Просмотр расписания</Typography>
        <Button component={RouterLink} to={paths.scheduleEdit(projectId, scheduleId)} variant="outlined">
          Редактировать
        </Button>
      </Stack>
      <Box>
        <ToggleButtonGroup exclusive size="small" value={week} aria-label="Учебная неделя"
          onChange={(_, value) => { if (value) setWeek(value); }}>
          <ToggleButton value="ODD">Нечётная неделя</ToggleButton>
          <ToggleButton value="EVEN">Чётная неделя</ToggleButton>
        </ToggleButtonGroup>
      </Box>
      <ScheduleTable entries={schedule.entries} week={week} />
    </Stack>
  );
}
