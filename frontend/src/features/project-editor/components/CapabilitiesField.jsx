import { Box, Button, FormHelperText, Stack, TextField, Typography } from "@mui/material";

import { LESSON_TYPES } from "../intervals.js";

const nativeSelect = { select: { native: true } };

// Набор пар «дисциплина + тип занятия». Пара — то, что преподаватель может вести
// или в какой аудитории можно проводить занятие (F_Data_4, F_Data_9)
export default function CapabilitiesField({ label, subjects, value, onChange, error, hint }) {
  const update = (index, changes) =>
    onChange(value.map((item, i) => (i === index ? { ...item, ...changes } : item)));

  const addRow = () =>
    onChange([...value, { subject_id: subjects[0]?.id ?? "", lesson_type: LESSON_TYPES[0].value }]);

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
        {value.map((item, index) => {
          const row = `${label}, пара ${index + 1}`;
          return (
            <Stack key={index} direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap" }}>
              <TextField
                select
                size="small"
                label="Дисциплина"
                value={item.subject_id}
                onChange={(event) => update(index, { subject_id: event.target.value })}
                slotProps={{ ...nativeSelect, htmlInput: { "aria-label": `Дисциплина: ${row}` } }}
                sx={{ minWidth: 200 }}
              >
                {subjects.map((subject) => (
                  <option key={subject.id} value={subject.id}>
                    {subject.name}
                  </option>
                ))}
              </TextField>
              <TextField
                select
                size="small"
                label="Тип занятия"
                value={item.lesson_type}
                onChange={(event) => update(index, { lesson_type: event.target.value })}
                slotProps={{ ...nativeSelect, htmlInput: { "aria-label": `Тип занятия: ${row}` } }}
              >
                {LESSON_TYPES.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </TextField>
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

      <Button size="small" sx={{ mt: 1 }} onClick={addRow} disabled={subjects.length === 0}>
        Добавить пару
      </Button>
      {error && <FormHelperText error>{error}</FormHelperText>}
    </Box>
  );
}
