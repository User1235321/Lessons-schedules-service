// Те же правила, что у Project на бэкенде (domain/projects/project.py)
export const MAX_PROJECT_NAME_LENGTH = 200;

export function validateProjectName(name) {
  const value = name.trim();
  if (!value) {
    return "Укажите название проекта"; // F_Project_1
  }
  if (value.length > MAX_PROJECT_NAME_LENGTH) {
    return `Название длиннее ${MAX_PROJECT_NAME_LENGTH} символов`;
  }
  return null;
}
