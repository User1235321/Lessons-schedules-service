// Те же правила, что на бэкенде (domain/auth/user.py): форма не отправляет заведомо
// неверные данные, но окончательно всё проверяет сервер.

export const MIN_PASSWORD_LENGTH = 6;
export const MAX_PASSWORD_LENGTH = 20;
const MAX_EMAIL_LENGTH = 254;
const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export function validateEmail(email) {
  const value = email.trim();
  if (!value) {
    return "Укажите адрес электронной почты";
  }
  if (value.length > MAX_EMAIL_LENGTH) {
    return `Адрес длиннее ${MAX_EMAIL_LENGTH} символов`;
  }
  if (!EMAIL_PATTERN.test(value)) {
    return "Некорректный адрес электронной почты";
  }
  return null;
}

// Длина проверяется только у нового пароля (F_Auth_2). При входе любой неподходящий
// пароль просто окажется неверным
export function validateNewPassword(password) {
  if (password.length < MIN_PASSWORD_LENGTH || password.length > MAX_PASSWORD_LENGTH) {
    return `Пароль должен содержать от ${MIN_PASSWORD_LENGTH} до ${MAX_PASSWORD_LENGTH} символов`;
  }
  return null;
}

export function validatePassword(password) {
  return password ? null : "Введите пароль";
}

// Ошибки по полям без пустых значений. Пустой объект — форма валидна
export function collectErrors(checks) {
  return Object.fromEntries(Object.entries(checks).filter(([, error]) => error));
}
