
export const WEEKS = [
  { value: "ANY", label: "Обе недели" },
  { value: "ODD", label: "Нечётная" },
  { value: "EVEN", label: "Чётная" }
];

export const WEEKDAYS = [
  { value: "MONDAY", label: "Понедельник", short: "Пн" },
  { value: "TUESDAY", label: "Вторник", short: "Вт" },
  { value: "WEDNESDAY", label: "Среда", short: "Ср" },
  { value: "THURSDAY", label: "Четверг", short: "Чт" },
  { value: "FRIDAY", label: "Пятница", short: "Пт" },
  { value: "SATURDAY", label: "Суббота", short: "Сб" },
  { value: "SUNDAY", label: "Воскресенье", short: "Вс" }
];

export const LESSON_TYPES = [
  { value: "LECTURE", label: "Лекция" },
  { value: "PRACTICE", label: "Практика" },
  { value: "LAB", label: "Лабораторная" }
];

export const newInterval = () => ({ week: "ANY", day: "MONDAY", start: "09:00", end: "18:00" });

export const ROOM_TYPES = [
  { value: "LECTURE", label: "Лекционная", hasCapabilities: false },
  { value: "PRACTICE_UNIVERSAL", label: "Практическая универсальная", hasCapabilities: false },
  { value: "PRACTICE_SPECIALIZED", label: "Практическая специализированная", hasCapabilities: true },
  { value: "LABORATORY", label: "Лаборатория", hasCapabilities: true }
];

export const LESSON_FORMATS = [
  { value: "ONSITE", label: "Очно" },
  { value: "REMOTE", label: "Дистанционно" }
];

export const TARGET_TYPES = [
  { value: "GROUP", label: "Группа" },
  { value: "SUBGROUP", label: "Подгруппа" },
  { value: "STREAM", label: "Поток" }
];

export const roomIntervalToForm = ({ week, weekday, start_time: start, end_time: end }) =>
  ({ week, day: weekday, start, end });

export const roomIntervalToApi = ({ week, day, start, end }) =>
  ({ week, weekday: day, start_time: start, end_time: end });

const labelOf = (options, value) => options.find((option) => option.value === value)?.label ?? value;

export const lessonTypeLabel = (value) => labelOf(LESSON_TYPES, value);
export const roomTypeLabel = (value) => labelOf(ROOM_TYPES, value);
export const lessonFormatLabel = (value) => labelOf(LESSON_FORMATS, value);
export const roomTypeHasCapabilities = (value) =>
  ROOM_TYPES.find((type) => type.value === value)?.hasCapabilities ?? false;

export function formatInterval({ week, day, start, end }) {
  const weekLabel = week === "ANY" ? "" : `, ${labelOf(WEEKS, week).toLowerCase()}`;
  const dayLabel = WEEKDAYS.find((item) => item.value === day)?.short ?? day;
  return `${dayLabel}${weekLabel} ${start}–${end}`;
}

export const formatRoomInterval = (interval) => formatInterval(roomIntervalToForm(interval));

export function validateIntervals(intervals, { required }) {
  if (required && intervals.length === 0) {
    return "Добавьте хотя бы один промежуток";
  }
  for (const { start, end } of intervals) {
    if (!start || !end) {
      return "Укажите время начала и окончания";
    }
    if (start >= end) {
      return "Время окончания должно быть позже начала";
    }
  }
  return null;
}

export function validateCapabilities(capabilities, { required }) {
  if (required && capabilities.length === 0) {
    return "Добавьте хотя бы одну пару «дисциплина + тип занятия»";
  }
  const seen = new Set();
  for (const { subject_id: subjectId, lesson_type: lessonType } of capabilities) {
    if (!subjectId) {
      return "Выберите дисциплину";
    }
    const key = `${subjectId}:${lessonType}`;
    if (seen.has(key)) {
      return "Пары не должны повторяться";
    }
    seen.add(key);
  }
  return null;
}
