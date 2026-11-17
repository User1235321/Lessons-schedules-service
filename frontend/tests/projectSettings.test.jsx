import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DEFAULT_SETTINGS, findHeading, renderRoute, TEST_PROJECTS } from "./renderRoute.jsx";

const DAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

async function openSettings(backend) {
  const result = renderRoute("/projects/42/settings", undefined, backend);
  await findHeading("Настройки проекта");
  return result;
}

function week(name) {
  return screen.getByRole("group", { name });
}

function savedPayload(fetchMock) {
  const [, request] = fetchMock.mock.calls.find(
    ([url, options]) => url === "/api/projects/42" && options?.method === "PATCH"
  );
  return JSON.parse(request.body);
}

describe("ProjectSettingsPage", () => {
  it("shows default settings from the already loaded project (F_Project_5)", async () => {
    const { fetchMock } = await openSettings();

    for (const weekName of ["Нечётная неделя", "Чётная неделя"]) {
      const controls = within(week(weekName));
      for (const day of DAYS.slice(0, 6)) {
        expect(controls.getByRole("checkbox", { name: day }).checked).toBe(true);
      }
      expect(controls.getByRole("checkbox", { name: "Вс" }).checked).toBe(false);
    }

    expect(screen.getByRole("radio", { name: "Только в начале часа" }).checked).toBe(true);
    expect(screen.getByRole("radio", { name: "Единая для всех занятий" }).checked).toBe(true);
    expect(screen.getByRole("spinbutton", { name: "Длительность занятия, минут" }).value).toBe("100");
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/projects/42")).toHaveLength(1);
  });

  it("saves different weekdays and modes, then restores them on reopening (F_Project_4, F_Data_1–3)", async () => {
    const { user, router, fetchMock } = await openSettings();

    await user.click(within(week("Нечётная неделя")).getByRole("checkbox", { name: "Пн" }));
    await user.click(within(week("Чётная неделя")).getByRole("checkbox", { name: "Вс" }));
    await user.click(screen.getByRole("radio", { name: "С минимальным временным шагом" }));
    await user.type(screen.getByRole("spinbutton", { name: "Минимальный шаг, минут" }), "15");
    await user.click(
      screen.getByRole("radio", { name: "Индивидуальная для каждого элемента нагрузки" })
    );
    await user.click(screen.getByRole("button", { name: "Сохранить настройки" }));

    expect(await screen.findByText("Настройки сохранены")).toBeTruthy();
    expect(savedPayload(fetchMock)).toEqual({
      cycle: {
        odd_week_days: DEFAULT_SETTINGS.cycle.odd_week_days.slice(1),
        even_week_days: [...DEFAULT_SETTINGS.cycle.even_week_days, "SUNDAY"]
      },
      time_mode: { type: "STEP", step_minutes: 15 },
      duration_mode: { type: "INDIVIDUAL" }
    });

    await router.navigate("/projects");
    await findHeading("Мои проекты");
    await router.navigate("/projects/42/settings");
    await findHeading("Настройки проекта");

    expect(within(week("Нечётная неделя")).getByRole("checkbox", { name: "Пн" }).checked).toBe(false);
    expect(within(week("Чётная неделя")).getByRole("checkbox", { name: "Вс" }).checked).toBe(true);
    expect(screen.getByRole("radio", { name: "С минимальным временным шагом" }).checked).toBe(true);
    expect(screen.getByRole("spinbutton", { name: "Минимальный шаг, минут" }).value).toBe("15");
    expect(screen.getByRole("radio", {
      name: "Индивидуальная для каждого элемента нагрузки"
    }).checked).toBe(true);
  });

  it("does not block locally valid empty weeks (F_Valid_3)", async () => {
    const project = {
      ...TEST_PROJECTS[0],
      cycle: { odd_week_days: [], even_week_days: [] }
    };
    const { user, fetchMock } = await openSettings({ projects: [project] });

    await user.click(screen.getByRole("button", { name: "Сохранить настройки" }));

    expect(await screen.findByText("Настройки сохранены")).toBeTruthy();
    expect(savedPayload(fetchMock).cycle).toEqual({
      odd_week_days: [],
      even_week_days: []
    });
  });

  it("requires positive whole minutes and does not submit invalid values (F_Valid_1–2)", async () => {
    const { user, fetchMock } = await openSettings();

    await user.click(screen.getByRole("radio", { name: "С минимальным временным шагом" }));
    await user.type(screen.getByRole("spinbutton", { name: "Минимальный шаг, минут" }), "0");
    await user.clear(screen.getByRole("spinbutton", { name: "Длительность занятия, минут" }));
    await user.type(screen.getByRole("spinbutton", { name: "Длительность занятия, минут" }), "0");
    await user.click(screen.getByRole("button", { name: "Сохранить настройки" }));

    expect(screen.getAllByText("Укажите положительное целое число минут")).toHaveLength(2);
    expect(fetchMock.mock.calls.some(([, options]) => options?.method === "PATCH")).toBe(false);

    await user.clear(screen.getByRole("spinbutton", { name: "Минимальный шаг, минут" }));
    await user.type(screen.getByRole("spinbutton", { name: "Минимальный шаг, минут" }), "30");
    await user.clear(screen.getByRole("spinbutton", { name: "Длительность занятия, минут" }));
    await user.type(screen.getByRole("spinbutton", { name: "Длительность занятия, минут" }), "90");
    await user.click(screen.getByRole("button", { name: "Сохранить настройки" }));

    expect(await screen.findByText("Настройки сохранены")).toBeTruthy();
    expect(savedPayload(fetchMock).time_mode).toEqual({ type: "STEP", step_minutes: 30 });
    expect(savedPayload(fetchMock).duration_mode).toEqual({
      type: "UNIFORM",
      duration_minutes: 90
    });
  });

  it("omits inactive parameters when switching modes", async () => {
    const project = {
      ...TEST_PROJECTS[0],
      time_mode: { type: "STEP", step_minutes: 20 },
      duration_mode: { type: "UNIFORM", duration_minutes: 85 }
    };
    const { user, fetchMock } = await openSettings({ projects: [project] });

    await user.click(screen.getByRole("radio", { name: "Только в начале часа" }));
    await user.click(
      screen.getByRole("radio", { name: "Индивидуальная для каждого элемента нагрузки" })
    );
    await user.click(screen.getByRole("button", { name: "Сохранить настройки" }));

    expect(await screen.findByText("Настройки сохранены")).toBeTruthy();
    expect(savedPayload(fetchMock).time_mode).toEqual({ type: "HOUR_START" });
    expect(savedPayload(fetchMock).duration_mode).toEqual({ type: "INDIVIDUAL" });
    expect(screen.queryByRole("spinbutton")).toBeNull();
  });

  it("shows API validation errors without claiming success", async () => {
    const { user, fetchMock } = await openSettings();
    const respond = fetchMock.getMockImplementation();
    fetchMock.mockImplementation(async (url, options) => {
      if (url === "/api/projects/42" && options?.method === "PATCH") {
        return new Response(JSON.stringify({
          code: "INVALID_VALUE",
          message: "Укажите положительный шаг",
          details: { field: "time_mode.step_minutes" }
        }), { status: 422 });
      }
      return respond(url, options);
    });

    await user.click(screen.getByRole("radio", { name: "С минимальным временным шагом" }));
    await user.type(screen.getByRole("spinbutton", { name: "Минимальный шаг, минут" }), "30");
    await user.click(screen.getByRole("button", { name: "Сохранить настройки" }));

    expect(await screen.findByText("Укажите положительный шаг")).toBeTruthy();
    expect(screen.queryByText("Настройки сохранены")).toBeNull();

    fetchMock.mockImplementation(respond);
    await user.click(screen.getByRole("button", { name: "Сохранить настройки" }));
    await waitFor(() => expect(screen.getByText("Настройки сохранены")).toBeTruthy());
  });
});
