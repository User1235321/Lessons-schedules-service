import { lessonTypeLabel, WEEKDAYS, WEEKS } from "../project-editor/intervals.js";
import { targetLabel, targetOptions } from "../project-editor/workloadTargets.js";

export const CONSTRAINT_TYPES = [
  { value: "MIN_START_TIME", label: "Минимальное время начала" },
  { value: "MAX_END_TIME", label: "Максимальное время окончания" },
  { value: "ALLOWED_DAYS", label: "Допустимые дни" },
  { value: "TIME_RANGE", label: "Допустимые временные интервалы" },
  { value: "EVERY_WEEK", label: "Занятие каждую неделю" },
  { value: "CONSECUTIVE", label: "Последовательные занятия" },
  { value: "NOT_CONSECUTIVE", label: "Запрет последовательных занятий" },
  { value: "MIN_GAP", label: "Минимальный интервал между занятиями" },
  { value: "BEFORE", label: "Порядок проведения занятий" },
  { value: "FIXED_DAY", label: "Фиксированный день" }
];

export const CRITERION_TYPES = [
  { value: "STUDENT_GAPS", label: "Минимизировать окна студентов" },
  { value: "TEACHER_GAPS", label: "Минимизировать окна преподавателей" },
  { value: "TEACHER_PREFERENCES", label: "Учитывать предпочтения преподавателей" },
  { value: "BALANCED_STUDENT_LOAD", label: "Равномерно распределять нагрузку" },
  { value: "EARLY_LATE_CLASSES", label: "Минимизировать ранние и поздние занятия" }
];

export const SCOPE_TYPES = [
  { value: "PROJECT", label: "Весь проект" },
  { value: "GROUP", label: "Группа" },
  { value: "SUBGROUP", label: "Подгруппа" },
  { value: "STREAM", label: "Поток" },
  { value: "WORKLOAD", label: "Учебная нагрузка" }
];

const WORKLOAD_ONLY = new Set([
  "EVERY_WEEK", "CONSECUTIVE", "NOT_CONSECUTIVE", "MIN_GAP", "BEFORE", "FIXED_DAY"
]);
const RELATED = new Set(["CONSECUTIVE", "NOT_CONSECUTIVE", "MIN_GAP", "BEFORE"]);
const TIME_PATTERN = /^([01]\d|2[0-3]):[0-5]\d$/;
const MAX_MINUTES = 2147483647;

export const NEW_WINDOW = { week: "ANY", day: "MONDAY", start: "09:00", end: "18:00" };

export const constraintTypeLabel = (type) =>
  CONSTRAINT_TYPES.find((option) => option.value === type)?.label ?? type;

const dayLabel = (day) => WEEKDAYS.find((item) => item.value === day)?.label ?? day;
const weekLabel = (week) => WEEKS.find((item) => item.value === week)?.label ?? week;

export const criterionTypeLabel = (type) =>
  CRITERION_TYPES.find((option) => option.value === type)?.label ?? type;

export const allowedScopeTypes = (kind) =>
  WORKLOAD_ONLY.has(kind) ? SCOPE_TYPES.filter((type) => type.value === "WORKLOAD") : SCOPE_TYPES;

export function createScopeOptions({ groups, streams, workloads, subjects }) {
  const targets = targetOptions({ groups, streams });
  const subjectNames = new Map(subjects.map((subject) => [subject.id, subject.name]));
  return {
    PROJECT: [],
    GROUP: targets.GROUP,
    SUBGROUP: targets.SUBGROUP,
    STREAM: targets.STREAM,
    WORKLOAD: workloads.map((workload) => ({
      id: workload.id,
      label: `${subjectNames.get(workload.subject_id) ?? "Дисциплина"} (${lessonTypeLabel(workload.lesson_type)}) — ${targetLabel(targets, workload)}`
    }))
  };
}

export function initialConstraintValues(item, options) {
  const kind = item?.constraint_type ?? "MIN_START_TIME";
  const scopeType = item?.scope?.type ?? (WORKLOAD_ONLY.has(kind) ? "WORKLOAD" : "PROJECT");
  const scopeId = item?.scope?.id ?? options[scopeType]?.[0]?.id ?? "";
  const parameters = item?.parameters ?? {};
  return {
    kind,
    scopeType,
    scopeId,
    time: parameters.time ?? (kind === "MAX_END_TIME" ? "18:00" : "08:00"),
    days: parameters.days ?? ["MONDAY"],
    windows: parameters.windows ?? [{ ...NEW_WINDOW }],
    week: parameters.week ?? "ANY",
    day: parameters.day ?? "MONDAY",
    relatedWorkloadId: parameters.workload_id ??
      options.WORKLOAD.find((workload) => workload.id !== scopeId)?.id ?? "",
    minutes: String(parameters.minutes ?? "30")
  };
}

export function validateConstraint(values, options) {
  const errors = {};
  if (values.scopeType !== "PROJECT" && !options[values.scopeType]?.some((item) => item.id === values.scopeId)) {
    errors.scopeId = "Выберите существующий ресурс";
  }
  if (["MIN_START_TIME", "MAX_END_TIME"].includes(values.kind) && !TIME_PATTERN.test(values.time)) {
    errors.time = "Укажите время в формате ЧЧ:ММ";
  }
  if (values.kind === "ALLOWED_DAYS" && values.days.length === 0) {
    errors.days = "Выберите хотя бы один день";
  }
  if (values.kind === "TIME_RANGE") {
    const windows = values.windows;
    if (!windows.length || windows.some((window) =>
      !TIME_PATTERN.test(window.start) || !TIME_PATTERN.test(window.end) || window.start >= window.end
    ) || new Set(windows.map((window) => JSON.stringify(window))).size !== windows.length) {
      errors.windows = "Добавьте неповторяющиеся интервалы с корректными временем начала и окончания";
    }
  }
  if (RELATED.has(values.kind)) {
    if (!options.WORKLOAD.some((item) => item.id === values.relatedWorkloadId)) {
      errors.relatedWorkloadId = "Выберите вторую учебную нагрузку";
    } else if (values.scopeId === values.relatedWorkloadId) {
      errors.relatedWorkloadId = "Выберите другую учебную нагрузку";
    }
  }
  if (values.kind === "MIN_GAP" && (!/^\d+$/.test(values.minutes) ||
    Number(values.minutes) < 1 || Number(values.minutes) > MAX_MINUTES)) {
    errors.minutes = "Укажите целое число минут от 1 до 2147483647";
  }
  return errors;
}

export function toConstraintRequest(values) {
  const scope = values.scopeType === "PROJECT"
    ? { type: "PROJECT" }
    : { type: values.scopeType, id: values.scopeId };
  let parameters;
  switch (values.kind) {
    case "MIN_START_TIME":
    case "MAX_END_TIME":
      parameters = { time: values.time };
      break;
    case "ALLOWED_DAYS":
      parameters = { days: values.days };
      break;
    case "TIME_RANGE":
      parameters = { windows: values.windows };
      break;
    case "EVERY_WEEK":
      parameters = {};
      break;
    case "CONSECUTIVE":
    case "NOT_CONSECUTIVE":
    case "BEFORE":
      parameters = { workload_id: values.relatedWorkloadId };
      break;
    case "MIN_GAP":
      parameters = { workload_id: values.relatedWorkloadId, minutes: Number(values.minutes) };
      break;
    case "FIXED_DAY":
      parameters = { day: values.day, week: values.week };
      break;
    default:
      throw new Error("Неизвестный тип ограничения");
  }
  return { constraint_type: values.kind, scope, parameters };
}

export function constraintScopeLabel(constraint, options) {
  const { type, id } = constraint.scope;
  if (type === "PROJECT") return "Весь проект";
  return options[type]?.find((item) => item.id === id)?.label ?? "Ресурс недоступен";
}

export function constraintParametersLabel(constraint, options) {
  const { constraint_type: kind, parameters: data } = constraint;
  const workloadName = (id) =>
    options.WORKLOAD.find((item) => item.id === id)?.label ?? "Нагрузка недоступна";
  switch (kind) {
    case "MIN_START_TIME":
    case "MAX_END_TIME":
      return data.time;
    case "ALLOWED_DAYS":
      return data.days.map(dayLabel).join(", ");
    case "TIME_RANGE":
      return data.windows.map((window) =>
        `${weekLabel(window.week)}: ${dayLabel(window.day)} ${window.start}–${window.end}`).join("; ");
    case "EVERY_WEEK":
      return "Каждую неделю";
    case "CONSECUTIVE":
    case "NOT_CONSECUTIVE":
    case "BEFORE":
      return workloadName(data.workload_id);
    case "MIN_GAP":
      return `${workloadName(data.workload_id)}, ${data.minutes} мин`;
    case "FIXED_DAY":
      return `${dayLabel(data.day)}, ${weekLabel(data.week ?? "ANY")}`;
    default:
      return "—";
  }
}
