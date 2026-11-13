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

const notFound = () => json(404, { code: "NOT_FOUND", message: "Проект не найден", details: {} });

export function stubBackend({
  authenticated = true,
  projects = TEST_PROJECTS,
  // Состояние задания расчёта: тест меняет поля, чтобы «продвинуть» расчёт
  job = { status: "QUEUED", progress: null, error_message: null }
} = {}) {
  const store = projects.map((project) => ({ ...project }));
  let nextId = 100;

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

    if (/^\/api\/projects\/[^/]+\/generation-jobs$/.test(url) && method === "POST") {
      if (body.result_mode === "TOP_N" && !(body.top_n > 0)) {
        return json(422, {
          code: "INVALID_VALUE",
          message: "Для TOP_N нужно положительное число вариантов",
          details: { field: "top_n" }
        });
      }
      job.status = "QUEUED";
      return json(202, { job_id: "job-1", status: "QUEUED" });
    }
    const jobUrl = url.match(/^\/api\/generation-jobs\/([^/]+)(\/cancel)?$/);
    if (jobUrl) {
      if (jobUrl[1] !== "job-1") {
        return json(404, { code: "NOT_FOUND", message: "Задание не найдено", details: {} });
      }
      if (jobUrl[2]) {
        if (!["QUEUED", "RUNNING"].includes(job.status)) {
          return json(409, {
            code: "JOB_NOT_CANCELLABLE",
            message: "Расчёт уже завершён и не может быть отменён",
            details: {}
          });
        }
        job.status = "CANCELLED";
      }
      return json(jobUrl[2] ? 202 : 200, {
        id: "job-1",
        project_id: "42",
        job_type: "GENERATE",
        ...job
      });
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
