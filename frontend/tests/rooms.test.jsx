import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderRoute } from "./renderRoute.jsx";

const SUBJECTS = [
  { id: "s1", name: "Программирование" },
  { id: "s2", name: "Химия" }
];
const LECTURE_ROOM = {
  id: "r1",
  name: "212",
  capacity: 60,
  type: "LECTURE",
  availability: [{ week: "ANY", day: "MONDAY", start: "09:00", end: "18:00" }],
  capabilities: []
};
const LAB = {
  id: "r2",
  name: "Лаборатория 3",
  capacity: 15,
  type: "LABORATORY",
  availability: [{ week: "ODD", day: "TUESDAY", start: "10:00", end: "14:00" }],
  capabilities: [{ subject_id: "s2", lesson_type: "LAB" }]
};

function openRooms(resources = { subjects: SUBJECTS, rooms: [LECTURE_ROOM, LAB] }) {
  return renderRoute("/projects/42/rooms", undefined, { resources });
}

const table = () => screen.findByRole("table", { name: "Аудитории" });
const isRoomWrite = ([url, init]) =>
  /^\/api\/projects\/42\/rooms/.test(url) && ["POST", "PATCH"].includes(init?.method);

async function openAddDialog(user) {
  await user.click(await screen.findByRole("button", { name: "Добавить аудиторию" }));
  return screen.findByRole("dialog", { name: "Новая аудитория" });
}

describe("Rooms section", () => {
  it("lists rooms with type, allowed lessons and availability", async () => {
    openRooms();

    const list = await table();
    expect(within(list).getByText("212")).toBeTruthy();
    expect(within(list).getByText("Лекционная")).toBeTruthy();
    expect(within(list).getByText("Химия (лабораторная)")).toBeTruthy();
    expect(within(list).getByText("Вт, нечётная 10:00–14:00")).toBeTruthy();
  });

  it("shows an empty state", async () => {
    openRooms({ subjects: SUBJECTS });

    expect(await screen.findByText(/Аудиторий пока нет/)).toBeTruthy();
  });

  it("requires a name, a positive capacity and availability (F_Data_7)", async () => {
    const { user, fetchMock } = openRooms({ subjects: SUBJECTS });

    const dialog = await openAddDialog(user);
    await user.type(within(dialog).getByLabelText("Вместимость"), "0");
    await user.click(within(dialog).getByRole("button", { name: "Добавить" }));

    expect(within(dialog).getByText("Укажите номер или название аудитории")).toBeTruthy();
    expect(within(dialog).getByText("Нужна положительная вместимость")).toBeTruthy();
    expect(within(dialog).getByText("Добавьте хотя бы один промежуток")).toBeTruthy();
    expect(fetchMock.mock.calls.some(isRoomWrite)).toBe(false);
  });

  it("offers allowed lessons only for specialized rooms and laboratories (F_Data_9)", async () => {
    const { user } = openRooms({ subjects: SUBJECTS });

    const dialog = await openAddDialog(user);
    expect(within(dialog).queryByText("Допустимые занятия")).toBeNull();

    await user.selectOptions(within(dialog).getByLabelText("Тип аудитории"), "PRACTICE_SPECIALIZED");
    expect(within(dialog).getByText("Допустимые занятия")).toBeTruthy();
  });

  it("adds a laboratory with allowed lessons", async () => {
    const { user, fetchMock } = openRooms({ subjects: SUBJECTS });
    await screen.findByText(/Аудиторий пока нет/);

    const dialog = await openAddDialog(user);
    await user.type(within(dialog).getByLabelText("Номер или название"), " 105 ");
    await user.type(within(dialog).getByLabelText("Вместимость"), "20");
    await user.selectOptions(within(dialog).getByLabelText("Тип аудитории"), "LABORATORY");
    await user.click(within(dialog).getByRole("button", { name: "Добавить пару" }));
    await user.selectOptions(within(dialog).getByLabelText("Тип занятия: Допустимые занятия, пара 1"), "LAB");
    await user.click(within(dialog).getByRole("button", { name: "Добавить промежуток" }));
    await user.click(within(dialog).getByRole("button", { name: "Добавить" }));

    const list = await table();
    expect(await within(list).findByText("105")).toBeTruthy();
    const [, init] = fetchMock.mock.calls.find(isRoomWrite);
    expect(JSON.parse(init.body)).toEqual({
      name: "105",
      capacity: 20,
      type: "LABORATORY",
      availability: [{ week: "ANY", day: "MONDAY", start: "09:00", end: "18:00" }],
      capabilities: [{ subject_id: "s1", lesson_type: "LAB" }]
    });
  });

  it("drops allowed lessons when the type no longer supports them", async () => {
    const { user, fetchMock } = openRooms();
    const list = await table();

    await user.click(within(list).getByRole("button", { name: "Изменить: Лаборатория 3" }));
    const dialog = await screen.findByRole("dialog", { name: "Изменить аудиторию" });
    await user.selectOptions(within(dialog).getByLabelText("Тип аудитории"), "PRACTICE_UNIVERSAL");
    await user.click(within(dialog).getByRole("button", { name: "Сохранить" }));

    expect(await within(list).findByText("Практическая универсальная")).toBeTruthy();
    const [url, init] = fetchMock.mock.calls.find(isRoomWrite);
    expect(url).toBe("/api/projects/42/rooms/r2");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body)).toMatchObject({ type: "PRACTICE_UNIVERSAL", capabilities: [] });
  });

  it("deletes a room after confirmation", async () => {
    const { user } = openRooms();
    const list = await table();

    await user.click(within(list).getByRole("button", { name: "Удалить: 212" }));
    const dialog = await screen.findByRole("dialog", { name: "Удалить?" });
    await user.click(within(dialog).getByRole("button", { name: "Удалить" }));

    await within(list).findByText("Лаборатория 3");
    expect(within(list).queryByText("212")).toBeNull();
  });
});
