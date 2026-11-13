import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderRoute } from "./renderRoute.jsx";

const SUBGROUPS = [
  { id: "sg1", group_id: "g1", name: "ИВТ-21/1", student_count: 12 },
  { id: "sg2", group_id: "g1", name: "ИВТ-21/2", student_count: 10 }
];
const GROUPS = [
  {
    id: "g1",
    name: "ИВТ-21",
    student_count: 25,
    subgroups: SUBGROUPS.map(({ id, name, student_count: count }) => ({ id, name, student_count: count }))
  }
];

const isSubgroupWrite = ([url, init]) =>
  /^\/api\/projects\/42\/subgroups/.test(url) && ["POST", "PATCH", "DELETE"].includes(init?.method);

async function openSubgroups() {
  const rendered = renderRoute("/projects/42/groups", undefined, {
    resources: { groups: GROUPS, subgroups: SUBGROUPS }
  });
  const groups = await screen.findByRole("table", { name: "Группы и подгруппы" });
  await rendered.user.click(within(groups).getByRole("button", { name: "Подгруппы: ИВТ-21" }));
  const dialog = await screen.findByRole("dialog", { name: "Подгруппы: ИВТ-21" });
  return { ...rendered, groups, dialog };
}

async function fillSubgroup(user, dialog, name, count) {
  const nameField = within(dialog).getByLabelText("Название подгруппы");
  const countField = within(dialog).getByLabelText("Число студентов в подгруппе");
  await user.clear(nameField);
  await user.type(nameField, name);
  await user.clear(countField);
  await user.type(countField, count);
}

describe("Subgroups dialog", () => {
  it("shows the subgroups and how many students are distributed", async () => {
    const { dialog } = await openSubgroups();

    const list = within(dialog).getByRole("list", { name: "Подгруппы" });
    expect(within(list).getByText("ИВТ-21/1")).toBeTruthy();
    expect(within(list).getByText("12 студентов")).toBeTruthy();
    expect(within(dialog).getByText("Распределено 22 из 25 студентов")).toBeTruthy();
  });

  it("adds a subgroup and updates the group row (F_Data_11)", async () => {
    const { user, fetchMock, groups, dialog } = await openSubgroups();

    await fillSubgroup(user, dialog, "  ИВТ-21/3 ", "3");
    await user.click(within(dialog).getByRole("button", { name: "Добавить подгруппу" }));

    const list = within(dialog).getByRole("list", { name: "Подгруппы" });
    expect(await within(list).findByText("ИВТ-21/3")).toBeTruthy();
    expect(within(dialog).getByText("Распределено 25 из 25 студентов")).toBeTruthy();
    expect(within(groups).getByText("ИВТ-21/1 (12), ИВТ-21/2 (10), ИВТ-21/3 (3)")).toBeTruthy();
    const [url, init] = fetchMock.mock.calls.find(isSubgroupWrite);
    expect(url).toBe("/api/projects/42/subgroups");
    expect(JSON.parse(init.body)).toEqual({ group_id: "g1", name: "ИВТ-21/3", student_count: 3 });
  });

  it("does not let subgroups exceed the group (F_Data_12)", async () => {
    const { user, fetchMock, dialog } = await openSubgroups();

    await fillSubgroup(user, dialog, "ИВТ-21/3", "4");
    await user.click(within(dialog).getByRole("button", { name: "Добавить подгруппу" }));

    expect(within(dialog).getByText(/Сумма студентов в подгруппах не должна превышать/)).toBeTruthy();
    expect(within(dialog).getByText(/свободно: 3/)).toBeTruthy();
    expect(fetchMock.mock.calls.some(isSubgroupWrite)).toBe(false);
  });

  it("requires a name and a positive number of students", async () => {
    const { user, fetchMock, dialog } = await openSubgroups();

    await fillSubgroup(user, dialog, "   ", "0");
    await user.click(within(dialog).getByRole("button", { name: "Добавить подгруппу" }));

    expect(within(dialog).getByText("Укажите название подгруппы")).toBeTruthy();
    expect(within(dialog).getByText("Нужно положительное целое число студентов")).toBeTruthy();
    expect(fetchMock.mock.calls.some(isSubgroupWrite)).toBe(false);
  });

  it("shows the backend error for a taken name next to the field", async () => {
    const { user, dialog } = await openSubgroups();

    await fillSubgroup(user, dialog, "ивт-21/1", "1");
    await user.click(within(dialog).getByRole("button", { name: "Добавить подгруппу" }));

    expect(await within(dialog).findByText("Такое название уже есть")).toBeTruthy();
  });

  it("edits a subgroup within the free space (F_Data_13)", async () => {
    const { user, fetchMock, groups, dialog } = await openSubgroups();

    await user.click(within(dialog).getByRole("button", { name: "Изменить подгруппу: ИВТ-21/1" }));
    expect(within(dialog).getByLabelText("Название подгруппы").value).toBe("ИВТ-21/1");
    await fillSubgroup(user, dialog, "ИВТ-21/А", "15");
    await user.click(within(dialog).getByRole("button", { name: "Сохранить подгруппу" }));

    const list = within(dialog).getByRole("list", { name: "Подгруппы" });
    expect(await within(list).findByText("ИВТ-21/А")).toBeTruthy();
    expect(within(groups).getByText("ИВТ-21/А (15), ИВТ-21/2 (10)")).toBeTruthy();
    const [url, init] = fetchMock.mock.calls.find(isSubgroupWrite);
    expect(url).toBe("/api/projects/42/subgroups/sg1");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body)).toEqual({ name: "ИВТ-21/А", student_count: 15 });
  });

  it("does not count the edited subgroup twice", async () => {
    const { user, fetchMock, dialog } = await openSubgroups();

    await user.click(within(dialog).getByRole("button", { name: "Изменить подгруппу: ИВТ-21/1" }));
    await fillSubgroup(user, dialog, "ИВТ-21/1", "16"); // 16 + 10 = 26 > 25
    await user.click(within(dialog).getByRole("button", { name: "Сохранить подгруппу" }));

    expect(within(dialog).getByText(/свободно: 15/)).toBeTruthy();
    expect(fetchMock.mock.calls.some(isSubgroupWrite)).toBe(false);
  });

  it("deletes a subgroup after confirmation (F_Data_13)", async () => {
    const { user, groups, dialog } = await openSubgroups();

    await user.click(within(dialog).getByRole("button", { name: "Удалить подгруппу: ИВТ-21/2" }));
    const confirm = await screen.findByRole("dialog", { name: "Удалить подгруппу?" });
    await user.click(within(confirm).getByRole("button", { name: "Удалить" }));

    await within(dialog).findByText("Распределено 12 из 25 студентов");
    // Пока подтверждение закрывается, диалог под ним скрыт от доступности
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "Удалить подгруппу?" })).toBeNull()
    );
    const list = within(dialog).getByRole("list", { name: "Подгруппы" });
    expect(within(list).queryByText("ИВТ-21/2")).toBeNull();
    expect(within(groups).getByText("ИВТ-21/1 (12)")).toBeTruthy();
  });
});
