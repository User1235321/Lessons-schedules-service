import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { validateProjectName } from "../src/features/projects/validation.js";
import { findHeading, renderRoute } from "./renderRoute.jsx";

function projectList() {
  return screen.findByRole("list", { name: "Проекты" });
}

describe("validateProjectName", () => {
  it("requires a non-empty name (F_Project_1)", () => {
    expect(validateProjectName("   ")).toBe("Укажите название проекта");
    expect(validateProjectName("x".repeat(201))).toBe("Название длиннее 200 символов");
    expect(validateProjectName(" Осень ")).toBeNull();
  });
});

describe("ProjectsPage", () => {
  it("lists the user's projects", async () => {
    renderRoute("/projects");

    const list = await projectList();
    expect(within(list).getByText("Осенний семестр")).toBeTruthy();
    expect(within(list).getByText("Весенний семестр")).toBeTruthy();
  });

  it("shows an empty state", async () => {
    renderRoute("/projects", undefined, { projects: [] });

    expect(await screen.findByText(/Проектов пока нет/)).toBeTruthy();
  });

  it("shows a load error and retries", async () => {
    const { user, fetchMock } = renderRoute("/projects");
    const respond = fetchMock.getMockImplementation();
    fetchMock.mockImplementation(async (url, init) =>
      url === "/api/projects" ? Promise.reject(new TypeError("Failed to fetch")) : respond(url, init)
    );
    await findHeading("Мои проекты");

    expect(await screen.findByText("Не удалось загрузить проекты")).toBeTruthy();

    fetchMock.mockImplementation(respond);
    await user.click(screen.getByRole("button", { name: "Повторить" }));

    expect(within(await projectList()).getByText("Осенний семестр")).toBeTruthy();
  });
  it("requires a project name and does not call the API without it (F_Project_1)", async () => {
    const { user, fetchMock } = renderRoute("/projects");
    await projectList();

    await user.click(screen.getByRole("button", { name: "Создать проект" }));
    const dialog = await screen.findByRole("dialog", { name: "Новый проект" });
    await user.type(within(dialog).getByLabelText("Название проекта"), "   ");
    await user.click(within(dialog).getByRole("button", { name: "Создать" }));

    expect(within(dialog).getByText("Укажите название проекта")).toBeTruthy();
    const posts = fetchMock.mock.calls.filter(
      ([url, init]) => url === "/api/projects" && init?.method === "POST"
    );
    expect(posts).toHaveLength(0);
  });

  it("creates a project and opens it", async () => {
    const { user, router, fetchMock } = renderRoute("/projects");
    await projectList();

    await user.click(screen.getByRole("button", { name: "Создать проект" }));
    const dialog = await screen.findByRole("dialog", { name: "Новый проект" });
    await user.type(within(dialog).getByLabelText("Название проекта"), "  Летняя сессия ");
    await user.click(within(dialog).getByRole("button", { name: "Создать" }));

    expect(await findHeading("Преподаватели")).toBeTruthy();
    expect(router.state.location.pathname).toBe("/projects/100/teachers");
    const [, init] = fetchMock.mock.calls.find(
      ([url, options]) => url === "/api/projects" && options?.method === "POST"
    );
    expect(JSON.parse(init.body)).toEqual({ name: "Летняя сессия" });
  });
});
