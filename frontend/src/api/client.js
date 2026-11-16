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

// Refresh-токен один на все вкладки (общая cookie), а бэкенд при обмене сжигает старый.
// Если две вкладки отправят его одновременно, вторая получит 401 и разлогинит пользователя.
// Поэтому обмен идёт под блокировкой Web Locks, общей для вкладок, а результат
// рассылается остальным через BroadcastChannel.
const REFRESH_LOCK = "auth-refresh";
// Сколько ждать результат вкладки, которая держала блокировку: сообщение между вкладками
// может прийти чуть позже, чем освободится блокировка
export const BROADCAST_WAIT_MS = 500;

const channel = typeof BroadcastChannel === "function" ? new BroadcastChannel("auth") : null;

// Идентификатор пользователя из access JWT (claim sub) или null, если токен не разобрать.
// Подпись здесь не проверяется: это не защита, а способ понять, чей токен пришёл
function tokenSubject(token) {
  try {
    const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const { sub } = JSON.parse(atob(payload));
    return typeof sub === "string" ? sub : null;
  } catch {
    return null;
  }
}

// Токен из другой вкладки годится, только если у этой вкладки есть сессия и она того же
// пользователя. Вышедшая вкладка и вкладка, где вошли под другой учётной записью, его не берут
function belongsToThisSession(token) {
  const own = accessToken && tokenSubject(accessToken);
  return Boolean(own) && own === tokenSubject(token);
}

// Вкладки, которые ждут итог refresh в другой вкладке. Каждая получает новый токен или null
const waiters = new Set();

channel?.addEventListener("message", ({ data }) => {
  if (data?.type === "refreshed") {
    const accepted = belongsToThisSession(data.token);
    if (accepted) {
      setAccessToken(data.token);
    }
    // Чужой токен ждущей вкладке не нужен: она обновит свой сама
    waiters.forEach((finish) => finish(accepted ? data.token : null));
  } else if (data?.type === "refresh-failed") {
    waiters.forEach((finish) => finish(null));
  }
});

// Ждёт итог refresh в другой вкладке: новый токен или null, если там не вышло,
// токен чужой или время истекло
function waitForOtherTab() {
  let finish;
  const result = new Promise((resolve) => {
    const timer = setTimeout(() => finish(null), BROADCAST_WAIT_MS);
    finish = (token) => {
      clearTimeout(timer);
      waiters.delete(finish);
      resolve(token);
    };
    waiters.add(finish);
  });
  return { result, cancel: () => finish(null) };
}

async function exchangeRefreshToken() {
  try {
    const response = await send("/auth/refresh", { method: "POST", auth: false });
    if (!response.ok) {
      throw await toApiError(response);
    }
    const { access_token: token } = await readBody(response);

    // Cookie общая на все вкладки. Если в другой вкладке вошли под другой учётной записью,
    // cookie уже её, и молча подменить пользователя в этой вкладке нельзя
    const own = accessToken && tokenSubject(accessToken);
    if (own && own !== tokenSubject(token)) {
      throw new ApiError({
        status: 401,
        code: "SESSION_CHANGED",
        message: "В другой вкладке выполнен вход под другой учётной записью. Войдите заново"
      });
    }

    setAccessToken(token);
    channel?.postMessage({ type: "refreshed", token });
    return token;
  } catch (error) {
    channel?.postMessage({ type: "refresh-failed" });
    throw error;
  }
}

async function refreshAcrossTabs(staleToken) {
  // Токен уже обновили, пока запрос ждал ответа: эта вкладка или сообщение из другой
  const isFresh = () => accessToken !== null && accessToken !== staleToken;

  // Без Web Locks (старый браузер) остаётся защита только внутри вкладки
  if (!navigator.locks) {
    return exchangeRefreshToken();
  }

  const BUSY = Symbol("busy");
  const first = await navigator.locks.request(REFRESH_LOCK, { ifAvailable: true }, (lock) => {
    if (!lock) {
      return BUSY;
    }
    return isFresh() ? accessToken : exchangeRefreshToken();
  });
  if (first !== BUSY) {
    return first;
  }

  // Другая вкладка уже обменивает токен. Ждём блокировку и её результат.
  // Если результата нет, обмен идёт с cookie, которую та вкладка оставила, — она ещё не сожжена
  const otherTab = waitForOtherTab();
  return navigator.locks.request(REFRESH_LOCK, async () => {
    if (isFresh()) {
      otherTab.cancel();
      return accessToken;
    }
    const token = await otherTab.result;
    return token ?? exchangeRefreshToken();
  });
}

// staleToken — access token, с которым запрос получил 401.
// Параллельные запросы внутри вкладки ждут один общий refresh.
export function refreshAccessToken(staleToken = null) {
  refreshPromise ??= refreshAcrossTabs(staleToken)
    .catch((error) => {
      expireSession();
      throw error;
    })
    .finally(() => {
      refreshPromise = null;
    });
  return refreshPromise;
}

// Запрос к API. Возвращает разобранное тело ответа (null для 204) или бросает ApiError.
// auth: false — для запросов без access token (вход, регистрация): их 401 не ведёт к refresh.
export async function request(path, options = {}) {
  const { auth = true } = options;
  const usedToken = accessToken;
  let response = await send(path, options);

  if (response.status === 401 && auth) {
    await refreshAccessToken(usedToken);
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
