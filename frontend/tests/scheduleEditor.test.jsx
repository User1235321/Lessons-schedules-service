import { act, fireEvent, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderRoute } from "./renderRoute.jsx";

const first = {
  id: "one", week: "ODD", weekday: "MONDAY", start_time: "09:00", end_time: "10:30",
  subject_name: "Физика", participant_label: "Группа Б", lesson_format: "ONSITE",
  room_id: "a", room_name: "101", teachers: [{ teacher_id: null, display_name: "Смирнова" }]
};
const second = { ...first, id: "two", weekday: "TUESDAY", subject_name: "Алгебра" };
const rooms = [{ id: "a", name: "101" }, { id: "b", name: "202" }];
const teachers = [{ id: "staff", full_name: "Иванов" }];
const base = "/api/schedules/s-1";
const url = "/projects/42/schedules/s-1/edit";

function openEditor(entries = [first, second]) {
  const result = renderRoute(url, undefined, { resources: { rooms, teachers } });
  const fallback = result.fetchMock.getMockImplementation();
  const schedule = { id: "s-1", project_id: "42", entries: structuredClone(entries) };
  function conflicts() {
    const [a, b] = schedule.entries;
    return a && b && a.weekday === b.weekday && a.room_id && a.room_id === b.room_id
      ? [{ code: "ROOM_OVERLAP", message: "Аудитория занята", entry_ids: [a.id, b.id], details: {} }]
      : [];
  }
  result.fetchMock.mockImplementation(async (path, init = {}) => {
    if (path === base && init.method === "GET") return Response.json(schedule);
    if (path === base + "/validate" && init.method === "POST") {
      const found = conflicts();
      return Response.json({ status: found.length ? "invalid" : "valid", conflicts: found });
    }
    if (path.startsWith(base + "/entries/") && init.method === "PATCH") {
      const entry = schedule.entries.find((item) => path === base + "/entries/" + item.id);
      const changes = JSON.parse(init.body);
      Object.assign(entry, changes);
      if (changes.room_id) entry.room_name = rooms.find((room) => room.id === changes.room_id).name;
      return Response.json({ entry, conflicts: conflicts() });
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

describe("Повторная проверка расписания", () => {
  it("сохраняет конфликт, отмечает оба занятия и восстанавливает их после повторного открытия", async () => {
    const { user, router, fetchMock } = openEditor();
    await screen.findByText("Конфликтов нет.");
    const dialog = await edit(user);
    await user.selectOptions(dialog.getByLabelText("День"), "TUESDAY");
    await user.click(dialog.getByRole("button", { name: "Сохранить" }));
    expect(await screen.findByText("Изменения сохранены.")).toBeTruthy();

    for (const subject of ["Физика", "Алгебра"]) {
      const row = within(screen.getByText(subject).closest("tr"));
      expect(row.getByText("Конфликт")).toBeTruthy();
      expect(row.getByText("Аудитория занята")).toBeTruthy();
    }
    expect(fetchMock.mock.calls.filter(([path]) => path === base + "/validate")).toHaveLength(2);
    await user.click(screen.getByRole("link", { name: "Вернуться к просмотру" }));
    await act(() => router.navigate(url));
    expect(await screen.findByText("Обнаружено конфликтов: 1")).toBeTruthy();
    const reopened = await edit(user);
    expect(reopened.getByLabelText("День").value).toBe("TUESDAY");
    await user.selectOptions(reopened.getByLabelText("День"), "WEDNESDAY");
    await user.click(reopened.getByRole("button", { name: "Сохранить" }));
    expect(await screen.findByText("Конфликтов нет.")).toBeTruthy();
    expect(screen.queryByText("Аудитория занята")).toBeNull();
  });

  it("оставляет изменения сохранёнными при сбое повторной проверки и позволяет повторить её отдельно", async () => {
    const { user, fetchMock } = openEditor();
    await screen.findByText("Конфликтов нет.");
    const fallback = fetchMock.getMockImplementation();
    let failed = false;
    fetchMock.mockImplementation((path, init) => {
      if (!failed && path === base + "/validate") {
        failed = true;
        return Promise.resolve(new Response(null, { status: 503 }));
      }
      return fallback(path, init);
    });
    const dialog = await edit(user);
    await user.selectOptions(dialog.getByLabelText("День"), "TUESDAY");
    await user.click(dialog.getByRole("button", { name: "Сохранить" }));
    expect(await screen.findByText(/Не удалось проверить расписание/)).toBeTruthy();
    expect(screen.getByText("Изменения сохранены.")).toBeTruthy();
    expect(screen.getAllByText("Аудитория занята")).toHaveLength(2);
    await user.click(screen.getByRole("button", { name: "Проверить расписание" }));
    expect(screen.queryByText(/Не удалось проверить расписание/)).toBeNull();
    expect(fetchMock.mock.calls.filter(([, init]) => init.method === "PATCH")).toHaveLength(1);
  });
});
