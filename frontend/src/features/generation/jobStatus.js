export const JOB_STATUS = {
  QUEUED: { label: "В очереди", color: "default" },
  RUNNING: { label: "Выполняется", color: "info" },
  COMPLETED: { label: "Завершён", color: "success" },
  FAILED: { label: "Ошибка", color: "error" },
  CANCELLED: { label: "Отменён", color: "warning" },
  UNKNOWN: { label: "Неизвестно", color: "default" }
};

const FINAL = ["COMPLETED", "FAILED", "CANCELLED"];

export const isFinal = (status) => FINAL.includes(status);
export const isCancellable = (status) => status === "QUEUED" || status === "RUNNING";
