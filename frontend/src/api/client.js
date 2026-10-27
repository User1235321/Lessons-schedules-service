// HTTP-клиент для backend API: JSON-запросы, единый формат ошибок (HLD 10)
// и авторизация access JWT + refresh token (HLD 8).

// В деве запросы на /api проксирует Vite. Для другого адреса API задаётся VITE_API_BASE_URL
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(/\/$/, "");

// Ошибка ответа в форме { code, message, details }. Сетевые сбои и ответы без этого тела
// приводятся к той же форме, чтобы UI обрабатывал все ошибки одинаково.
export class ApiError extends Error {
  constructor({ status, code, message, details = {} }) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

// Access token живёт только в памяти: localStorage доступен скрипту, внедрённому через XSS.
// После перезагрузки страницы токен восстанавливается через refresh (cookie httpOnly).
let accessToken = null;
let refreshPromise = null;
const sessionExpiredListeners = new Set();

export function getAccessToken() {
  return accessToken;
}

export function setAccessToken(token) {
  accessToken = token;
}

export function clearSession() {
  accessToken = null;
}

// Вызывается, когда refresh не удался и пользователь разлогинен. Возвращает функцию отписки
export function onSessionExpired(listener) {
  sessionExpiredListeners.add(listener);
  return () => sessionExpiredListeners.delete(listener);
}

function expireSession() {
  clearSession();
  sessionExpiredListeners.forEach((listener) => listener());
}

async function readBody(response) {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function send(path, { method = "GET", body, headers = {}, auth = true, signal }) {
  const requestHeaders = { Accept: "application/json", ...headers };
  if (body !== undefined) {
    requestHeaders["Content-Type"] = "application/json";
  }
  if (auth && accessToken) {
    requestHeaders.Authorization = `Bearer ${accessToken}`;
  }

  try {
    return await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: requestHeaders,
      body: body === undefined ? undefined : JSON.stringify(body),
      // Refresh-cookie нужна для /auth/refresh и /auth/logout
      credentials: "include",
      signal
    });
  } catch (error) {
    if (error.name === "AbortError") {
      throw error;
    }
    throw new ApiError({
      status: 0,
      code: "NETWORK_ERROR",
      message: "Сервер недоступен. Проверьте подключение и повторите попытку"
    });
  }
}

async function toApiError(response) {
  const body = await readBody(response);
  if (body && typeof body === "object" && typeof body.code === "string") {
    return new ApiError({ status: response.status, ...body });
  }
  return new ApiError({
    status: response.status,
    code: "UNEXPECTED_RESPONSE",
    message: `Сервер вернул ошибку ${response.status}`
  });
}

// Параллельные запросы, получившие 401, ждут один общий refresh, а не запускают свой:
// refresh меняет токен в cookie, и второй запрос пришёл бы уже с отозванным.
export function refreshAccessToken() {
  refreshPromise ??= (async () => {
    try {
      const response = await send("/auth/refresh", { method: "POST", auth: false });
      if (!response.ok) {
        throw await toApiError(response);
      }
      const { access_token: token } = await readBody(response);
      setAccessToken(token);
      return token;
    } catch (error) {
      expireSession();
      throw error;
    } finally {
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

// Запрос к API. Возвращает разобранное тело ответа (null для 204) или бросает ApiError.
// auth: false — для запросов без access token (вход, регистрация): их 401 не ведёт к refresh.
export async function request(path, options = {}) {
  const { auth = true } = options;
  let response = await send(path, options);

  if (response.status === 401 && auth) {
    await refreshAccessToken();
    response = await send(path, options);
  }

  if (!response.ok) {
    throw await toApiError(response);
  }
  return readBody(response);
}

export const api = {
  get: (path, options) => request(path, { ...options, method: "GET" }),
  post: (path, body, options) => request(path, { ...options, method: "POST", body }),
  patch: (path, body, options) => request(path, { ...options, method: "PATCH", body }),
  put: (path, body, options) => request(path, { ...options, method: "PUT", body }),
  delete: (path, options) => request(path, { ...options, method: "DELETE" })
};
