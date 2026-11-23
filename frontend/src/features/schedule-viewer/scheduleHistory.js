// API выдаёт отдельное расписание по ID или результаты одного расчёта.
// В браузере храним только ссылки, раздельно для каждого пользователя и проекта.
const prefix = (userId, projectId) => `schedule-history:${userId}:${projectId.toLowerCase()}:`;

export function rememberSchedules(userId, projectId, schedules) {
  if (!userId) return;
  const addedAt = Date.now();
  try {
    for (const schedule of schedules) {
      if (schedule.project_id !== projectId.toLowerCase()) continue;
      const key = prefix(userId, projectId) + schedule.id;
      if (localStorage.getItem(key) === null) {
        localStorage.setItem(key, JSON.stringify({
          index: schedule.result_index, source: schedule.source, addedAt
        }));
      }
    }
  } catch {
    // Просмотр по прямой ссылке работает и при недоступном хранилище.
  }
}

export function readScheduleHistory(userId, projectId) {
  const records = [];
  const start = prefix(userId, projectId);
  try {
    for (const key of Object.keys(localStorage)) {
      if (!key.startsWith(start)) continue;
      try {
        const record = JSON.parse(localStorage.getItem(key));
        if (Number.isFinite(record?.addedAt)) records.push({ ...record, id: key.slice(start.length) });
      } catch {
        // Повреждённая запись не мешает открыть остальные расписания.
      }
    }
  } catch {
    return [];
  }
  return records.sort((a, b) => b.addedAt - a.addedAt || a.index - b.index);
}
