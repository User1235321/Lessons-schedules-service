import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderRoute } from "./renderRoute.jsx";

const SUBJECTS = [
  { id: "s1", name: "Математика" },
  { id: "s2", name: "Физика" }
];
const TEACHER = {
  id: "t1",
  full_name: "Иванов Иван Иванович",
  capabilities: [{ subject_id: "s1", lesson_type: "LECTURE" }],
  availability: [{ week: "ANY", day: "MONDAY", start: "09:00", end: "13:00" }],
  preferences: []
};

function openTeachers(resources = { subjects: SUBJECTS, teachers: [TEACHER] }, backend = {}) {
  return renderRoute("/projects/42/teachers", undefined, { resources, ...backend });
}

const table = () => screen.findByRole("table", { name: "Преподаватели" });
const isTeacherWrite = ([url, init]) =>
  /^\/api\/projects\/42\/teachers/.test(url) && ["POST", "PATCH"].includes(init?.method);

async function openAddDialog(user) {
  await user.click(await screen.findByRole("button", { name: "Добавить преподавателя" }));
  return screen.findByRole("dialog", { name: "Новый преподаватель" });
}

describe("Teachers section", () => {
  it("lists teachers with subjects and availability in readable form", async () => {
    openTeachers();

    const list = await table();
    expect(within(list).getByText("Иванов Иван Иванович")).toBeTruthy();
    expect(within(list).getByText("Математика (лекция)")).toBeTruthy();
    expect(within(list).getByText("Пн 09:00–13:00")).toBeTruthy();
  });

  it("shows an empty state", async () => {
    openTeachers({ subjects: SUBJECTS });

    expect(await screen.findByText(/Преподавателей пока нет/)).toBeTruthy();
  });

  it("requires a name, a subject pair and availability (F_Data_4)", async () => {
    const { user, fetchMock } = openTeachers({ subjects: SUBJECTS });

    const dialog = await openAddDialog(user);
    await user.click(within(dialog).getByRole("button", { name: "Добавить" }));

    expect(within(dialog).getByText("Укажите ФИО преподавателя")).toBeTruthy();
    expect(within(dialog).getByText(/хотя бы одну пару/)).toBeTruthy();
    expect(within(dialog).getByText("Добавьте хотя бы один промежуток")).toBeTruthy();
    expect(fetchMock.mock.calls.some(isTeacherWrite)).toBe(false);
  });

  it("asks to add subjects first when there are none", async () => {
    const { user } = openTeachers({});

    const dialog = await openAddDialog(user);

    expect(within(dialog).getByText(/Сначала добавьте дисциплины/)).toBeTruthy();
    expect(within(dialog).getByRole("link", { name: "«Дисциплины»" })).toBeTruthy();
    expect(within(dialog).getByRole("button", { name: "Добавить пару" }).disabled).toBe(true);
  });

  it("adds a teacher", async () => {
    const { user, fetchMock } = openTeachers({ subjects: SUBJECTS });
    await screen.findByText(/Преподавателей пока нет/);

    const dialog = await openAddDialog(user);
    await user.type(within(dialog).getByLabelText("ФИО"), "  Петров Пётр ");
    await user.click(within(dialog).getByRole("button", { name: "Добавить пару" }));
    await user.selectOptions(within(dialog).getByLabelText("Дисциплина: Что ведёт, пара 1"), "s2");
    await user.selectOptions(within(dialog).getByLabelText("Тип занятия: Что ведёт, пара 1"), "LAB");
    await user.click(within(dialog).getAllByRole("button", { name: "Добавить промежуток" })[0]);
    await user.click(within(dialog).getByRole("button", { name: "Добавить" }));

    const list = await table();
    expect(await within(list).findByText("Петров Пётр")).toBeTruthy();
    expect(within(list).getByText("Физика (лабораторная)")).toBeTruthy();
    const [, init] = fetchMock.mock.calls.find(isTeacherWrite);
    expect(JSON.parse(init.body)).toEqual({
      full_name: "Петров Пётр",
      capabilities: [{ subject_id: "s2", lesson_type: "LAB" }],
      availability: [{ week: "ANY", day: "MONDAY", start: "09:00", end: "18:00" }],
      preferences: []
    });
  });

  it("rejects an interval that ends before it starts", async () => {
    const { user, fetchMock } = openTeachers();
    const list = await table();

    await user.click(within(list).getByRole("button", { name: "Изменить: Иванов Иван Иванович" }));
    const dialog = await screen.findByRole("dialog", { name: "Изменить преподавателя" });
    const end = within(dialog).getByLabelText("Окончание: Доступность, промежуток 1");
    await user.clear(end);
    await user.type(end, "08:00");
    await user.click(within(dialog).getByRole("button", { name: "Сохранить" }));

    expect(within(dialog).getByText("Время окончания должно быть позже начала")).toBeTruthy();
    expect(fetchMock.mock.calls.some(isTeacherWrite)).toBe(false);
  });

  it("edits a teacher and sends the full sets", async () => {
    const { user, fetchMock } = openTeachers();
    const list = await table();

    await user.click(within(list).getByRole("button", { name: "Изменить: Иванов Иван Иванович" }));
    const dialog = await screen.findByRole("dialog", { name: "Изменить преподавателя" });
    const name = within(dialog).getByLabelText("ФИО");
    expect(name.value).toBe("Иванов Иван Иванович");
    await user.clear(name);
    await user.type(name, "Иванов И. И.");
    await user.click(within(dialog).getByRole("button", { name: "Сохранить" }));

    expect(await within(list).findByText("Иванов И. И.")).toBeTruthy();
    const [url, init] = fetchMock.mock.calls.find(isTeacherWrite);
    expect(url).toBe("/api/projects/42/teachers/t1");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body)).toMatchObject({
      full_name: "Иванов И. И.",
      capabilities: TEACHER.capabilities,
      availability: TEACHER.availability
    });
  });

  it("deletes a teacher after confirmation", async () => {
    const { user } = openTeachers();
    const list = await table();

    await user.click(within(list).getByRole("button", { name: "Удалить: Иванов Иван Иванович" }));
    const dialog = await screen.findByRole("dialog", { name: "Удалить?" });
    expect(within(dialog).getByText(/Иванов Иван Иванович/)).toBeTruthy();
    await user.click(within(dialog).getByRole("button", { name: "Удалить" }));

    // Преподаватель был единственным: вместо таблицы показывается пустое состояние
    expect(await screen.findByText(/Преподавателей пока нет/)).toBeTruthy();
    expect(screen.queryByText("Иванов Иван Иванович")).toBeNull();
  });
});
