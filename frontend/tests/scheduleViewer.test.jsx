import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderRoute } from "./renderRoute.jsx";

const lecture = {
  id: "lesson-1", week: "ODD", weekday: "TUESDAY", start_time: "10:30", end_time: "12:00",
  subject_name: "Физика", participant_label: "Поток 1", lesson_type: "LECTURE", lesson_format: "ONSITE",
  teachers: [{ display_name: "Иванова И. И." }, { display_name: "Петров П. П." }], room_name: "Б-201"
};

const imported = { id: "saved", project_id: "42", source: "IMPORTED", job_id: null, result_index: null,
  entries: [
    lecture,
    { ...lecture, id: "lesson-2", weekday: "MONDAY", subject_name: "История", participant_label: "Группа А" },
    { ...lecture, id: "lesson-3", week: "EVEN", subject_name: "Алгебра", participant_label: "Подгруппа А-2",
      lesson_type: "PRACTICE", lesson_format: "REMOTE", room_name: null, teachers: [] }
  ]
};

describe("Просмотр расписания", () => {
  it("открывает сохранённый результат по ссылке, сортирует занятия и переключает неделю", async () => {
    const { user, fetchMock } = renderRoute("/projects/42/schedules/saved", undefined, { schedules: [imported] });
    const table = within(await screen.findByRole("table"));
    expect(table.getAllByRole("row")[1].textContent).toContain("История");
    const row = table.getByText("Физика").closest("tr");
    expect(within(row).getAllByRole("cell").map((cell) => cell.textContent)).toEqual([
      "Вторник", "10:30–12:00", "Физика", "Лекция", "Очно", "Поток 1", "Иванова И. И., Петров П. П.", "Б-201"
    ]);
    expect(table.queryByText("Алгебра")).toBeNull();

    await user.click(screen.getByRole("button", { name: "Чётная неделя" }));
    expect(table.getByText("Подгруппа А-2")).toBeTruthy();
    expect(table.getByText("Дистанционно")).toBeTruthy();
    expect(table.getAllByText("—")).toHaveLength(2);
    expect(table.queryByText("Физика")).toBeNull();
    expect(fetchMock.mock.calls.filter(([url]) => url === "/api/schedules/saved")).toHaveLength(1);
    expect(fetchMock.mock.calls.some(([url]) => url.includes("/generation-jobs/"))).toBe(false);
  });

  it("объясняет, когда на выбранной неделе занятий нет", async () => {
    renderRoute("/projects/42/schedules/saved", undefined, { schedules: [{ ...imported, entries: [] }] });
    expect(await screen.findByText("На этой неделе занятий нет.")).toBeTruthy();
  });

  it("не показывает расписание другого проекта", async () => {
    renderRoute("/projects/43/schedules/saved", undefined, { schedules: [imported] });
    expect(await screen.findByText("Расписание не найдено в этом проекте.")).toBeTruthy();
    expect(screen.queryByRole("table")).toBeNull();
  });
});
