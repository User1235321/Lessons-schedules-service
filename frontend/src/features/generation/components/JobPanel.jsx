import { Box, Chip, Stack, Typography } from "@mui/material";

import { JOB_STATUS } from "../jobStatus.js";

// Состояние расчёта. aria-live сообщает об изменении статуса без перехода фокуса
export default function JobPanel({ job }) {
  const status = JOB_STATUS[job.status] ?? { label: job.status, color: "default" };

  return (
    <Box role="status" aria-live="polite" sx={{ mt: 3 }}>
      <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
        <Typography variant="subtitle1">Состояние расчёта:</Typography>
        <Chip label={status.label} color={status.color} />
      </Stack>
    </Box>
  );
}
