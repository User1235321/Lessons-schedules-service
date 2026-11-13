// Статусы задания расчёта (domain/scheduling/job.py)
export const JOB_STATUS = {
  QUEUED: { label: "В очереди", color: "default" },
  RUNNING: { label: "Выполняется", color: "info" },
  COMPLETED: { label: "Завершён", color: "success" },
  FAILED: { label: "Ошибка", color: "error" },
  CANCELLED: { label: "Отменён", color: "warning" },
  // Состояние не удалось получить (сеть): показываем честно, а не придумываем статус
  UNKNOWN: { label: "Неизвестно", color: "default" }
};

const FINAL = ["COMPLETED", "FAILED", "CANCELLED"];

export const isFinal = (status) => FINAL.includes(status);
// Отменить можно только то, что ещё не закончилось
export const isCancellable = (status) => status === "QUEUED" || status === "RUNNING";
