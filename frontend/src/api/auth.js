import { api, clearSession, refreshAccessToken, setAccessToken } from "./client.js";

// Вход и регистрация возвращают access token в теле, а refresh token — в httpOnly-cookie
async function authenticate(path, credentials) {
  const { access_token: token } = await api.post(path, credentials, { auth: false });
  setAccessToken(token);
  return token;
}

export const authApi = {
  register: (credentials) => authenticate("/auth/register", credentials),
  login: (credentials) => authenticate("/auth/login", credentials),
  refresh: refreshAccessToken,
  me: () => api.get("/auth/me"),

  // Локальная сессия очищается, даже если сервер не ответил: пользователь просил выйти
  async logout() {
    try {
      await api.post("/auth/logout", undefined, { auth: false });
    } finally {
      clearSession();
    }
  }
};
