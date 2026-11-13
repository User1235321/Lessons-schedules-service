import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { findHeading, renderRoute, TEST_PROJECTS } from "./renderRoute.jsx";

const SETTINGS = {
  cycle: {
    odd_week_days: ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"],
    even_week_days: ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"]
  },
  time_mode: { type: "HOUR_START", step_minutes: null },
  duration_mode: { type: "UNIFORM", duration_minutes: 100 }
};

function openSettings(settings = SETTINGS) {
  const projects = TEST_PROJECTS.map((project) => ({ ...project, ...settings }));
  return renderRoute("/projects/42/settings", undefined, { projects });
}

const isProjectPatch = ([url, init]) => url === "/api/projects/42" && init?.method === "PATCH";
const checkbox = (name) => screen.getByRole("checkbox", { name });

describe("Project settings", () => {
  it("shows the saved settings", async () => {
    openSettings();
    await findHeading("Настройки проекта");

    expect(checkbox("Суббота, нечётная неделя").checked).toBe(true);
    expect(checkbox("Суббота, чётная неделя").checked).toBe(false);
    expect(screen.getByRole("radio", { name: "В начале часа" }).checked).toBe(true);
    expect(screen.getByLabelText("Длительность, минут").value).toBe("100");
  });

  it("saves days, a time step and individual durations (F_Data_1–F_Data_3)", async () => {
    const { user, fetchMock } = openSettings();
    await findHeading("Настройки проекта");

    await user.click(checkbox("Суббота, нечётная неделя"));
    await user.click(checkbox("Суббота, чётная неделя"));
    await user.click(screen.getByRole("radio", { name: "С заданным шагом" }));
    await user.type(screen.getByLabelText("Шаг, минут"), "30");
    await user.click(screen.getByRole("radio", { name: "Своя у каждого элемента нагрузки" }));
    await user.click(screen.getByRole("button", { name: "Сохранить" }));

    expect(await screen.findByText("Настройки сохранены")).toBeTruthy();
    const [, init] = fetchMock.mock.calls.find(isProjectPatch);
    expect(JSON.parse(init.body)).toEqual({
      cycle: {
        odd_week_days: ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"],
        even_week_days: ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"]
      },
      time_mode: { type: "STEP", step_minutes: 30 },
      duration_mode: { type: "INDIVIDUAL" }
    });
  });

  it("requires a positive step and duration", async () => {
    const { user, fetchMock } = openSettings();
    await findHeading("Настройки проекта");

    await user.click(screen.getByRole("radio", { name: "С заданным шагом" }));
    const duration = screen.getByLabelText("Длительность, минут");
    await user.clear(duration);
    await user.type(duration, "0");
    await user.click(screen.getByRole("button", { name: "Сохранить" }));

    expect(screen.getByText("Нужен положительный шаг в минутах")).toBeTruthy();
    expect(screen.getByText("Нужна положительная длительность в минутах")).toBeTruthy();
    expect(fetchMock.mock.calls.some(isProjectPatch)).toBe(false);
  });

  it("warns when a week has no study days", async () => {
    const { user } = openSettings({ ...SETTINGS, cycle: { ...SETTINGS.cycle, even_week_days: ["MONDAY"] } });
    await findHeading("Настройки проекта");

    await user.click(checkbox("Понедельник, чётная неделя"));

    expect(screen.getByText(/Учебных дней нет/)).toBeTruthy();
  });

  it("keeps the saved settings after reopening the section", async () => {
    const { user, router } = openSettings();
    await findHeading("Настройки проекта");

    await user.click(screen.getByRole("radio", { name: "Своя у каждого элемента нагрузки" }));
    await user.click(screen.getByRole("button", { name: "Сохранить" }));
    await screen.findByText("Настройки сохранены");

    await router.navigate("/projects/42/rooms");
    await findHeading("Аудитории");
    await router.navigate("/projects/42/settings");
    await findHeading("Настройки проекта");

    expect(screen.getByRole("radio", { name: "Своя у каждого элемента нагрузки" }).checked).toBe(true);
  });
});
