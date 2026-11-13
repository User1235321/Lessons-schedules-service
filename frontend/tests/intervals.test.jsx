import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import IntervalsField from "../src/features/project-editor/components/IntervalsField.jsx";
import {
  formatInterval,
  validateCapabilities,
  validateIntervals
} from "../src/features/project-editor/intervals.js";

describe("intervals helpers", () => {
  it("formats an interval for a table", () => {
    expect(formatInterval({ week: "ANY", day: "MONDAY", start: "09:00", end: "11:00" })).toBe(
      "Пн 09:00–11:00"
    );
    expect(formatInterval({ week: "ODD", day: "FRIDAY", start: "10:00", end: "12:00" })).toBe(
      "Пт, нечётная 10:00–12:00"
    );
  });

  it("requires at least one interval when asked", () => {
    expect(validateIntervals([], { required: true })).toBe("Добавьте хотя бы один промежуток");
    expect(validateIntervals([], { required: false })).toBeNull();
  });

  it("requires the end to be later than the start", () => {
    const interval = { week: "ANY", day: "MONDAY", start: "10:00", end: "10:00" };

    expect(validateIntervals([interval], { required: true })).toBe(
      "Время окончания должно быть позже начала"
    );
    expect(validateIntervals([{ ...interval, end: "11:00" }], { required: true })).toBeNull();
    expect(validateIntervals([{ ...interval, end: "" }], { required: true })).toBe(
      "Укажите время начала и окончания"
    );
  });
});

function Harness({ initial = [], onChange }) {
  const [value, setValue] = useState(initial);
  return (
    <IntervalsField
      label="Доступность"
      value={value}
      onChange={(next) => {
        setValue(next);
        onChange?.(next);
      }}
    />
  );
}

describe("IntervalsField", () => {
  it("adds, edits and removes intervals", async () => {
    const user = userEvent.setup();
    let latest = [];
    render(<Harness onChange={(next) => (latest = next)} />);

    await user.click(screen.getByRole("button", { name: "Добавить промежуток" }));
    expect(latest).toEqual([{ week: "ANY", day: "MONDAY", start: "09:00", end: "18:00" }]);

    await user.selectOptions(screen.getByLabelText("День: Доступность, промежуток 1"), "FRIDAY");
    await user.selectOptions(screen.getByLabelText("Неделя: Доступность, промежуток 1"), "ODD");
    expect(latest[0]).toMatchObject({ week: "ODD", day: "FRIDAY" });

    await user.click(screen.getByRole("button", { name: "Добавить промежуток" }));
    expect(latest).toHaveLength(2);

    await user.click(screen.getByRole("button", { name: "Удалить: Доступность, промежуток 1" }));
    expect(latest).toHaveLength(1);
    expect(latest[0]).toMatchObject({ week: "ANY", day: "MONDAY" });
  });
});

describe("validateCapabilities", () => {
  const pair = { subject_id: "s1", lesson_type: "LECTURE" };

  it("requires a pair when asked and forbids duplicates", () => {
    expect(validateCapabilities([], { required: true })).toMatch(/хотя бы одну пару/);
    expect(validateCapabilities([], { required: false })).toBeNull();
    expect(validateCapabilities([pair, pair], { required: true })).toBe("Пары не должны повторяться");
    expect(validateCapabilities([pair, { ...pair, lesson_type: "LAB" }], { required: true })).toBeNull();
    expect(validateCapabilities([{ ...pair, subject_id: "" }], { required: true })).toBe(
      "Выберите дисциплину"
    );
  });
});
