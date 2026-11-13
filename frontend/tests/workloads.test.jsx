import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderRoute, TEST_PROJECTS } from "./renderRoute.jsx";

const SUBJECTS = [
  { id: "s1", name: "Математика" },
  { id: "s2", name: "Химия" }
];
const GROUPS = [
  {
    id: "g1",
    name: "301",
    student_count: 25,
    subgroups: [{ id: "sg1", name: "1", student_count: 12 }]
  },
  { id: "g2", name: "302", student_count: 20, subgroups: [] }
];
const STREAMS = [{ id: "st1", name: "301 + 302", group_ids: ["g1", "g2"] }];
const LECTURE = {
  id: "w1",
  target: { type: "STREAM", id: "st1" },
  subject_id: "s1",
  lesson_type: "LECTURE",
  format: "ONSITE",
  occurrences_per_cycle: 2,
  duration_minutes: null,
  required_teacher_count: 1
};

const UNIFORM = { type: "UNIFORM", duration_minutes: 100 };
const INDIVIDUAL = { type: "INDIVIDUAL", duration_minutes: null };

function openWorkloads({ workloads = [LECTURE], durationMode = UNIFORM } = {}) {
  const projects = TEST_PROJECTS.map((project) => ({ ...project, duration_mode: durationMode }));
  return renderRoute("/projects/42/workloads", undefined, {
    projects,
    resources: { subjects: SUBJECTS, groups: GROUPS, streams: STREAMS, workloads }
  });
}

const table = () => screen.findByRole("table", { name: "Учебная нагрузка" });
const isWorkloadWrite = ([url, init]) =>
  /^\/api\/projects\/42\/workloads/.test(url) && ["POST", "PATCH"].includes(init?.method);

async function openAddDialog(user) {
  await user.click(await screen.findByRole("button", { name: "Добавить нагрузку" }));
  return screen.findByRole("dialog", { name: "Новая нагрузка" });
}

describe("Workloads section", () => {
  it("lists workloads with their target and the project duration", async () => {
    openWorkloads();

    const list = await table();
    expect(within(list).getByText("Математика")).toBeTruthy();
    expect(within(list).getByText("Лекция, очно")).toBeTruthy();
    expect(within(list).getByText("Поток 301 + 302")).toBeTruthy();
    expect(within(list).getByText("100 мин")).toBeTruthy();
  });

  it("shows an empty state", async () => {
    openWorkloads({ workloads: [] });

    expect(await screen.findByText(/Нагрузки пока нет/)).toBeTruthy();
  });

  it("adds a laboratory for a subgroup with two teachers (F_Data_16)", async () => {
    const { user, fetchMock } = openWorkloads({ workloads: [] });
    await screen.findByText(/Нагрузки пока нет/);

    const dialog = await openAddDialog(user);
    expect(within(dialog).queryByLabelText("Длительность, минут")).toBeNull();
    expect(within(dialog).queryByLabelText("Число преподавателей")).toBeNull();

    await user.selectOptions(within(dialog).getByLabelText("Для кого"), "SUBGROUP");
    expect(within(dialog).getByLabelText("Подгруппа").value).toBe("sg1");
    await user.selectOptions(within(dialog).getByLabelText("Дисциплина"), "s2");
    await user.selectOptions(within(dialog).getByLabelText("Тип занятия"), "LAB");
    await user.selectOptions(within(dialog).getByLabelText("Формат"), "REMOTE");
    const count = within(dialog).getByLabelText("Занятий за двухнедельный цикл");
    await user.clear(count);
    await user.type(count, "4");
    const teachers = within(dialog).getByLabelText("Число преподавателей");
    await user.clear(teachers);
    await user.type(teachers, "2");
    await user.click(within(dialog).getByRole("button", { name: "Добавить" }));

    const list = await table();
    expect(await within(list).findByText("301 / 1")).toBeTruthy();
    const [, init] = fetchMock.mock.calls.find(isWorkloadWrite);
    expect(JSON.parse(init.body)).toEqual({
      target: { type: "SUBGROUP", id: "sg1" },
      subject_id: "s2",
      lesson_type: "LAB",
      format: "REMOTE",
      occurrences_per_cycle: 4,
      duration_minutes: null,
      required_teacher_count: 2
    });
  });

  it("requires a positive number of lessons", async () => {
    const { user, fetchMock } = openWorkloads({ workloads: [] });

    const dialog = await openAddDialog(user);
    const count = within(dialog).getByLabelText("Занятий за двухнедельный цикл");
    await user.clear(count);
    await user.type(count, "0");
    await user.click(within(dialog).getByRole("button", { name: "Добавить" }));

    expect(within(dialog).getByText("Нужно положительное число занятий")).toBeTruthy();
    expect(fetchMock.mock.calls.some(isWorkloadWrite)).toBe(false);
  });

  it("asks for a duration in the individual duration mode (F_Data_3)", async () => {
    const { user, fetchMock } = openWorkloads({ durationMode: INDIVIDUAL });
    const list = await table();
    expect(within(list).getByText("не задана")).toBeTruthy();

    await user.click(within(list).getByRole("button", { name: "Изменить: Математика, Поток 301 + 302" }));
    const dialog = await screen.findByRole("dialog", { name: "Изменить нагрузку" });
    await user.click(within(dialog).getByRole("button", { name: "Сохранить" }));
    expect(within(dialog).getByText("Нужна положительная длительность в минутах")).toBeTruthy();

    await user.type(within(dialog).getByLabelText("Длительность, минут"), "90");
    await user.click(within(dialog).getByRole("button", { name: "Сохранить" }));

    expect(await within(list).findByText("90 мин")).toBeTruthy();
    const [url, init] = fetchMock.mock.calls.find(isWorkloadWrite);
    expect(url).toBe("/api/projects/42/workloads/w1");
    expect(JSON.parse(init.body)).toMatchObject({ duration_minutes: 90, required_teacher_count: 1 });
  });

  it("deletes a workload after confirmation", async () => {
    const { user } = openWorkloads();
    const list = await table();

    await user.click(within(list).getByRole("button", { name: "Удалить: Математика, Поток 301 + 302" }));
    const dialog = await screen.findByRole("dialog", { name: "Удалить?" });
    await user.click(within(dialog).getByRole("button", { name: "Удалить" }));

    expect(await screen.findByText(/Нагрузки пока нет/)).toBeTruthy();
  });
});
