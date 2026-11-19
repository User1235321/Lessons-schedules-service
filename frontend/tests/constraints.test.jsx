import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { findHeading, renderRoute } from "./renderRoute.jsx";

const workloadA = "00000000-0000-0000-0000-000000000001";
const workloadB = "00000000-0000-0000-0000-000000000002";
const academicData = {
  groups: [{ id: "g-1", name: "Группа 1", subgroups: [] }],
  subjects: [{ id: "s-1", name: "Математика" }],
  streams: [],
  workloads: [
    { id: workloadA, group_id: "g-1", subject_id: "s-1", lesson_type: "LECTURE" },
    { id: workloadB, group_id: "g-1", subject_id: "s-1", lesson_type: "PRACTICE" }
  ]
};

const cases = [
  ["MIN_START_TIME", { time: "08:00" }],
  ["MAX_END_TIME", { time: "08:00" }],
  ["ALLOWED_DAYS", { days: ["MONDAY"] }],
  ["TIME_RANGE", { windows: [{ week: "ANY", day: "MONDAY", start: "09:00", end: "18:00" }] }],
  ["EVERY_WEEK", {}],
  ["CONSECUTIVE", { workload_id: workloadB }],
  ["NOT_CONSECUTIVE", { workload_id: workloadB }],
  ["MIN_GAP", { workload_id: workloadB, minutes: 30 }],
  ["BEFORE", { workload_id: workloadB }],
  ["FIXED_DAY", { day: "MONDAY", week: "ANY" }]
];

const sentRequests = (fetchMock, method, suffix) =>
  fetchMock.mock.calls.filter(([url, init]) => url.endsWith(suffix) && (init?.method ?? "GET") === method);

describe("constraints", () => {
  it.each(cases)("creates an %s constraint with the backend contract", async (type, parameters) => {
    const { user, fetchMock } = renderRoute("/projects/42/constraints", undefined, {
      resources: academicData
    });

    await findHeading("Ограничения");
    await user.click(await screen.findByRole("button", { name: "Добавить ограничение" }));
    await user.selectOptions(screen.getByLabelText("Тип ограничения"), type);
    if (["CONSECUTIVE", "NOT_CONSECUTIVE", "MIN_GAP", "BEFORE"].includes(type)) {
      await user.selectOptions(screen.getByLabelText("Вторая учебная нагрузка"), workloadB);
    }
    await user.click(screen.getByRole("button", { name: "Добавить", exact: true }));

    await waitFor(() => {
      expect(sentRequests(fetchMock, "POST", "/constraints")).toHaveLength(1);
    });
    const body = JSON.parse(sentRequests(fetchMock, "POST", "/constraints")[0][1].body);
    expect(body.constraint_type).toBe(type);
    expect(body.scope).toEqual(
      ["EVERY_WEEK", "CONSECUTIVE", "NOT_CONSECUTIVE", "MIN_GAP", "BEFORE", "FIXED_DAY"].includes(type)
        ? { type: "WORKLOAD", id: workloadA }
        : { type: "PROJECT" }
    );
    expect(body.parameters).toEqual(parameters);
  });

  it("restores saved values, updates and deletes a constraint", async () => {
    const { user, fetchMock } = renderRoute("/projects/42/constraints", undefined, {
      resources: {
        ...academicData,
        constraints: [{
          id: "constraint-1",
          constraint_type: "FIXED_DAY",
          scope: { type: "WORKLOAD", id: workloadA },
          parameters: { day: "FRIDAY", week: "EVEN" }
        }]
      }
    });

    await findHeading("Ограничения");
    await user.click(await screen.findByRole("button", { name: "Изменить: Фиксированный день" }));
    expect(screen.getByLabelText("День").value).toBe("FRIDAY");
    expect(screen.getByLabelText("Неделя").value).toBe("EVEN");
    await user.selectOptions(screen.getByLabelText("День"), "MONDAY");
    await user.click(screen.getByRole("button", { name: "Сохранить", exact: true }));

    await waitFor(() => expect(sentRequests(fetchMock, "PATCH", "/constraints/constraint-1")).toHaveLength(1));
    const changed = JSON.parse(sentRequests(fetchMock, "PATCH", "/constraints/constraint-1")[0][1].body);
    expect(changed.parameters).toEqual({ day: "MONDAY", week: "EVEN" });

    await user.click(await screen.findByRole("button", { name: "Удалить: Фиксированный день" }));
    await user.click(screen.getByRole("button", { name: "Удалить", exact: true }));
    await waitFor(() => expect(sentRequests(fetchMock, "DELETE", "/constraints/constraint-1")).toHaveLength(1));
    expect(screen.getByText(/Ограничений пока нет/)).toBeTruthy();
  });

  it("validates missing workloads without sending a request", async () => {
    const { user, fetchMock } = renderRoute("/projects/42/constraints");

    await findHeading("Ограничения");
    await user.click(await screen.findByRole("button", { name: "Добавить ограничение" }));
    await user.selectOptions(screen.getByLabelText("Тип ограничения"), "EVERY_WEEK");
    await user.click(screen.getByRole("button", { name: "Добавить", exact: true }));

    expect(await screen.findByText("Выберите существующий ресурс")).toBeTruthy();
    expect(sentRequests(fetchMock, "POST", "/constraints")).toHaveLength(0);
  });

  it("validates and submits multiple time windows", async () => {
    const { user, fetchMock } = renderRoute("/projects/42/constraints");

    await findHeading("Ограничения");
    await user.click(await screen.findByRole("button", { name: "Добавить ограничение" }));
    await user.selectOptions(screen.getByLabelText("Тип ограничения"), "TIME_RANGE");
    await user.click(screen.getByRole("button", { name: "Добавить интервал" }));
    await user.click(screen.getByRole("button", { name: "Добавить", exact: true }));

    expect(await screen.findByText(/Добавьте неповторяющиеся интервалы/)).toBeTruthy();
    expect(sentRequests(fetchMock, "POST", "/constraints")).toHaveLength(0);

    await user.selectOptions(screen.getAllByLabelText("День")[1], "TUESDAY");
    await user.click(screen.getByRole("button", { name: "Добавить", exact: true }));
    await waitFor(() => expect(sentRequests(fetchMock, "POST", "/constraints")).toHaveLength(1));
    const body = JSON.parse(sentRequests(fetchMock, "POST", "/constraints")[0][1].body);
    expect(body.parameters.windows).toHaveLength(2);
    expect(body.parameters.windows[1].day).toBe("TUESDAY");
  });

  it("keeps constraints from different projects separate", async () => {
    const { router } = renderRoute("/projects/42/constraints", undefined, {
      resources: {
        ...academicData,
        constraintsByProject: {
          42: [{
            id: "first",
            constraint_type: "MIN_START_TIME",
            scope: { type: "PROJECT" },
            parameters: { time: "10:00" }
          }],
          43: [{
            id: "second",
            constraint_type: "MAX_END_TIME",
            scope: { type: "PROJECT" },
            parameters: { time: "17:00" }
          }]
        }
      }
    });

    expect(await screen.findByText("10:00")).toBeTruthy();
    await router.navigate("/projects/43/constraints");
    expect(await screen.findByText("17:00")).toBeTruthy();
    expect(screen.queryByText("10:00")).toBeNull();
  });
});

describe("optimization", () => {
  it("restores criteria, changes priorities and saves through the API", async () => {
    const { user, fetchMock } = renderRoute("/projects/42/optimization", undefined, {
      optimizationCriteria: {
        42: [
          { criterion_type: "STUDENT_GAPS", priority: 2, is_active: true },
          { criterion_type: "TEACHER_GAPS", priority: 1, is_active: true }
        ]
      }
    });

    await findHeading("Оптимизация");
    const students = await screen.findByRole("checkbox", { name: "Минимизировать окна студентов" });
    const teachers = screen.getByRole("checkbox", { name: "Минимизировать окна преподавателей" });
    expect(students.checked).toBe(true);
    expect(teachers.checked).toBe(true);
    await user.click(screen.getByRole("button", { name: "Повысить приоритет: Минимизировать окна студентов" }));
    await user.click(screen.getByRole("checkbox", { name: "Учитывать предпочтения преподавателей" }));
    await user.click(screen.getByRole("button", { name: "Сохранить критерии" }));

    await waitFor(() => expect(sentRequests(fetchMock, "PUT", "/optimization-criteria")).toHaveLength(1));
    const { criteria } = JSON.parse(sentRequests(fetchMock, "PUT", "/optimization-criteria")[0][1].body);
    expect(criteria).toHaveLength(5);
    expect(criteria.filter((criterion) => criterion.is_active).map((criterion) =>
      [criterion.criterion_type, criterion.priority]
    )).toEqual([
      ["STUDENT_GAPS", 1],
      ["TEACHER_GAPS", 2],
      ["TEACHER_PREFERENCES", 3]
    ]);
  });

  it("restores saved criteria when reopening another project", async () => {
    const { router } = renderRoute("/projects/42/optimization", undefined, {
      optimizationCriteria: {
        42: [{ criterion_type: "STUDENT_GAPS", priority: 1, is_active: true }],
        43: [{ criterion_type: "TEACHER_GAPS", priority: 1, is_active: true }]
      }
    });

    expect((await screen.findByRole("checkbox", { name: "Минимизировать окна студентов" })).checked).toBe(true);
    await router.navigate("/projects/43/optimization");
    await waitFor(() => {
      expect(screen.getByRole("checkbox", { name: "Минимизировать окна студентов" }).checked).toBe(false);
      expect(screen.getByRole("checkbox", { name: "Минимизировать окна преподавателей" }).checked).toBe(true);
    });
  });
});
