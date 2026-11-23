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


export const DEFAULT_SETTINGS = {
  odd_week_days: ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"],
  even_week_days: ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"],
  time_mode: "HOUR_START",
  time_step_minutes: null,
  duration_mode: "UNIFORM",
  duration_minutes: 100
};

export const TEST_PROJECTS = [
  { id: "42", name: "Осенний семестр", created_at: "2026-09-01T10:00:00Z", updated_at: "2026-09-01T10:00:00Z" },
  { id: "43", name: "Весенний семестр", created_at: "2026-10-01T10:00:00Z", updated_at: "2026-10-01T10:00:00Z" }
];

function validateResource(name, values, items, ownId) {
  if ("name" in values) {
    const value = String(values.name).trim();
    if (!value) {
      return json(422, { code: "INVALID_VALUE", message: "Укажите название", details: { field: "name" } });
    }
    const candidates = name === "subgroups"
      ? items.filter((item) => item.group_id === values.group_id)
      : items;
    const taken = candidates.some((item) => item.id !== ownId && item.name?.toLowerCase() === value.toLowerCase());
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
  blockedDeletes = [],
  failedResourceLoads = [],
  job = { status: "QUEUED", progress: null, error_message: null },
  schedules = [{ id: "schedule-1", result_index: 1 }],
  optimizationCriteria = {}
} = {}) {
  const store = projects.map((project) => ({ ...structuredClone(DEFAULT_SETTINGS), ...project }));
  let nextId = 100;
  const collections = Object.fromEntries(
    Object.entries(resources).map(([name, items]) => [name, structuredClone(items)])
  );
  const collection = (name) => (collections[name] ??= []);
  const constraintCollections = new Map();
  const projectConstraints = (projectId) => {
    if (!constraintCollections.has(projectId)) {
      constraintCollections.set(projectId, structuredClone(
        resources.constraintsByProject?.[projectId] ?? resources.constraints ?? []
      ));
    }
    return constraintCollections.get(projectId);
  };
  const criteriaCollections = new Map(Object.entries(optimizationCriteria).map(
    ([projectId, criteria]) => [projectId, structuredClone(criteria)]
  ));

  const syncSubgroup = (subgroup) => {
    const group = collection("groups").find((entry) => entry.id === subgroup.group_id);
    if (!group) return;
    const nested = {
      id: subgroup.id,
      name: subgroup.name,
      student_count: subgroup.student_count,
      availability: subgroup.availability ?? []
    };
    const previous = group.subgroups ?? [];
    group.subgroups = previous.some((entry) => entry.id === subgroup.id)
      ? previous.map((entry) => (entry.id === subgroup.id ? nested : entry))
      : [...previous, nested];
  };

  const removeSubgroup = (subgroup) => {
    const group = collection("groups").find((entry) => entry.id === subgroup.group_id);
    if (group) group.subgroups = (group.subgroups ?? []).filter((entry) => entry.id !== subgroup.id);
  };

  const fetchMock = vi.fn(async (url, init = {}) => {
    const method = init.method ?? "GET";
    const body = init.body ? JSON.parse(init.body) : null;

    if (url === "/api/auth/password-reset/request" && method === "POST") {
      return json(202, { message: "Если аккаунт с таким адресом существует, мы отправим письмо для восстановления пароля." });
    }
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
    const schedulesUrl = url.match(/^\/api\/generation-jobs\/([^/]+)\/schedules$/);
    if (schedulesUrl && method === "GET") {
      if (schedulesUrl[1] !== "job-1") {
        return json(404, { code: "NOT_FOUND", message: "Задание не найдено", details: {} });
      }
      return job.status === "COMPLETED"
        ? json(200, schedules)
        : json(409, { code: "JOB_RESULTS_UNAVAILABLE", message: "Результаты недоступны", details: {} });
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
      const project = { ...structuredClone(DEFAULT_SETTINGS), id: String(nextId++), name, ...body, created_at: now, updated_at: now };
      store.push(project);
      return json(201, project);
    }
    const optimization = url.match(/^\/api\/projects\/([^/]+)\/optimization-criteria$/);
    if (optimization) {
      const projectId = optimization[1];
      if (method === "GET") return json(200, criteriaCollections.get(projectId) ?? []);
      if (method === "PUT") {
        criteriaCollections.set(projectId, structuredClone(body.criteria));
        return json(200, criteriaCollections.get(projectId));
      }
    }

    const resource = url.match(
      /^\/api\/projects\/([^/]+)\/(subjects|teachers|rooms|groups|subgroups|streams|workloads|constraints)(?:\/([^/]+))?$/
    );
    if (resource) {
      const [, projectId, name, id] = resource;
      const items = name === "constraints" ? projectConstraints(projectId) : collection(name);
      const index = id ? items.findIndex((item) => item.id === id) : -1;

      if (!id && method === "GET") {
        return failedResourceLoads.includes(name)
          ? json(500, { code: "LOAD_FAILED", message: "Не удалось загрузить ресурсы", details: {} })
          : json(200, items);
      }
      if (!id && method === "POST") {
        const invalid = validateResource(name, body, items, null);
        if (invalid) {
          return invalid;
        }
        const created = { ...body, id: String(nextId++) };
        if (name === "groups") {
          created.subgroups = [];
        }
        items.push(created);
        if (name === "subgroups") syncSubgroup(created);
        return json(201, created);
      }
      if (index === -1) {
        return notFound();
      }
      if (method === "DELETE") {
        if (blockedDeletes.includes(id)) {
          return json(409, { code: "IN_USE", message: "Используется в нагрузке", details: {} });
        }
        if (name === "subgroups") removeSubgroup(items[index]);
        items.splice(index, 1);
        return json(204);
      }
      if (method === "PATCH") {
        const invalid = validateResource(name, { ...items[index], ...body }, items, id);
        if (invalid) {
          return invalid;
        }
        items[index] = { ...items[index], ...body };
        if (name === "subgroups") syncSubgroup(items[index]);
        return json(200, items[index]);
      }
      return json(200, items[index]);
    }

    const match = url.match(/^\/api\/projects\/([^/]+)$/);
    if (match) {
      const index = store.findIndex((project) => project.id.toLowerCase() === decodeURIComponent(match[1]).toLowerCase());
      if (index === -1) {
        return notFound();
      }
      if (method === "DELETE") {
        store.splice(index, 1);
        return json(204);
      }
      if (method === "PATCH") {
        store[index] = { ...store[index], ...body, updated_at: new Date().toISOString() };
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
