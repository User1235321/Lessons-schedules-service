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


export const TEST_PROJECTS = [
  { id: "42", name: "Осенний семестр", created_at: "2026-09-01T10:00:00Z", updated_at: "2026-09-01T10:00:00Z" },
  { id: "43", name: "Весенний семестр", created_at: "2026-10-01T10:00:00Z", updated_at: "2026-10-01T10:00:00Z" }
];

// Те же проверки названия, что на бэкенде: непустое и уникальное без учёта регистра
function validateResource(name, values, items, ownId) {
  if ("name" in values) {
    const value = String(values.name).trim();
    if (!value) {
      return json(422, { code: "INVALID_VALUE", message: "Укажите название", details: { field: "name" } });
    }
    const taken = items.some((item) => item.id !== ownId && item.name?.toLowerCase() === value.toLowerCase());
    if (taken) {
      return json(409, { code: "NAME_TAKEN", message: "Такое название уже есть", details: { field: "name" } });
    }
  }
  return null;
}

const notFound = () => json(404, { code: "NOT_FOUND", message: "Проект не найден", details: {} });

export function stubBackend({
  authenticated = true,
  projects = TEST_PROJECTS,
  resources = {},
  blockedDeletes = []
} = {}) {
  const store = projects.map((project) => ({ ...project }));
  let nextId = 100;
  // Коллекции проекта в памяти. Для простоты они общие для всех проектов
  const collections = Object.fromEntries(
    Object.entries(resources).map(([name, items]) => [name, items.map((item) => ({ ...item }))])
  );
  const collection = (name) => (collections[name] ??= []);

  const fetchMock = vi.fn(async (url, init = {}) => {
    const method = init.method ?? "GET";
    const body = init.body ? JSON.parse(init.body) : null;

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
    const resource = url.match(
      /^\/api\/projects\/[^/]+\/(subjects|teachers|rooms|groups|subgroups|streams|workloads|constraints)(?:\/([^/]+))?$/
    );
    if (resource) {
      const [, name, id] = resource;
      const items = collection(name);
      const index = id ? items.findIndex((item) => item.id === id) : -1;

      if (!id && method === "GET") {
        return json(200, items);
      }
      if (!id && method === "POST") {
        const invalid = validateResource(name, body, items, null);
        if (invalid) {
          return invalid;
        }
        const created = { ...body, id: String(nextId++) };
        items.push(created);
        return json(201, created);
      }
      if (index === -1) {
        return notFound();
      }
      if (method === "DELETE") {
        if (blockedDeletes.includes(id)) {
          return json(409, { code: "SUBJECT_IN_USE", message: "Дисциплина используется", details: {} });
        }
        items.splice(index, 1);
        return json(204);
      }
      if (method === "PATCH") {
        const invalid = validateResource(name, { ...items[index], ...body }, items, id);
        if (invalid) {
          return invalid;
        }
        items[index] = { ...items[index], ...body };
        return json(200, items[index]);
      }
      return json(200, items[index]);
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
