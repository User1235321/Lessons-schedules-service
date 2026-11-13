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
