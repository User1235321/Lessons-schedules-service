import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { authApi } from "../src/api/auth.js";
import {
  api,
  ApiError,
  clearSession,
  getAccessToken,
  onSessionExpired,
  setAccessToken
} from "../src/api/client.js";

function jsonResponse(status, body) {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}

const unauthorized = () =>
  jsonResponse(401, { code: "NOT_AUTHENTICATED", message: "Требуется вход", details: {} });

// Токен в виде JWT без подписи: клиент читает из него только sub
function fakeJwt(sub, id) {
  const encode = (value) =>
    btoa(JSON.stringify(value)).replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
  return `${encode({ alg: "none" })}.${encode({ sub, id })}.signature`;
}

let fetchMock;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  clearSession();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function call(index) {
  const [url, init] = fetchMock.mock.calls[index];
  return { url, init };
}

describe("request", () => {
  it("sends JSON to the base URL with the access token and parses the response", async () => {
    setAccessToken("token-1");
    fetchMock.mockResolvedValueOnce(jsonResponse(201, { id: "p1" }));

    const result = await api.post("/projects", { name: "Осень" });

    expect(result).toEqual({ id: "p1" });
    const { url, init } = call(0);
    expect(url).toBe("/api/projects");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ name: "Осень" }));
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(init.headers.Authorization).toBe("Bearer token-1");
    expect(init.credentials).toBe("include");
  });

  it("returns null for 204 No Content", async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));

    await expect(api.delete("/projects/p1")).resolves.toBeNull();
  });

  it("throws ApiError with the backend error body", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(422, {
        code: "VALIDATION_ERROR",
        message: "Проверьте введённые данные",
        details: { fields: [{ field: "name", reason: "required" }] }
      })
    );

    const error = await api.post("/projects", {}).catch((e) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(422);
    expect(error.code).toBe("VALIDATION_ERROR");
    expect(error.message).toBe("Проверьте введённые данные");
    expect(error.details.fields[0].field).toBe("name");
  });

  it("wraps a response without the error format", async () => {
    fetchMock.mockResolvedValueOnce(new Response("Bad Gateway", { status: 502 }));

    const error = await api.get("/projects").catch((e) => e);

    expect(error).toMatchObject({ status: 502, code: "UNEXPECTED_RESPONSE" });
  });

  it("turns a network failure into NETWORK_ERROR", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    const error = await api.get("/projects").catch((e) => e);

    expect(error).toMatchObject({ status: 0, code: "NETWORK_ERROR" });
  });
});

describe("refresh on 401", () => {
  it("refreshes the access token once and retries the request", async () => {
    setAccessToken("expired");
    fetchMock
      .mockResolvedValueOnce(unauthorized())
      .mockResolvedValueOnce(jsonResponse(200, { access_token: "fresh" }))
      .mockResolvedValueOnce(jsonResponse(200, [{ id: "p1" }]));

    const result = await api.get("/projects");

    expect(result).toEqual([{ id: "p1" }]);
    expect(call(1).url).toBe("/api/auth/refresh");
    expect(call(1).init.headers.Authorization).toBeUndefined();
    expect(call(2).init.headers.Authorization).toBe("Bearer fresh");
    expect(getAccessToken()).toBe("fresh");
  });

  it("shares one refresh between parallel requests", async () => {
    fetchMock.mockImplementation(async (url, init) => {
      if (url === "/api/auth/refresh") {
        return jsonResponse(200, { access_token: "fresh" });
      }
      return init.headers.Authorization === "Bearer fresh"
        ? jsonResponse(200, { url })
        : unauthorized();
    });

    await Promise.all([api.get("/projects"), api.get("/auth/me")]);

    const refreshCalls = fetchMock.mock.calls.filter(([url]) => url === "/api/auth/refresh");
    expect(refreshCalls).toHaveLength(1);
  });

  it("logs out when refresh fails", async () => {
    setAccessToken("expired");
    const listener = vi.fn();
    const unsubscribe = onSessionExpired(listener);
    fetchMock.mockResolvedValueOnce(unauthorized()).mockResolvedValueOnce(unauthorized());

    const error = await api.get("/projects").catch((e) => e);
    unsubscribe();

    expect(error).toMatchObject({ status: 401, code: "NOT_AUTHENTICATED" });
    expect(listener).toHaveBeenCalledTimes(1);
    expect(getAccessToken()).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("does not refresh for requests without auth", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(401, { code: "INVALID_CREDENTIALS", message: "Неверный пароль", details: {} })
    );

    const error = await authApi.login({ email: "a@b.c", password: "x" }).catch((e) => e);

    expect(error.code).toBe("INVALID_CREDENTIALS");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("authApi", () => {
  it("stores the access token after login", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { access_token: "t", token_type: "bearer" }));

    await authApi.login({ email: "a@b.c", password: "secret" });

    expect(call(0).url).toBe("/api/auth/login");
    expect(getAccessToken()).toBe("t");
  });

  it("clears the session after the server confirms logout", async () => {
    setAccessToken("t");
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));

    await authApi.logout();

    expect(call(0).url).toBe("/api/auth/logout");
    expect(call(0).init.credentials).toBe("include");
    expect(getAccessToken()).toBeNull();
  });

  it("keeps the session when the server did not confirm logout", async () => {
    setAccessToken("t");
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    await expect(authApi.logout()).rejects.toMatchObject({ code: "NETWORK_ERROR" });

    expect(getAccessToken()).toBe("t");
  });

  it("keeps the session on a server error during logout", async () => {
    setAccessToken("t");
    fetchMock.mockResolvedValueOnce(
      jsonResponse(500, { code: "INTERNAL_ERROR", message: "Внутренняя ошибка сервера", details: {} })
    );

    await expect(authApi.logout()).rejects.toMatchObject({ status: 500, code: "INTERNAL_ERROR" });

    expect(getAccessToken()).toBe("t");
  });
});

// Две вкладки — два экземпляра модуля клиента. Общие у них только cookie (одна на браузер),
// блокировки Web Locks и BroadcastChannel, как в настоящем браузере
describe("refresh across tabs", () => {
  // Как в браузере: блокировка занята с момента запроса, ifAvailable не встаёт в очередь
  class FakeLockManager {
    #pending = 0;
    #tail = Promise.resolve();

    async request(name, options, callback) {
      if (typeof options === "function") {
        callback = options;
        options = {};
      }
      if (options.ifAvailable && this.#pending > 0) {
        return callback(null);
      }
      this.#pending += 1;
      const previous = this.#tail;
      let release;
      this.#tail = new Promise((resolve) => (release = resolve));
      await previous;
      try {
        return await callback({ name });
      } finally {
        this.#pending -= 1;
        release();
      }
    }
  }

  // Бэкенд с ротацией refresh-токена: старый сгорает при обмене, как в use case Refresh
  function fakeBackend() {
    // subject — владелец cookie: чей токен выдаст refresh
    const state = {
      cookie: "r1",
      current: "r1",
      issued: 0,
      subject: "user-1",
      refreshCalls: [],
      validTokens: new Set()
    };
    const delay = () => new Promise((resolve) => setTimeout(resolve, 10));

    state.fetch = vi.fn(async (url, init) => {
      if (url === "/api/auth/refresh") {
        const sent = state.cookie;
        state.refreshCalls.push(sent);
        await delay();
        if (sent !== state.current) {
          return jsonResponse(401, {
            code: "INVALID_REFRESH_TOKEN",
            message: "Сессия завершена, войдите снова",
            details: {}
          });
        }
        state.issued += 1;
        state.current = state.cookie = `r${state.issued + 1}`;
        const token = fakeJwt(state.subject, `access-${state.issued}`);
        state.validTokens.add(token);
        return jsonResponse(200, { access_token: token });
      }
      const token = init.headers.Authorization?.replace("Bearer ", "");
      return state.validTokens.has(token) ? jsonResponse(200, []) : unauthorized();
    });
    return state;
  }

  async function openTab() {
    vi.resetModules();
    return import("../src/api/client.js");
  }

  const expired = fakeJwt("user-1", "expired");
  let backend;

  beforeEach(() => {
    backend = fakeBackend();
    vi.stubGlobal("fetch", backend.fetch);
    vi.stubGlobal("navigator", { ...navigator, locks: new FakeLockManager() });
  });

  it("refreshes once when the access token expires in two tabs at the same time", async () => {
    const [tabA, tabB] = [await openTab(), await openTab()];
    tabA.setAccessToken(expired);
    tabB.setAccessToken(expired);
    const onExpired = vi.fn();
    tabA.onSessionExpired(onExpired);
    tabB.onSessionExpired(onExpired);

    await Promise.all([tabA.api.get("/projects"), tabB.api.get("/projects")]);

    expect(backend.refreshCalls).toEqual(["r1"]);
    expect(tabB.getAccessToken()).toBe(tabA.getAccessToken());
    expect(onExpired).not.toHaveBeenCalled();
  });

  it("never sends a refresh token that was already rotated", async () => {
    const tabs = [await openTab(), await openTab(), await openTab()];
    tabs.forEach((tab) => tab.setAccessToken(expired));

    await Promise.all(tabs.flatMap((tab) => [tab.api.get("/projects"), tab.api.get("/projects")]));

    expect(backend.refreshCalls).toEqual(["r1"]);
  });

  it("shares the new token with tabs that did not refresh", async () => {
    const [tabA, tabB] = [await openTab(), await openTab()];
    tabB.setAccessToken(expired);

    const token = await tabA.refreshAccessToken();
    await vi.waitFor(() => expect(tabB.getAccessToken()).toBe(token));
  });

  it("refreshes itself with the rotated cookie when the other tab failed", async () => {
    const [tabA, tabB] = [await openTab(), await openTab()];
    const respond = backend.fetch.getMockImplementation();
    backend.fetch.mockImplementationOnce(async () => {
      await new Promise((resolve) => setTimeout(resolve, 10));
      throw new TypeError("Failed to fetch");
    });
    backend.fetch.mockImplementation(respond);

    const results = await Promise.allSettled([
      tabA.refreshAccessToken(),
      tabB.refreshAccessToken()
    ]);

    expect(results[0]).toMatchObject({ status: "rejected", reason: { code: "NETWORK_ERROR" } });
    expect(results[1]).toMatchObject({ status: "fulfilled" });
    expect(results[1].value).toBe(tabB.getAccessToken());
  });

  it("does not give a token to a tab that signed out", async () => {
    const [tabA, tabB, control] = [await openTab(), await openTab(), await openTab()];
    [tabA, tabB, control].forEach((tab) => tab.setAccessToken(expired));
    tabB.clearSession(); // вкладка B вышла

    // expired — токен, с которым запрос получил 401, поэтому A идёт на сервер за новым
    const token = await tabA.refreshAccessToken(expired);
    expect(token).not.toBe(expired);

    // control получила токен, значит сообщение дошло и до B, но B его не взяла
    await vi.waitFor(() => expect(control.getAccessToken()).toBe(token));
    expect(tabB.getAccessToken()).toBeNull();
  });

  it("does not give a token to a tab with another account", async () => {
    const [tabA, tabB, control] = [await openTab(), await openTab(), await openTab()];
    const otherAccount = fakeJwt("user-2", "own");
    tabA.setAccessToken(expired);
    control.setAccessToken(expired);
    tabB.setAccessToken(otherAccount);

    const token = await tabA.refreshAccessToken(expired);
    expect(token).not.toBe(expired);

    await vi.waitFor(() => expect(control.getAccessToken()).toBe(token));
    expect(tabB.getAccessToken()).toBe(otherAccount);
  });

  it("does not switch accounts silently when the cookie belongs to another user", async () => {
    const tab = await openTab();
    const onExpired = vi.fn();
    tab.onSessionExpired(onExpired);
    tab.setAccessToken(expired);
    backend.subject = "user-2"; // в другой вкладке вошли под другой учётной записью

    const error = await tab.api.get("/projects").catch((e) => e);

    expect(error).toMatchObject({ code: "SESSION_CHANGED" });
    expect(tab.getAccessToken()).toBeNull();
    expect(onExpired).toHaveBeenCalledTimes(1);
  });

  it("a waiting tab does not take a token of another account", async () => {
    const [tabA, tabB] = [await openTab(), await openTab()];
    tabA.setAccessToken(fakeJwt("user-2", "old"));
    tabB.setAccessToken(fakeJwt("user-1", "old"));
    backend.subject = "user-2"; // cookie уже принадлежит user-2

    // A обменивает токен, B ждёт, получает токен user-2, не берёт его и обменивает сам
    const results = await Promise.allSettled([
      tabA.refreshAccessToken(fakeJwt("user-2", "old")),
      tabB.refreshAccessToken(fakeJwt("user-1", "old"))
    ]);

    expect(results[0].status).toBe("fulfilled");
    expect(results[1]).toMatchObject({ status: "rejected", reason: { code: "SESSION_CHANGED" } });
    expect(tabB.getAccessToken()).toBeNull();
  });

  it("without Web Locks the second tab would hit a rotated token", async () => {
    vi.stubGlobal("navigator", { ...navigator, locks: undefined });
    const [tabA, tabB] = [await openTab(), await openTab()];
    tabA.setAccessToken(expired);
    tabB.setAccessToken(expired);

    const results = await Promise.allSettled([tabA.api.get("/projects"), tabB.api.get("/projects")]);

    expect(results.map((result) => result.status).sort()).toEqual(["fulfilled", "rejected"]);
    expect(backend.refreshCalls).toEqual(["r1", "r1"]);
  });
});
