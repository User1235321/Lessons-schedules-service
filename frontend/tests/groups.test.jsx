import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { validateStudentCount } from "../src/features/project-editor/validation.js";
import { renderRoute } from "./renderRoute.jsx";

const GROUPS = [
  {
    id: "g1",
    name: "ИВТ-21",
    student_count: 25,
    subgroups: [
      { id: "sg1", name: "ИВТ-21/1", student_count: 12 },
      { id: "sg2", name: "ИВТ-21/2", student_count: 10 }
    ]
  },
  { id: "g2", name: "ПИ-22", student_count: 30, subgroups: [] }
];

function openGroups(resources = { groups: GROUPS }, backend = {}) {
  return renderRoute("/projects/42/groups", undefined, { resources, ...backend });
}

const table = () => screen.findByRole("table", { name: "Группы и подгруппы" });
const isGroupWrite = ([url, init]) =>
  /^\/api\/projects\/42\/groups/.test(url) && ["POST", "PATCH"].includes(init?.method);

async function openAddDialog(user) {
  await user.click(await screen.findByRole("button", { name: "Добавить группу" }));
  return screen.findByRole("dialog", { name: "Новая группа" });
}

describe("validateStudentCount", () => {
  it("accepts only positive integers", () => {
    expect(validateStudentCount("25")).toBeNull();
    expect(validateStudentCount(" 7 ")).toBeNull();
    for (const bad of ["", "0", "-3", "2.5", "abc", String(2 ** 31)]) {
      expect(validateStudentCount(bad)).not.toBeNull();
    }
  });
});

describe("Groups section", () => {
  it("lists groups with their subgroups", async () => {
    openGroups();

    const list = await table();
    expect(within(list).getByText("ИВТ-21")).toBeTruthy();
    expect(within(list).getByText("25")).toBeTruthy();
    expect(within(list).getByText("ИВТ-21/1 (12), ИВТ-21/2 (10)")).toBeTruthy();
    expect(within(list).getByText("ПИ-22")).toBeTruthy();
  });

  it("shows an empty state", async () => {
    openGroups({});

    expect(await screen.findByText(/Групп пока нет/)).toBeTruthy();
  });

  it("requires a name and a positive number of students (F_Data_10)", async () => {
    const { user, fetchMock } = openGroups({});

    const dialog = await openAddDialog(user);
    await user.type(within(dialog).getByLabelText("Число студентов"), "0");
    await user.click(within(dialog).getByRole("button", { name: "Добавить" }));

    expect(within(dialog).getByText("Укажите название группы")).toBeTruthy();
    expect(within(dialog).getByText("Нужно положительное целое число студентов")).toBeTruthy();
    expect(fetchMock.mock.calls.some(isGroupWrite)).toBe(false);
  });

  it("adds a group", async () => {
    const { user, fetchMock } = openGroups({});
    await screen.findByText(/Групп пока нет/);

    const dialog = await openAddDialog(user);
    await user.type(within(dialog).getByLabelText("Название группы"), " ФИЗ-23 ");
    await user.type(within(dialog).getByLabelText("Число студентов"), "28");
    await user.click(within(dialog).getByRole("button", { name: "Добавить" }));

    expect(await within(await table()).findByText("ФИЗ-23")).toBeTruthy();
    const [, init] = fetchMock.mock.calls.find(isGroupWrite);
    expect(JSON.parse(init.body)).toEqual({ name: "ФИЗ-23", student_count: 28 });
  });

  it("shows the backend error for a taken name next to the field", async () => {
    const { user } = openGroups();
    await table();

    const dialog = await openAddDialog(user);
    await user.type(within(dialog).getByLabelText("Название группы"), "пи-22");
    await user.type(within(dialog).getByLabelText("Число студентов"), "20");
    await user.click(within(dialog).getByRole("button", { name: "Добавить" }));

    expect(await within(dialog).findByText("Такое название уже есть")).toBeTruthy();
  });

  it("does not let the group get smaller than its subgroups (F_Data_12)", async () => {
    const { user, fetchMock } = openGroups();
    const list = await table();

    await user.click(within(list).getByRole("button", { name: "Изменить: ИВТ-21" }));
    const dialog = await screen.findByRole("dialog", { name: "Изменить группу" });
    const count = within(dialog).getByLabelText("Число студентов");
    await user.clear(count);
    await user.type(count, "20");
    await user.click(within(dialog).getByRole("button", { name: "Сохранить" }));

    expect(within(dialog).getByText("Меньше суммы студентов в подгруппах (22)")).toBeTruthy();
    expect(fetchMock.mock.calls.some(isGroupWrite)).toBe(false);
  });

  it("edits a group", async () => {
    const { user, fetchMock } = openGroups();
    const list = await table();

    await user.click(within(list).getByRole("button", { name: "Изменить: ПИ-22" }));
    const dialog = await screen.findByRole("dialog", { name: "Изменить группу" });
    const count = within(dialog).getByLabelText("Число студентов");
    expect(count.value).toBe("30");
    await user.clear(count);
    await user.type(count, "32");
    await user.click(within(dialog).getByRole("button", { name: "Сохранить" }));

    expect(await within(list).findByText("32")).toBeTruthy();
    const [url, init] = fetchMock.mock.calls.find(isGroupWrite);
    expect(url).toBe("/api/projects/42/groups/g2");
    expect(JSON.parse(init.body)).toEqual({ name: "ПИ-22", student_count: 32 });
  });

  it("deletes a group after confirmation", async () => {
    const { user } = openGroups();
    const list = await table();

    await user.click(within(list).getByRole("button", { name: "Удалить: ПИ-22" }));
    const dialog = await screen.findByRole("dialog", { name: "Удалить?" });
    await user.click(within(dialog).getByRole("button", { name: "Удалить" }));

    expect(await within(list).findByText("ИВТ-21")).toBeTruthy();
    await screen.findByRole("table", { name: "Группы и подгруппы" });
    expect(screen.queryByText("ПИ-22")).toBeNull();
  });

  it("keeps a group that is in use and shows why", async () => {
    const { user } = openGroups(undefined, { blockedDeletes: ["g2"] });
    const list = await table();

    await user.click(within(list).getByRole("button", { name: "Удалить: ПИ-22" }));
    const dialog = await screen.findByRole("dialog", { name: "Удалить?" });
    await user.click(within(dialog).getByRole("button", { name: "Удалить" }));

    expect(await within(dialog).findByText("Используется в нагрузке")).toBeTruthy();
    expect(within(list).getByText("ПИ-22")).toBeTruthy();
  });
});
