import { Box, Button, FormHelperText, Stack, TextField, Typography } from "@mui/material";

import { newInterval, WEEKDAYS, WEEKS } from "../intervals.js";

const nativeSelect = { select: { native: true } };

// Редактор набора промежутков времени: неделя, день, начало и окончание
export default function IntervalsField({ label, value, onChange, error, hint }) {
  const update = (index, changes) =>
    onChange(value.map((interval, i) => (i === index ? { ...interval, ...changes } : interval)));

  return (
    <Box component="fieldset" sx={{ border: 0, p: 0, m: 0 }}>
      <Typography component="legend" variant="subtitle2" sx={{ mb: 0.5 }}>
        {label}
      </Typography>
      {hint && (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {hint}
        </Typography>
      )}

      <Stack spacing={1}>
        {value.map((interval, index) => {
          const row = `${label}, промежуток ${index + 1}`;
          return (
            <Stack key={index} direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap" }}>
              <TextField
                select
                size="small"
                label="Неделя"
                value={interval.week}
                onChange={(event) => update(index, { week: event.target.value })}
                slotProps={{ ...nativeSelect, htmlInput: { "aria-label": `Неделя: ${row}` } }}
              >
                {WEEKS.map((week) => (
                  <option key={week.value} value={week.value}>
                    {week.label}
                  </option>
                ))}
              </TextField>
              <TextField
                select
                size="small"
                label="День"
                value={interval.day}
                onChange={(event) => update(index, { day: event.target.value })}
                slotProps={{ ...nativeSelect, htmlInput: { "aria-label": `День: ${row}` } }}
              >
                {WEEKDAYS.map((day) => (
                  <option key={day.value} value={day.value}>
                    {day.label}
                  </option>
                ))}
              </TextField>
              <TextField
                size="small"
                type="time"
                label="С"
                value={interval.start}
                onChange={(event) => update(index, { start: event.target.value })}
                slotProps={{ inputLabel: { shrink: true }, htmlInput: { "aria-label": `Начало: ${row}` } }}
              />
              <TextField
                size="small"
                type="time"
                label="До"
                value={interval.end}
                onChange={(event) => update(index, { end: event.target.value })}
                slotProps={{ inputLabel: { shrink: true }, htmlInput: { "aria-label": `Окончание: ${row}` } }}
              />
              <Button
                size="small"
                color="error"
                aria-label={`Удалить: ${row}`}
                onClick={() => onChange(value.filter((_, i) => i !== index))}
              >
                Удалить
              </Button>
            </Stack>
          );
        })}
      </Stack>

      <Button size="small" sx={{ mt: 1 }} onClick={() => onChange([...value, newInterval()])}>
        Добавить промежуток
      </Button>
      {error && <FormHelperText error>{error}</FormHelperText>}
    </Box>
  );
}
