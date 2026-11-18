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
const MAX_TOP_N = 2_147_483_647;

function validateTopN(value) {
  const count = Number(value);
  if (!/^\d+$/.test(value.trim()) || count <= 0) {
    return "Укажите целое число вариантов больше нуля";
  }
  if (count > MAX_TOP_N) {
    return `Число вариантов не должно превышать ${MAX_TOP_N}`;
  }
  return null;
}

export default function GenerationPage() {
  const { projectId } = useParams();
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
    schedules,
    resultsLoading,
    resultsError,
    retryResults,
    start,
    cancel
  } = useGenerationJob(projectId);
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
          projectId={projectId}
          job={job}
          pollError={pollError}
          cancelling={cancelling}
          cancelRequested={cancelRequested}
          cancelError={cancelError}
          schedules={schedules}
          resultsLoading={resultsLoading}
          resultsError={resultsError}
          onRetryResults={retryResults}
          onCancel={cancel}
        />
      )}
    </Box>
  );
}
