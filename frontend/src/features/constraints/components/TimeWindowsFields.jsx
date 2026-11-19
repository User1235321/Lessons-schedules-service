import { Alert, Button, Stack, TextField, Typography } from "@mui/material";

import { WEEKDAYS, WEEKS } from "../../project-editor/intervals.js";
import { NEW_WINDOW } from "../constraintModel.js";
import ConstraintSelectField from "./ConstraintSelectField.jsx";

export default function TimeWindowsFields({ windows, error, onChange }) {
  const changeWindow = (index, field, value) => {
    onChange(windows.map((window, position) =>
      position === index ? { ...window, [field]: value } : window
    ));
  };

  return (
    <Stack spacing={2}>
      <Typography>Допустимые интервалы</Typography>
      {windows.map((window, index) => (
        <Stack key={index} spacing={2} sx={{ border: 1, borderColor: "divider", borderRadius: 1, p: 2 }}>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <ConstraintSelectField
              label="Неделя"
              value={window.week}
              onChange={(value) => changeWindow(index, "week", value)}
              options={WEEKS}
            />
            <ConstraintSelectField
              label="День"
              value={window.day}
              onChange={(value) => changeWindow(index, "day", value)}
              options={WEEKDAYS}
            />
          </Stack>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
            <TextField
              label="Начало"
              type="time"
              value={window.start}
              onChange={(event) => changeWindow(index, "start", event.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
              fullWidth
            />
            <TextField
              label="Конец"
              type="time"
              value={window.end}
              onChange={(event) => changeWindow(index, "end", event.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
              fullWidth
            />
          </Stack>
          <Button
            color="error"
            size="small"
            onClick={() => onChange(windows.filter((_, position) => position !== index))}
          >
            Удалить интервал
          </Button>
        </Stack>
      ))}
      {error && <Alert severity="error">{error}</Alert>}
      <Button onClick={() => onChange([...windows, { ...NEW_WINDOW }])}>
        Добавить интервал
      </Button>
    </Stack>
  );
}
