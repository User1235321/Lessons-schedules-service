export const MAX_NAME_LENGTH = 200;

export function validateName(name, missing) {
  const value = name.trim();
  if (!value) {
    return missing;
  }
  if (value.length > MAX_NAME_LENGTH) {
    return `Не длиннее ${MAX_NAME_LENGTH} символов`;
  }
  return null;
}

export const MAX_STUDENT_COUNT = 2 ** 31 - 1;

export function validateStudentCount(value) {
  const text = String(value).trim();
  if (!/^\d+$/.test(text) || Number(text) <= 0) {
    return "Нужно положительное целое число студентов";
  }
  if (Number(text) > MAX_STUDENT_COUNT) {
    return "Слишком большое число";
  }
  return null;
}
