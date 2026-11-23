import { useState } from "react";
import { Alert, Box, Button, Stack, ToggleButton, ToggleButtonGroup, Typography } from "@mui/material";
import { Link as RouterLink, useParams } from "react-router";

import { paths } from "../../../app/paths.js";
import ErrorState from "../../../components/ErrorState.jsx";
import LoadingState from "../../../components/LoadingState.jsx";
import { useAuth } from "../../auth/AuthProvider.jsx";
import ScheduleTable from "../components/ScheduleTable.jsx";
import { useSchedule } from "../useSchedule.js";

export default function ScheduleViewerPage() {
  const { projectId, scheduleId: routeScheduleId } = useParams();
  const { user } = useAuth();
  const scheduleId = routeScheduleId.toLowerCase();
  const [week, setWeek] = useState("ODD");
  const { schedule, variants, error, variantError, retry, retryVariants } =
    useSchedule(user.id, projectId.toLowerCase(), scheduleId);
  const position = variants.findIndex(({ id }) => id === scheduleId);

  if (!schedule) {
    if (error) {
      return <ErrorState title="Не удалось открыть расписание" message={error} onRetry={retry} />;
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
      {variantError && (
        <Alert severity="warning" action={<Button color="inherit" onClick={retryVariants}>Повторить</Button>}>
          Не удалось загрузить варианты расчёта. {variantError}
        </Alert>
      )}
      {variants.length > 1 && position >= 0 && (
        <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap" }}>
          <Typography sx={{ mr: 1 }}>Вариант {schedule.result_index} из {variants.length}</Typography>
          {position > 0 && (
            <Button component={RouterLink} to={paths.schedule(projectId, variants[position - 1].id)}>
              Предыдущий вариант
            </Button>
          )}
          {position + 1 < variants.length && (
            <Button component={RouterLink} to={paths.schedule(projectId, variants[position + 1].id)}>
              Следующий вариант
            </Button>
          )}
        </Stack>
      )}
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
