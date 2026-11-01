import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { vi } from "vitest";

import AppProviders from "../src/app/AppProviders.jsx";
import { routes } from "../src/app/routes.jsx";

export const TEST_USER = { id: "u-1", email: "user@example.com" };

function json(status, body) {
  return new Response(body === undefined ? null : JSON.stringify(body), { status });
}

export const TEST_PROJECTS = [
  { id: "42", name: "Осенний семестр", created_at: "2026-09-01T10:00:00Z", updated_at: "2026-09-01T10:00:00Z" },
  { id: "43", name: "Весенний семестр", created_at: "2026-10-01T10:00:00Z", updated_at: "2026-10-01T10:00:00Z" }
];

const notFound = () => json(404, { code: "NOT_FOUND", message: "Проект не найден", details: {} });

// Минимальный бэкенд: auth и проекты в памяти. При authenticated: false refresh отвечает 401
export function stubBackend({ authenticated = true, projects = TEST_PROJECTS } = {}) {
  const store = projects.map((project) => ({ ...project }));
  let nextId = 100;

  const fetchMock = vi.fn(async (url, init = {}) => {
    const method = init.method ?? "GET";
    const body = init.body ? JSON.parse(init.body) : null;

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

    if (url === "/api/projects" && method === "GET") {
      return json(200, store);
    }
    if (url === "/api/projects" && method === "POST") {
      const name = body.name.trim();
      if (!name) {
        return json(422, {
          code: "INVALID_VALUE",
          message: "Укажите название проекта",
          details: { field: "name" }
        });
      }
      const now = new Date().toISOString();
      const project = { id: String(nextId++), name, created_at: now, updated_at: now };
      store.push(project);
      return json(201, project);
    }
    const match = url.match(/^\/api\/projects\/([^/]+)$/);
    if (match) {
      const index = store.findIndex((project) => project.id === decodeURIComponent(match[1]));
      if (index === -1) {
        return notFound();
      }
      if (method === "DELETE") {
        store.splice(index, 1);
        return json(204);
      }
      return json(200, store[index]);
    }

    return json(404, { code: "NOT_FOUND", message: "Не найдено", details: {} });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

// Рендерит приложение целиком с заданного URL на memory-роутере.
export function renderRoute(path, routeConfig = routes, backend = {}) {
  const fetchMock = stubBackend(backend);
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
