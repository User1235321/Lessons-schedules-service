import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { findHeading, renderRoute } from "./renderRoute.jsx";

describe("routing", () => {
  it("redirects root to the projects list", async () => {
    const { router } = renderRoute("/");

    expect(await findHeading("Мои проекты")).toBeTruthy();
    expect(router.state.location.pathname).toBe("/projects");
  });

  it("renders auth pages inside the auth layout", async () => {
    renderRoute("/login", undefined, { authenticated: false });

    expect(await findHeading("Вход")).toBeTruthy();
    expect(screen.queryByRole("banner")).toBeNull();
  });

  it("navigates between auth pages", async () => {
    const { user, router } = renderRoute("/login", undefined, { authenticated: false });

    await user.click(await screen.findByRole("link", { name: "Нет аккаунта? Зарегистрироваться" }));

    expect(await findHeading("Регистрация")).toBeTruthy();
    expect(router.state.location.pathname).toBe("/register");
  });

  it("opens the default project section", async () => {
    const { router } = renderRoute("/projects/42");

    expect(await findHeading("Преподаватели")).toBeTruthy();
    expect(router.state.location.pathname).toBe("/projects/42/teachers");
    expect(screen.getByRole("tab", { name: "Преподаватели", selected: true })).toBeTruthy();
  });

  it("switches project sections through tabs", async () => {
    const { user, router } = renderRoute("/projects/42/teachers");
    await findHeading("Преподаватели");

    await user.click(screen.getByRole("tab", { name: "Аудитории" }));

    expect(await findHeading("Аудитории")).toBeTruthy();
    expect(router.state.location.pathname).toBe("/projects/42/rooms");
    expect(screen.getByRole("tab", { name: "Аудитории", selected: true })).toBeTruthy();
  });

  it("goes from the projects list to a project", async () => {
    const { user, router } = renderRoute("/projects");

    await user.click(await screen.findByRole("link", { name: "Открыть демо-проект" }));

    expect(await findHeading("Преподаватели")).toBeTruthy();
    expect(router.state.location.pathname).toBe("/projects/demo/teachers");
  });

  it("goes from schedule viewer to schedule editor", async () => {
    const { user, router } = renderRoute("/projects/42/schedules/s-1");

    await user.click(await screen.findByRole("link", { name: "Редактировать" }));

    expect(await findHeading("Редактирование расписания")).toBeTruthy();
    expect(router.state.location.pathname).toBe("/projects/42/schedules/s-1/edit");
    expect(screen.getByRole("tab", { name: "Расписания", selected: true })).toBeTruthy();
  });

  it("shows not found page for unknown URL", async () => {
    renderRoute("/no-such-page");

    expect(await findHeading("Страница не найдена")).toBeTruthy();
    expect(screen.getByRole("link", { name: "К списку проектов" })).toBeTruthy();
  });

  it("logs out to the login page from the profile menu", async () => {
    const { user, router, fetchMock } = renderRoute("/projects");
    await findHeading("Мои проекты");

    await user.click(screen.getByRole("button", { name: "Профиль" }));
    await user.click(await screen.findByRole("menuitem", { name: "Выйти" }));

    expect(await findHeading("Вход")).toBeTruthy();
    expect(router.state.location.pathname).toBe("/login");
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/logout", expect.anything());
  });

  it("sends an anonymous user to the login page and remembers the address", async () => {
    const { router } = renderRoute("/projects/42/rooms", undefined, { authenticated: false });

    expect(await findHeading("Вход")).toBeTruthy();
    expect(router.state.location.pathname).toBe("/login");
    expect(router.state.location.state.from.pathname).toBe("/projects/42/rooms");
  });
});
