import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { vi } from "vitest";

import AppProviders from "../src/app/AppProviders.jsx";
import { routes } from "../src/app/routes.jsx";

export const TEST_USER = { id: "u-1", email: "user@example.com" };
export const TEST_PASSWORD = "secret";
export const TAKEN_EMAIL = "taken@example.com";

function json(status, body) {
  return new Response(body === undefined ? null : JSON.stringify(body), { status });
}

// Минимальный бэкенд для auth: при authenticated: false refresh отвечает 401.
// Вход проходит только с TEST_USER и TEST_PASSWORD, регистрация — с любым адресом, кроме TAKEN_EMAIL
export function stubAuthBackend({ authenticated = true } = {}) {
  const fetchMock = vi.fn(async (url, init) => {
    const body = init?.body ? JSON.parse(init.body) : null;
    if (url === "/api/auth/login") {
      return body.email === TEST_USER.email && body.password === TEST_PASSWORD
        ? json(200, { access_token: "test-token" })
        : json(401, {
            code: "INVALID_CREDENTIALS",
            message: "Неверный адрес или пароль",
            details: {}
          });
    }
    if (url === "/api/auth/register") {
      return body.email === TAKEN_EMAIL
        ? json(409, { code: "EMAIL_ALREADY_REGISTERED", message: "Адрес занят", details: {} })
        : json(201, { access_token: "test-token" });
    }
    if (url === "/api/auth/refresh") {
      return authenticated
        ? json(200, { access_token: "test-token" })
        : json(401, { code: "NOT_AUTHENTICATED", message: "Требуется вход", details: {} });
    }
    if (url === "/api/auth/me") {
      return json(200, TEST_USER);
    }
    if (url === "/api/auth/logout") {
      return json(204);
    }
    return json(404, { code: "NOT_FOUND", message: "Не найдено", details: {} });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

// Рендерит приложение целиком с заданного URL на memory-роутере.
export function renderRoute(path, routeConfig = routes, { authenticated = true } = {}) {
  const fetchMock = stubAuthBackend({ authenticated });
  const router = createMemoryRouter(routeConfig, { initialEntries: [path] });
  const user = userEvent.setup();

  render(
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  );

  return { router, user, fetchMock };
}

// Страницы грузятся лениво, поэтому даём запас по времени на первый import().
export function findHeading(name) {
  return screen.findByRole("heading", { name }, { timeout: 3000 });
}
