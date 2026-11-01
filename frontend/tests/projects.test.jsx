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
});
