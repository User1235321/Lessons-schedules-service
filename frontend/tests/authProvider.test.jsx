import { act, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { api, getAccessToken } from "../src/api/client.js";
import { AuthProvider, useAuth } from "../src/features/auth/AuthProvider.jsx";
import { stubAuthBackend, TEST_USER } from "./renderRoute.jsx";

let auth;

function Probe() {
  auth = useAuth();
  return <p>{auth.status}</p>;
}

function renderProvider() {
  render(
    <AuthProvider>
      <Probe />
    </AuthProvider>
  );
}

describe("AuthProvider", () => {
  it("restores the session through refresh", async () => {
    stubAuthBackend();
    renderProvider();

    expect(screen.getByText("loading")).toBeTruthy();
    expect(await screen.findByText("authenticated")).toBeTruthy();
    expect(auth.user).toEqual(TEST_USER);
  });

  it("stays anonymous when there is no session", async () => {
    stubAuthBackend({ authenticated: false });
    renderProvider();

    expect(await screen.findByText("anonymous")).toBeTruthy();
    expect(auth.user).toBeNull();
  });

  it("logs in and loads the user", async () => {
    const fetchMock = stubAuthBackend({ authenticated: false });
    renderProvider();
    await screen.findByText("anonymous");

    fetchMock.mockImplementation(async (url) =>
      url === "/api/auth/me"
        ? new Response(JSON.stringify(TEST_USER), { status: 200 })
        : new Response(JSON.stringify({ access_token: "t" }), { status: 200 })
    );
    await act(() => auth.login({ email: TEST_USER.email, password: "secret" }));

    expect(screen.getByText("authenticated")).toBeTruthy();
    expect(getAccessToken()).toBe("t");
  });

  it("becomes anonymous when the session expires", async () => {
    const fetchMock = stubAuthBackend();
    renderProvider();
    await screen.findByText("authenticated");

    // Любой запрос получает 401, refresh тоже
    fetchMock.mockImplementation(
      async () =>
        new Response(JSON.stringify({ code: "NOT_AUTHENTICATED", message: "", details: {} }), {
          status: 401
        })
    );
    await act(() => api.get("/projects").catch(() => {}));

    await waitFor(() => expect(screen.getByText("anonymous")).toBeTruthy());
    expect(getAccessToken()).toBeNull();
  });
});
