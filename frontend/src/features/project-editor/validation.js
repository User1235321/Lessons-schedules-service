// Правила совпадают с backend (domain/academic/names.py): название без пробелов по краям,
// непустое и не длиннее 200 символов
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

// Предел хранения на backend (колонка integer), а не правило предметной области
export const MAX_STUDENT_COUNT = 2 ** 31 - 1;

// Положительное целое (F_Valid_1). Принимает строку из поля ввода
export function validatePositiveInteger(value, invalid) {
  const text = String(value).trim();
  if (!/^\d+$/.test(text) || Number(text) <= 0) {
    return invalid;
  }
  if (Number(text) > MAX_STUDENT_COUNT) {
    return "Слишком большое число";
  }
  return null;
}

export function validateStudentCount(value) {
  return validatePositiveInteger(value, "Нужно положительное целое число студентов");
}
