import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  FormControlLabel,
  FormGroup,
  FormHelperText,
  Radio,
  RadioGroup,
  Stack,
  TextField,
  Typography
} from "@mui/material";
import { useOutletContext } from "react-router";

import { projectsApi } from "../../projects/api.js";
import { toFormErrors } from "../formErrors.js";
import { WEEKDAYS } from "../intervals.js";
import { validatePositiveInteger } from "../validation.js";

// Значения по умолчанию совпадают с backend (domain/projects/settings.py)
const MONDAY_TO_SATURDAY = WEEKDAYS.slice(0, 6).map((day) => day.value);
const DEFAULT_DURATION_MINUTES = 100;

function toValues(project) {
  return {
    odd_week_days: project.cycle?.odd_week_days ?? MONDAY_TO_SATURDAY,
    even_week_days: project.cycle?.even_week_days ?? MONDAY_TO_SATURDAY,
    time_mode: project.time_mode?.type ?? "HOUR_START",
    step_minutes: String(project.time_mode?.step_minutes ?? ""),
    duration_mode: project.duration_mode?.type ?? "UNIFORM",
    duration_minutes: String(
      project.duration_mode ? (project.duration_mode.duration_minutes ?? "") : DEFAULT_DURATION_MINUTES
    )
  };
}

// Порядок дней как в неделе, а не как их отметили
const ordered = (days) => WEEKDAYS.map((day) => day.value).filter((day) => days.includes(day));

function validate(values) {
  const errors = {
    "time_mode.step_minutes":
      values.time_mode === "STEP"
        ? validatePositiveInteger(values.step_minutes, "Нужен положительный шаг в минутах")
        : null,
    "duration_mode.duration_minutes":
      values.duration_mode === "UNIFORM"
        ? validatePositiveInteger(values.duration_minutes, "Нужна положительная длительность в минутах")
        : null
  };
  return Object.fromEntries(Object.entries(errors).filter(([, error]) => error));
}

function WeekDays({ legend, value, onChange }) {
  const toggle = (day) => onChange(value.includes(day) ? value.filter((item) => item !== day) : [...value, day]);

  return (
    <Box component="fieldset" sx={{ border: 0, p: 0, m: 0 }}>
      <Typography component="legend" variant="subtitle2">
        {legend}
      </Typography>
      <FormGroup row>
        {WEEKDAYS.map((day) => (
          <FormControlLabel
            key={day.value}
            control={<Checkbox checked={value.includes(day.value)} onChange={() => toggle(day.value)} />}
            label={day.short}
            aria-label={`${day.label}, ${legend.toLowerCase()}`}
          />
        ))}
      </FormGroup>
      {value.length === 0 && (
        <FormHelperText>Учебных дней нет: занятия на этой неделе не планируются.</FormHelperText>
      )}
    </Box>
  );
}

// Настройки времени проекта (F_Data_1–F_Data_3). Несовместимость с уже введёнными данными
// проверяется перед расчётом, а не здесь
export default function ProjectSettingsPage() {
  const { project, onProjectChange } = useOutletContext();
  const [values, setValues] = useState(() => toValues(project));
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const setValue = (name, value) => {
    setValues((current) => ({ ...current, [name]: value }));
    setErrors({});
    setSaved(false);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setFormError(null);

    const found = validate(values);
    setErrors(found);
    if (Object.keys(found).length > 0) {
      return;
    }

    setSaving(true);
    try {
      const updated = await projectsApi.update(project.id, {
        cycle: { odd_week_days: ordered(values.odd_week_days), even_week_days: ordered(values.even_week_days) },
        time_mode:
          values.time_mode === "STEP"
            ? { type: "STEP", step_minutes: Number(values.step_minutes) }
            : { type: "HOUR_START" },
        duration_mode:
          values.duration_mode === "UNIFORM"
            ? { type: "UNIFORM", duration_minutes: Number(values.duration_minutes) }
            : { type: "INDIVIDUAL" }
      });
      onProjectChange(updated);
      setValues(toValues(updated));
      setSaved(true);
    } catch (error) {
      const { fields, form } = toFormErrors(error);
      setErrors(fields);
      setFormError(form);
    } finally {
      setSaving(false);
    }
  };

  const stepError = errors["time_mode.step_minutes"] ?? errors.time_mode;
  const durationError = errors["duration_mode.duration_minutes"] ?? errors.duration_mode;

  return (
    <Box component="form" noValidate onSubmit={handleSubmit} sx={{ py: 2, maxWidth: 640 }}>
      <Typography component="h2" variant="h5" sx={{ mb: 1 }}>
        Настройки проекта
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 2 }}>
        Учебные дни двухнедельного цикла, время начала и длительность занятий.
      </Typography>

      <Stack spacing={3}>
        {formError && <Alert severity="error">{formError}</Alert>}

        <Stack spacing={1}>
          <Typography component="h3" variant="h6">
            Учебные дни
          </Typography>
          <WeekDays
            legend="Нечётная неделя"
            value={values.odd_week_days}
            onChange={(next) => setValue("odd_week_days", next)}
          />
          <WeekDays
            legend="Чётная неделя"
            value={values.even_week_days}
            onChange={(next) => setValue("even_week_days", next)}
          />
        </Stack>

        <Stack spacing={1}>
          <Typography component="h3" variant="h6" id="time-mode">
            Начало занятий
          </Typography>
          <RadioGroup
            aria-labelledby="time-mode"
            value={values.time_mode}
            onChange={(event) => setValue("time_mode", event.target.value)}
          >
            <FormControlLabel value="HOUR_START" control={<Radio />} label="В начале часа" />
            <FormControlLabel value="STEP" control={<Radio />} label="С заданным шагом" />
          </RadioGroup>
          {values.time_mode === "STEP" && (
            <TextField
              label="Шаг, минут"
              value={values.step_minutes}
              onChange={(event) => setValue("step_minutes", event.target.value)}
              error={Boolean(stepError)}
              helperText={stepError ?? "Например, 30: занятия начинаются в 9:00, 9:30, 10:00…"}
              slotProps={{ htmlInput: { inputMode: "numeric" } }}
            />
          )}
        </Stack>

        <Stack spacing={1}>
          <Typography component="h3" variant="h6" id="duration-mode">
            Длительность занятий
          </Typography>
          <RadioGroup
            aria-labelledby="duration-mode"
            value={values.duration_mode}
            onChange={(event) => setValue("duration_mode", event.target.value)}
          >
            <FormControlLabel value="UNIFORM" control={<Radio />} label="Одинаковая для всех занятий" />
            <FormControlLabel value="INDIVIDUAL" control={<Radio />} label="Своя у каждого элемента нагрузки" />
          </RadioGroup>
          {values.duration_mode === "UNIFORM" ? (
            <TextField
              label="Длительность, минут"
              value={values.duration_minutes}
              onChange={(event) => setValue("duration_minutes", event.target.value)}
              error={Boolean(durationError)}
              helperText={durationError}
              slotProps={{ htmlInput: { inputMode: "numeric" } }}
            />
          ) : (
            <FormHelperText>Длительность указывается в разделе «Нагрузка» для каждого занятия.</FormHelperText>
          )}
        </Stack>

        {saved && <Alert severity="success">Настройки сохранены</Alert>}
        <Box>
          <Button type="submit" variant="contained" disabled={saving}>
            Сохранить
          </Button>
        </Box>
      </Stack>
    </Box>
  );
}
