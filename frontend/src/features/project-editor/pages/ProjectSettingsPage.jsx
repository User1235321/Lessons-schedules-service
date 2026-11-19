import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  FormControl,
  FormControlLabel,
  FormGroup,
  FormLabel,
  Paper,
  Radio,
  RadioGroup,
  Stack,
  TextField,
  Typography
} from "@mui/material";
import { useOutletContext } from "react-router";

import { projectsApi } from "../../projects/api.js";
import {
  createSettingsDraft,
  settingsPayload,
  validateSettingsDraft,
  WEEKDAYS
} from "../projectSettings.js";

const WEEKS = [
  { field: "oddWeekDays", label: "Нечётная неделя" },
  { field: "evenWeekDays", label: "Чётная неделя" }
];

const API_FIELDS = {
  "time_step_minutes": "stepMinutes",
  "duration_minutes": "durationMinutes"
};

export default function ProjectSettingsPage() {
  const { project, updateProject } = useOutletContext();
  const [draft, setDraft] = useState(() => createSettingsDraft(project));
  const [errors, setErrors] = useState({});
  const [message, setMessage] = useState(null);
  const [saving, setSaving] = useState(false);

  const changeField = (field, value) => {
    setDraft((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
    setMessage(null);
  };

  const toggleWeekday = (field, day, checked) => {
    setDraft((current) => ({
      ...current,
      [field]: checked
        ? [...current[field], day]
        : current[field].filter((value) => value !== day)
    }));
    setMessage(null);
  };

  const save = async (event) => {
    event.preventDefault();
    const validationErrors = validateSettingsDraft(draft);
    setErrors(validationErrors);
    setMessage(null);

    if (Object.keys(validationErrors).length > 0) {
      return;
    }

    setSaving(true);
    try {
      const updated = await projectsApi.update(project.id, settingsPayload(draft));
      updateProject(updated);
      setDraft(createSettingsDraft(updated));
      setMessage({ severity: "success", text: "Настройки сохранены" });
    } catch (error) {
      const field = API_FIELDS[error.details?.field];
      if (field) {
        setErrors({ [field]: error.message });
      } else {
        setMessage({
          severity: "error",
          text: error.message ?? "Не удалось сохранить настройки"
        });
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <Box component="form" noValidate onSubmit={save} sx={{ mt: 3 }}>
      <Stack spacing={3} sx={{ maxWidth: 800 }}>
        <Typography component="h2" variant="h5">
          Настройки проекта
        </Typography>

        <Paper variant="outlined" sx={{ p: 3 }}>
          <Stack spacing={2}>
            <Typography variant="h6">Учебные дни</Typography>
            <Stack direction={{ xs: "column", md: "row" }} spacing={3}>
              {WEEKS.map(({ field, label }) => (
                <FormControl component="fieldset" key={field} sx={{ flex: 1 }}>
                  <FormLabel component="legend">{label}</FormLabel>
                  <FormGroup row>
                    {WEEKDAYS.map(({ value, label: day }) => (
                      <FormControlLabel
                        key={value}
                        label={day}
                        control={
                          <Checkbox
                            checked={draft[field].includes(value)}
                            onChange={(event) => toggleWeekday(field, value, event.target.checked)}
                            disabled={saving}
                          />
                        }
                      />
                    ))}
                  </FormGroup>
                </FormControl>
              ))}
            </Stack>
            <Typography variant="body2" color="text.secondary">
              Можно оставить неделю без учебных дней. Возможность составить расписание
              проверяется при запуске расчёта.
            </Typography>
          </Stack>
        </Paper>

        <Paper variant="outlined" sx={{ p: 3 }}>
          <FormControl component="fieldset">
            <FormLabel component="legend">Начало занятий</FormLabel>
            <RadioGroup
              value={draft.timeMode}
              onChange={(event) => changeField("timeMode", event.target.value)}
            >
              <FormControlLabel
                value="HOUR_START"
                control={<Radio disabled={saving} />}
                label="Только в начале часа"
              />
              <FormControlLabel
                value="STEP"
                control={<Radio disabled={saving} />}
                label="С минимальным временным шагом"
              />
            </RadioGroup>
            {draft.timeMode === "STEP" && (
              <TextField
                label="Минимальный шаг, минут"
                type="number"
                value={draft.stepMinutes}
                onChange={(event) => changeField("stepMinutes", event.target.value)}
                error={Boolean(errors.stepMinutes)}
                helperText={errors.stepMinutes}
                slotProps={{ htmlInput: { min: 1, step: 1 } }}
                disabled={saving}
                margin="dense"
                sx={{ maxWidth: 280 }}
              />
            )}
          </FormControl>
        </Paper>

        <Paper variant="outlined" sx={{ p: 3 }}>
          <FormControl component="fieldset">
            <FormLabel component="legend">Длительность занятий</FormLabel>
            <RadioGroup
              value={draft.durationMode}
              onChange={(event) => changeField("durationMode", event.target.value)}
            >
              <FormControlLabel
                value="UNIFORM"
                control={<Radio disabled={saving} />}
                label="Единая для всех занятий"
              />
              <FormControlLabel
                value="INDIVIDUAL"
                control={<Radio disabled={saving} />}
                label="Индивидуальная для каждого элемента нагрузки"
              />
            </RadioGroup>
            {draft.durationMode === "UNIFORM" && (
              <TextField
                label="Длительность занятия, минут"
                type="number"
                value={draft.durationMinutes}
                onChange={(event) => changeField("durationMinutes", event.target.value)}
                error={Boolean(errors.durationMinutes)}
                helperText={errors.durationMinutes}
                slotProps={{ htmlInput: { min: 1, step: 1 } }}
                disabled={saving}
                margin="dense"
                sx={{ maxWidth: 280 }}
              />
            )}
          </FormControl>
        </Paper>

        {message && <Alert severity={message.severity}>{message.text}</Alert>}

        <Box>
          <Button type="submit" variant="contained" disabled={saving}>
            {saving ? "Сохранение..." : "Сохранить настройки"}
          </Button>
        </Box>
      </Stack>
    </Box>
  );
}
