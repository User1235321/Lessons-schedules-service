import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { findHeading, renderRoute, TEST_PROJECTS } from "./renderRoute.jsx";

// implemented: раздел уже работает с API и не показывает заглушку «В разработке»
const editorSections = [
  { path: "teachers", label: "Преподаватели", heading: "Преподаватели", implemented: true },
  { path: "rooms", label: "Аудитории", heading: "Аудитории" },
  { path: "groups", label: "Группы", heading: "Группы и подгруппы" },
  { path: "streams", label: "Потоки", heading: "Потоки" },
  { path: "workloads", label: "Нагрузка", heading: "Учебная нагрузка" },
  { path: "constraints", label: "Ограничения", heading: "Ограничения" },
  { path: "optimization", label: "Оптимизация", heading: "Оптимизация" }
];

describe("project editor", () => {
  describe.each(TEST_PROJECTS)("project $id", (project) => {
    it.each(editorSections)("opens $path by direct URL", async (section) => {
      const pathname = `/projects/${project.id}/${section.path}`;
      const { router, fetchMock } = renderRoute(pathname);

      expect(await findHeading(section.heading)).toBeTruthy();
      expect(screen.getByRole("heading", { level: 1, name: project.name })).toBeTruthy();
      expect(router.state.location.pathname).toBe(pathname);
      expect(screen.getByRole("tab", { name: section.label, selected: true })).toBeTruthy();
      if (!section.implemented) {
        expect(screen.getByText("В разработке")).toBeTruthy();
        expect(screen.getByRole("list", { name: "Планируемые функции" })).toBeTruthy();
      }
      expect(fetchMock).toHaveBeenCalledWith(`/api/projects/${project.id}`, expect.anything());
    });

    it("switches all seven sections without losing the project", async () => {
      const { user, router, fetchMock } = renderRoute(`/projects/${project.id}/teachers`);
      await findHeading("Преподаватели");

      const navigation = screen.getByRole("navigation", { name: "Разделы проекта" });
      for (const section of editorSections) {
        const tab = within(navigation).getByRole("tab", { name: section.label });
        expect(tab.getAttribute("href")).toBe(`/projects/${project.id}/${section.path}`);

        await user.click(tab);

        expect(await findHeading(section.heading)).toBeTruthy();
        expect(router.state.location.pathname).toBe(`/projects/${project.id}/${section.path}`);
        expect(screen.getByRole("heading", { level: 1, name: project.name })).toBeTruthy();
        expect(within(navigation).getAllByRole("tab", { selected: true })).toHaveLength(1);
        expect(tab.getAttribute("aria-selected")).toBe("true");
      }

      // Проект грузится один раз; запросы данных разделов идут по адресам глубже
      const projectRequests = fetchMock.mock.calls.filter(([url]) => /^\/api\/projects\/[^/]+$/.test(url));
      expect(projectRequests.map(([url]) => url)).toEqual([`/api/projects/${project.id}`]);
    });
  });

  it("keeps mandatory constraints separate from optimization criteria", async () => {
    const { user } = renderRoute("/projects/42/constraints");
    await findHeading("Ограничения");

    expect(screen.getByText(/Дополнительные обязательные ограничения/)).toBeTruthy();
    expect(screen.queryByText(/Выбор критериев оптимизации/)).toBeNull();
    expect(screen.queryByText(/Порядок приоритетов критериев/)).toBeNull();

    await user.click(screen.getByRole("tab", { name: "Оптимизация" }));
    await findHeading("Оптимизация");

    expect(screen.getByText(/Выбор критериев оптимизации/)).toBeTruthy();
    expect(screen.getByText(/Порядок приоритетов критериев/)).toBeTruthy();
    expect(screen.queryByText(/Дополнительные обязательные ограничения/)).toBeNull();
  });

  it.each([
    { path: "subjects", label: "Дисциплины", heading: "Дисциплины" },
    { path: "generation", label: "Расчёт", heading: "Построение расписания" },
    { path: "schedules", label: "Расписания", heading: "Расписания" },
    { path: "files", label: "Файлы", heading: "Импорт и экспорт" },
    { path: "settings", label: "Настройки", heading: "Настройки проекта" }
  ])("preserves the $path tab", async (section) => {
    const { user, router } = renderRoute("/projects/43/optimization");
    await findHeading("Оптимизация");

    await user.click(screen.getByRole("tab", { name: section.label }));

    expect(await findHeading(section.heading)).toBeTruthy();
    expect(router.state.location.pathname).toBe(`/projects/43/${section.path}`);
    expect(screen.getByRole("tab", { name: section.label, selected: true })).toBeTruthy();
  });

  it("opens generation from the calculate action in optimization", async () => {
    const { user, router } = renderRoute("/projects/43/optimization");
    await findHeading("Оптимизация");

    await user.click(screen.getByRole("link", { name: "Рассчитать" }));

    expect(await findHeading("Построение расписания")).toBeTruthy();
    expect(router.state.location.pathname).toBe("/projects/43/generation");
    expect(screen.getByRole("tab", { name: "Расчёт", selected: true })).toBeTruthy();
  });

  it.each(["constraints", "optimization"])("hides %s for an unavailable project", async (section) => {
    renderRoute(`/projects/999/${section}`);

    expect(await findHeading("Страница не найдена")).toBeTruthy();
    expect(screen.queryByRole("navigation", { name: "Разделы проекта" })).toBeNull();
    expect(screen.queryByText("В разработке")).toBeNull();
  });

  it("requires authentication for a direct optimization URL", async () => {
    const { router, fetchMock } = renderRoute("/projects/42/optimization", undefined, {
      authenticated: false
    });

    expect(await findHeading("Вход")).toBeTruthy();
    expect(router.state.location.state.from.pathname).toBe("/projects/42/optimization");
    expect(fetchMock.mock.calls.some(([url]) => url === "/api/projects/42")).toBe(false);
  });
});
