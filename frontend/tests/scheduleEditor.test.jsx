import { fireEvent, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderRoute } from "./renderRoute.jsx";

const first = {
  id: "one", week: "ODD", weekday: "MONDAY", start_time: "09:00", end_time: "10:30",
  subject_name: "Физика", participant_label: "Группа Б", lesson_format: "ONSITE",
  room_id: "a", room_name: "101", teachers: [{ teacher_id: null, display_name: "Смирнова" }]
};
const second = { ...first, id: "two", subject_name: "Алгебра" };
const rooms = [{ id: "a", name: "101" }, { id: "b", name: "202" }];
const teachers = [{ id: "staff", full_name: "Иванов" }];
const base = "/api/schedules/s-1";
const url = "/projects/42/schedules/s-1/edit";

function openEditor(entries = [first, second]) {
  const result = renderRoute(url, undefined, { resources: { rooms, teachers } });
  const fallback = result.fetchMock.getMockImplementation();
  const schedule = { id: "s-1", project_id: "42", entries: structuredClone(entries) };
  result.fetchMock.mockImplementation(async (path, init = {}) => {
    if (path === base && init.method === "GET") return Response.json(schedule);
    if (path.startsWith(base + "/entries/") && init.method === "PATCH") {
      const entry = schedule.entries.find((item) => path === base + "/entries/" + item.id);
      const changes = JSON.parse(init.body);
      Object.assign(entry, changes);
      if (changes.room_id) entry.room_name = rooms.find((room) => room.id === changes.room_id).name;
      return Response.json({ entry, conflicts: [] });
    }
    return fallback(path, init);
  });
  return { ...result, schedule };
}

async function edit(user, subject = "Физика") {
  const row = (await screen.findByText(subject)).closest("tr");
  await user.click(within(row).getByRole("button", { name: "Изменить" }));
  return within(await screen.findByRole("dialog"));
}

describe("Редактирование расписания", () => {
  it("сохраняет только изменённые поля выбранного занятия и показывает ответ сервера", async () => {
    const { user, fetchMock } = openEditor();
    const dialog = await edit(user);
    await user.selectOptions(dialog.getByLabelText("День"), "TUESDAY");
    fireEvent.change(dialog.getByLabelText("Начало"), { target: { value: "09:30" } });
    await user.selectOptions(dialog.getByLabelText("Аудитория"), "b");
    await user.click(dialog.getByLabelText("Преподаватели"));
    await user.click(await screen.findByRole("option", { name: "Иванов" }));
    await user.click(dialog.getByRole("button", { name: "Сохранить" }));
    expect(await screen.findByText("Изменения сохранены.")).toBeTruthy();
    const patch = fetchMock.mock.calls.find(([, init]) => init.method === "PATCH");
    expect(patch[0]).toBe(base + "/entries/one");
    expect(JSON.parse(patch[1].body)).toEqual({
      weekday: "TUESDAY", start_time: "09:30", room_id: "b",
      teachers: [...first.teachers, { teacher_id: "staff", display_name: "Иванов" }]
    });
    expect(screen.getByText("Очно · 202")).toBeTruthy();
    expect(screen.getByText("Смирнова, Иванов")).toBeTruthy();
  });

  it("проверяет интервал до отправки и очищает аудиторию при переходе на дистанционный формат", async () => {
    const { user, fetchMock } = openEditor();
    const dialog = await edit(user);
    fireEvent.change(dialog.getByLabelText("Окончание"), { target: { value: "08:00" } });
    await user.click(dialog.getByRole("button", { name: "Сохранить" }));
    expect(dialog.getByText("Окончание должно быть позже начала")).toBeTruthy();
    expect(fetchMock.mock.calls.some(([, init]) => init.method === "PATCH")).toBe(false);
    fireEvent.change(dialog.getByLabelText("Окончание"), { target: { value: "11:00" } });
    await user.selectOptions(dialog.getByLabelText("Формат"), "REMOTE");
    expect(dialog.queryByLabelText("Аудитория")).toBeNull();
    await user.click(dialog.getByRole("button", { name: "Сохранить" }));
    expect(await screen.findByText("Изменения сохранены.")).toBeTruthy();
    const patch = fetchMock.mock.calls.find(([, init]) => init.method === "PATCH");
    expect(JSON.parse(patch[1].body)).toEqual({
      end_time: "11:00", lesson_format: "REMOTE", room_id: null, room_name: null
    });
  });
});
