import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { authApi } from "../../api/auth.js";
import { onSessionExpired } from "../../api/client.js";

const AuthContext = createContext(null);

// status: "loading" — сессия ещё восстанавливается, "authenticated" или "anonymous"
export function AuthProvider({ children }) {
  const [state, setState] = useState({ status: "loading", user: null });

  const loadUser = useCallback(async () => {
    const user = await authApi.me();
    setState({ status: "authenticated", user });
  }, []);

  useEffect(() => {
    // Access token в памяти теряется при перезагрузке, сессию восстанавливаем по refresh-cookie
    authApi
      .refresh()
      .then(loadUser)
      .catch(() => setState({ status: "anonymous", user: null }));

    return onSessionExpired(() => setState({ status: "anonymous", user: null }));
  }, [loadUser]);

  const value = useMemo(
    () => ({
      ...state,
      login: async (credentials) => {
        await authApi.login(credentials);
        await loadUser();
      },
      register: async (credentials) => {
        await authApi.register(credentials);
        await loadUser();
      },
      logout: async () => {
        try {
          await authApi.logout();
        } catch {
          // Локальная сессия уже очищена, ошибка сервера выходу не мешает
        }
        setState({ status: "anonymous", user: null });
      }
    }),
    [state, loadUser]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth используется вне AuthProvider");
  }
  return context;
}
