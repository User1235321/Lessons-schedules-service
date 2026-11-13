import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  FormControl,
  FormControlLabel,
  FormLabel,
  Radio,
  RadioGroup,
  Stack,
  TextField,
  Typography
} from "@mui/material";
import { useParams } from "react-router";

import JobPanel from "../components/JobPanel.jsx";
import { isFinal } from "../jobStatus.js";
import { useGenerationJob } from "../useGenerationJob.js";

const DEFAULT_TOP_N = "5";

// Ошибка поля top_n или null. N — целое больше нуля (F_Gen_4)
function validateTopN(value) {
  return /^\d+$/.test(value.trim()) && Number(value) > 0
    ? null
    : "Укажите целое число вариантов больше нуля";
}

export default function GenerationPage() {
  const { projectId } = useParams();
  // key: при смене проекта состояние расчёта прошлого проекта не должно остаться
  return <GenerationView key={projectId} projectId={projectId} />;
}

function GenerationView({ projectId }) {
  const {
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
  } = useGenerationJob(projectId);
  // Пока расчёт идёт или его состояние уточняется, запустить второй нельзя
  const running = restoring || (job !== null && !isFinal(job.status));
  const [mode, setMode] = useState("SINGLE");
  const [topN, setTopN] = useState(DEFAULT_TOP_N);
  const [topNError, setTopNError] = useState(null);

  const handleSubmit = (event) => {
    event.preventDefault();
    const error = mode === "TOP_N" ? validateTopN(topN) : null;
    setTopNError(error);
    if (!error) {
      start({ resultMode: mode, topN: Number(topN) });
    }
  };

  // Ошибка сервера по полю top_n показывается у поля, остальное — над формой
  const serverTopNError =
    startError?.code === "INVALID_VALUE" && startError.details?.field === "top_n";

  return (
    <Box sx={{ py: 2 }}>
      <Typography component="h2" variant="h5" sx={{ mb: 1 }}>
        Построение расписания
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Выберите, сколько вариантов нужно, и запустите расчёт. Состояние обновляется само.
      </Typography>

      <Box component="form" noValidate onSubmit={handleSubmit}>
        <Stack spacing={2} sx={{ maxWidth: 480 }}>
          {startError && !serverTopNError && <Alert severity="error">{startError.message}</Alert>}
          {!job && pollError && <Alert severity="error">{pollError.message}</Alert>}

          <FormControl>
            <FormLabel id="result-mode-label">Сколько вариантов построить</FormLabel>
            <RadioGroup
              aria-labelledby="result-mode-label"
              value={mode}
              onChange={(event) => setMode(event.target.value)}
            >
              <FormControlLabel
                value="SINGLE"
                control={<Radio />}
                label="Один оптимальный вариант"
              />
              <FormControlLabel value="TOP_N" control={<Radio />} label="TOP-N лучших вариантов" />
            </RadioGroup>
          </FormControl>

          {mode === "TOP_N" && (
            <TextField
              label="Число вариантов (N)"
              value={topN}
              onChange={(event) => {
                setTopN(event.target.value);
                setTopNError(null);
              }}
              error={Boolean(topNError) || serverTopNError}
              helperText={topNError ?? (serverTopNError ? startError.message : null)}
              slotProps={{ htmlInput: { inputMode: "numeric" } }}
            />
          )}

          <Box>
            <Button type="submit" variant="contained" disabled={starting || running}>
              Запустить расчёт
            </Button>
          </Box>
        </Stack>
      </Box>

      {job && (
        <JobPanel
          job={job}
          projectId={projectId}
          pollError={pollError}
          cancelling={cancelling}
          cancelRequested={cancelRequested}
          cancelError={cancelError}
          onCancel={cancel}
        />
      )}
    </Box>
  );
}
