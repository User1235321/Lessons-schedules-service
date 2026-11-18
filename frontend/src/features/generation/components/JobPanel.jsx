import { Alert, Box, Button, Chip, LinearProgress, Stack, Typography } from "@mui/material";
import { Link as RouterLink } from "react-router";

import { paths } from "../../../app/paths.js";
import { isCancellable, isFinal, JOB_STATUS } from "../jobStatus.js";

function Progress({ job }) {
  const hasProgress = typeof job.progress === "number";
  return (
    <Box sx={{ mt: 2 }}>
      <LinearProgress
        aria-label="Прогресс расчёта"
        variant={hasProgress ? "determinate" : "indeterminate"}
        value={hasProgress ? Math.min(100, Math.max(0, job.progress)) : undefined}
      />
      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
        {hasProgress
          ? `${Math.round(job.progress)}%`
          : job.status === "QUEUED"
            ? "Ждёт своей очереди"
            : "Процент выполнения пока неизвестен"}
      </Typography>
    </Box>
  );
}

function Outcome({ job }) {
  if (job.status === "COMPLETED") {
    return <Alert severity="success" sx={{ mt: 2 }}>Расчёт завершён.</Alert>;
  }
  if (job.status === "FAILED") {
    return (
      <Alert severity="error" sx={{ mt: 2 }}>
        Расчёт завершился ошибкой.
        {job.error_message ? ` ${job.error_message}` : ""}
      </Alert>
    );
  }
  return (
    <Alert severity="warning" sx={{ mt: 2 }}>
      Расчёт отменён.
    </Alert>
  );
}

function CompletedResults({ projectId, schedules, resultsLoading, resultsError, onRetryResults }) {
  if (resultsLoading || (schedules === null && !resultsError)) {
    return <Typography sx={{ mt: 2 }}>Загружаем результаты расчёта…</Typography>;
  }
  if (resultsError) {
    return (
      <Stack spacing={1} sx={{ mt: 2, alignItems: "flex-start" }}>
        <Alert severity="error">Не удалось загрузить результаты: {resultsError.message}</Alert>
        <Button variant="outlined" onClick={onRetryResults}>Повторить загрузку</Button>
      </Stack>
    );
  }
  if (schedules.length === 0) {
    return <Alert severity="warning" sx={{ mt: 2 }}>Допустимое расписание не найдено.</Alert>;
  }
  return (
    <Button
      sx={{ mt: 2 }}
      variant="contained"
      component={RouterLink}
      to={paths.schedule(projectId, schedules[0].id)}
    >
      Открыть расписание
    </Button>
  );
}

export default function JobPanel({
  projectId,
  job,
  pollError,
  cancelling,
  cancelRequested,
  cancelError,
  schedules,
  resultsLoading,
  resultsError,
  onRetryResults,
  onCancel
}) {
  const status = JOB_STATUS[job.status] ?? { label: job.status, color: "default" };

  return (
    <Box role="status" aria-live="polite" sx={{ mt: 3 }}>
      <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
        <Typography variant="subtitle1">Состояние расчёта:</Typography>
        <Chip label={status.label} color={status.color} />
      </Stack>

      {isFinal(job.status) ? <Outcome job={job} /> : <Progress job={job} />}
      {job.status === "COMPLETED" && (
        <CompletedResults
          projectId={projectId}
          schedules={schedules}
          resultsLoading={resultsLoading}
          resultsError={resultsError}
          onRetryResults={onRetryResults}
        />
      )}

      {isCancellable(job.status) && (
        <Stack direction="row" spacing={2} sx={{ mt: 2, alignItems: "center" }}>
          <Button
            color="error"
            variant="outlined"
            onClick={onCancel}
            disabled={cancelling || cancelRequested}
          >
            Отменить расчёт
          </Button>
          {cancelRequested && (
            <Typography variant="body2" color="text.secondary">
              Отмена запрошена, останавливаем расчёт…
            </Typography>
          )}
        </Stack>
      )}
      {cancelError && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {cancelError.message}
        </Alert>
      )}

      {pollError && !isFinal(job.status) && (
        <Alert severity="warning" sx={{ mt: 2 }}>
          Не удаётся получить состояние расчёта: {pollError.message} Пробуем снова.
        </Alert>
      )}
    </Box>
  );
}
