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

  it("clears the session on logout even if the server fails", async () => {
    setAccessToken("t");
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    await expect(authApi.logout()).rejects.toMatchObject({ code: "NETWORK_ERROR" });

    expect(call(0).url).toBe("/api/auth/logout");
    expect(getAccessToken()).toBeNull();
  });
});
