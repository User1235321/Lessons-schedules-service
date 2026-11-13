import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { findHeading, renderRoute } from "./renderRoute.jsx";

const SUBJECTS = [
  { id: "s1", name: "Математика" },
  { id: "s2", name: "Физика" }
];

function openSubjects(backend = {}) {
  const rendered = renderRoute("/projects/42/subjects", undefined, {
    resources: { subjects: SUBJECTS },
    ...backend
  });
  return rendered;
}

const isSubjectPost = ([url, init]) => url === "/api/projects/42/subjects" && init?.method === "POST";

async function table() {
  return screen.findByRole("table", { name: "Дисциплины" });
}

async function openAddDialog(user) {
  await user.click(screen.getByRole("button", { name: "Добавить дисциплину" }));
  return screen.findByRole("dialog", { name: "Новая дисциплина" });
}

describe("Subjects section", () => {
  it("lists the subjects", async () => {
    openSubjects();

    const list = await table();
    expect(within(list).getByText("Математика")).toBeTruthy();
    expect(within(list).getByText("Физика")).toBeTruthy();
  });

  it("shows an empty state", async () => {
    renderRoute("/projects/42/subjects");

    expect(await screen.findByText(/Дисциплин пока нет/)).toBeTruthy();
  });

  it("shows a load error and retries", async () => {
    const { user, fetchMock } = openSubjects();
    const respond = fetchMock.getMockImplementation();
    fetchMock.mockImplementation(async (url, init) =>
      url === "/api/projects/42/subjects"
        ? Promise.reject(new TypeError("Failed to fetch"))
        : respond(url, init)
    );
    await findHeading("Дисциплины");

    expect(await screen.findByText("Не удалось загрузить данные")).toBeTruthy();

    fetchMock.mockImplementation(respond);
    await user.click(screen.getByRole("button", { name: "Повторить" }));

    expect(within(await table()).getByText("Математика")).toBeTruthy();
  });

  it("requires a name and does not call the API without it", async () => {
    const { user, fetchMock } = openSubjects();
    await table();

    const dialog = await openAddDialog(user);
    await user.type(within(dialog).getByLabelText("Название дисциплины"), "   ");
    await user.click(within(dialog).getByRole("button", { name: "Добавить" }));

    expect(within(dialog).getByText("Укажите название дисциплины")).toBeTruthy();
    expect(fetchMock.mock.calls.some(isSubjectPost)).toBe(false);
  });

  it("adds a subject", async () => {
    const { user, fetchMock } = openSubjects();
    const list = await table();

    const dialog = await openAddDialog(user);
    await user.type(within(dialog).getByLabelText("Название дисциплины"), "  Химия ");
    await user.click(within(dialog).getByRole("button", { name: "Добавить" }));

    expect(await within(list).findByText("Химия")).toBeTruthy();
    const [, init] = fetchMock.mock.calls.find(isSubjectPost);
    expect(JSON.parse(init.body)).toEqual({ name: "Химия" });
  });

  it("shows the backend error for a taken name next to the field", async () => {
    const { user } = openSubjects();
    await table();

    const dialog = await openAddDialog(user);
    await user.type(within(dialog).getByLabelText("Название дисциплины"), "математика");
    await user.click(within(dialog).getByRole("button", { name: "Добавить" }));

    expect(await within(dialog).findByText("Такое название уже есть")).toBeTruthy();
  });

  it("renames a subject", async () => {
    const { user, fetchMock } = openSubjects();
    const list = await table();

    await user.click(within(list).getByRole("button", { name: "Изменить: Физика" }));
    const dialog = await screen.findByRole("dialog", { name: "Изменить дисциплину" });
    const field = within(dialog).getByLabelText("Название дисциплины");
    expect(field.value).toBe("Физика");
    await user.clear(field);
    await user.type(field, "Астрономия");
    await user.click(within(dialog).getByRole("button", { name: "Сохранить" }));

    expect(await within(list).findByText("Астрономия")).toBeTruthy();
    expect(within(list).queryByText("Физика")).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/projects/42/subjects/s2",
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ name: "Астрономия" }) })
    );
  });

  it("asks for confirmation and keeps the subject on cancel", async () => {
    const { user, fetchMock } = openSubjects();
    const list = await table();

    await user.click(within(list).getByRole("button", { name: "Удалить: Физика" }));
    const dialog = await screen.findByRole("dialog", { name: "Удалить?" });
    await user.click(within(dialog).getByRole("button", { name: "Отмена" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(within(list).getByText("Физика")).toBeTruthy();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(false);
  });

  it("deletes a subject after confirmation", async () => {
    const { user } = openSubjects();
    const list = await table();

    await user.click(within(list).getByRole("button", { name: "Удалить: Физика" }));
    const dialog = await screen.findByRole("dialog", { name: "Удалить?" });
    await user.click(within(dialog).getByRole("button", { name: "Удалить" }));

    await waitFor(() => expect(within(list).queryByText("Физика")).toBeNull());
    expect(within(list).getByText("Математика")).toBeTruthy();
  });

  it("keeps a subject that is in use and shows why", async () => {
    const { user } = openSubjects({ blockedDeletes: ["s1"] });
    const list = await table();

    await user.click(within(list).getByRole("button", { name: "Удалить: Математика" }));
    const dialog = await screen.findByRole("dialog", { name: "Удалить?" });
    await user.click(within(dialog).getByRole("button", { name: "Удалить" }));

    expect(await within(dialog).findByText("Дисциплина используется")).toBeTruthy();
    expect(within(list).getByText("Математика")).toBeTruthy();
  });
});
