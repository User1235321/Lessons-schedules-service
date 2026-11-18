import { Alert, Box, Button, Chip, LinearProgress, Stack, Typography } from "@mui/material";
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

export default function JobPanel({
  job,
  pollError,
  cancelling,
  cancelRequested,
  cancelError,
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
