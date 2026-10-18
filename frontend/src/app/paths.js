// Единый источник URL приложения. В компонентах ссылки строятся только через эти функции,
// чтобы при изменении структуры маршрутов не искать строки по всему коду.

export const projectSections = [
  { path: "subjects", label: "Дисциплины" },
  { path: "teachers", label: "Преподаватели" },
  { path: "rooms", label: "Аудитории" },
  { path: "groups", label: "Группы" },
  { path: "streams", label: "Потоки" },
  { path: "workloads", label: "Нагрузка" },
  { path: "constraints", label: "Ограничения" },
  { path: "generation", label: "Расчёт" },
  { path: "schedules", label: "Расписания" },
  { path: "files", label: "Файлы" },
  { path: "settings", label: "Настройки" }
];

export const DEFAULT_PROJECT_SECTION = "teachers";

export const paths = {
  home: "/",
  login: "/login",
  register: "/register",
  passwordReset: "/password-reset",
  passwordResetConfirm: "/password-reset/confirm",
  projects: "/projects",
  project: (projectId) => `/projects/${projectId}`,
  projectSection: (projectId, section) => `/projects/${projectId}/${section}`,
  schedule: (projectId, scheduleId) =>
    `/projects/${projectId}/schedules/${scheduleId}`,
  scheduleEdit: (projectId, scheduleId) =>
    `/projects/${projectId}/schedules/${scheduleId}/edit`
};
