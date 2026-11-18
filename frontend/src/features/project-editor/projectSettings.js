export const WEEKDAYS = [
  { value: "MONDAY", label: "Пн" },
  { value: "TUESDAY", label: "Вт" },
  { value: "WEDNESDAY", label: "Ср" },
  { value: "THURSDAY", label: "Чт" },
  { value: "FRIDAY", label: "Пт" },
  { value: "SATURDAY", label: "Сб" },
  { value: "SUNDAY", label: "Вс" }
];

export function createSettingsDraft(project) {
  return {
    oddWeekDays: [...project.cycle.odd_week_days],
    evenWeekDays: [...project.cycle.even_week_days],
    timeMode: project.time_mode.type,
    stepMinutes: String(project.time_mode.step_minutes ?? ""),
    durationMode: project.duration_mode.type,
    durationMinutes: String(project.duration_mode.duration_minutes ?? "")
  };
}

function isPositiveMinutes(value) {
  const minutes = value.trim();
  return /^\d+$/.test(minutes) && Number.isSafeInteger(Number(minutes)) && Number(minutes) > 0;
}

export function validateSettingsDraft(draft) {
  const errors = {};

  if (draft.timeMode === "STEP" && !isPositiveMinutes(draft.stepMinutes)) {
    errors.stepMinutes = "Укажите положительное целое число минут";
  }

  if (draft.durationMode === "UNIFORM" && !isPositiveMinutes(draft.durationMinutes)) {
    errors.durationMinutes = "Укажите положительное целое число минут";
  }

  return errors;
}

export function settingsPayload(draft) {
  return {
    cycle: {
      odd_week_days: WEEKDAYS.map(({ value }) => value).filter((day) =>
        draft.oddWeekDays.includes(day)
      ),
      even_week_days: WEEKDAYS.map(({ value }) => value).filter((day) =>
        draft.evenWeekDays.includes(day)
      )
    },
    time_mode: draft.timeMode === "STEP"
      ? { type: "STEP", step_minutes: Number(draft.stepMinutes) }
      : { type: "HOUR_START" },
    duration_mode: draft.durationMode === "UNIFORM"
      ? { type: "UNIFORM", duration_minutes: Number(draft.durationMinutes) }
      : { type: "INDIVIDUAL" }
  };
}
