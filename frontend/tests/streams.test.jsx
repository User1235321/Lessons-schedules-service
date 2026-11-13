import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderRoute } from "./renderRoute.jsx";

const GROUPS = [
  { id: "g1", name: "301", student_count: 25, subgroups: [] },
  { id: "g2", name: "302", student_count: 20, subgroups: [] },
  { id: "g3", name: "303", student_count: 18, subgroups: [] }
];
const STREAM = { id: "st1", name: "301 + 302", group_ids: ["g1", "g2"] };

function openStreams(resources = { groups: GROUPS, streams: [STREAM] }, backend = {}) {
  return renderRoute("/projects/42/streams", undefined, { resources, ...backend });
}

const table = () => screen.findByRole("table", { name: "Потоки" });
const isStreamWrite = ([url, init]) =>
  /^\/api\/projects\/42\/streams/.test(url) && ["POST", "PATCH"].includes(init?.method);

async function openAddDialog(user) {
  await user.click(await screen.findByRole("button", { name: "Добавить поток" }));
  return screen.findByRole("dialog", { name: "Новый поток" });
}

describe("Streams section", () => {
  it("lists streams with their groups and total students", async () => {
    openStreams();

    const list = await table();
    expect(within(list).getByText("301 + 302")).toBeTruthy();
    expect(within(list).getByText("301, 302")).toBeTruthy();
    expect(within(list).getByText("45")).toBeTruthy();
  });

  it("requires a name and at least one group (F_Data_14)", async () => {
    const { user, fetchMock } = openStreams({ groups: GROUPS });

    const dialog = await openAddDialog(user);
    await user.click(within(dialog).getByRole("button", { name: "Добавить" }));

    expect(within(dialog).getByText("Укажите название потока")).toBeTruthy();
    expect(within(dialog).getByText("Выберите хотя бы одну группу")).toBeTruthy();
    expect(fetchMock.mock.calls.some(isStreamWrite)).toBe(false);
  });

  it("asks to add groups first when there are none", async () => {
    const { user } = openStreams({});

    const dialog = await openAddDialog(user);

    expect(within(dialog).getByText(/Сначала добавьте группы/)).toBeTruthy();
    expect(within(dialog).getByRole("link", { name: "«Группы»" })).toBeTruthy();
  });

  it("adds a stream from selected groups", async () => {
    const { user, fetchMock } = openStreams({ groups: GROUPS });
    await screen.findByText(/Потоков пока нет/);

    const dialog = await openAddDialog(user);
    await user.type(within(dialog).getByLabelText("Название потока"), "Весь курс");
    await user.click(within(dialog).getByLabelText("301 (25)"));
    await user.click(within(dialog).getByLabelText("303 (18)"));
    await user.click(within(dialog).getByRole("button", { name: "Добавить" }));

    const list = await table();
    expect(await within(list).findByText("Весь курс")).toBeTruthy();
    const [, init] = fetchMock.mock.calls.find(isStreamWrite);
    expect(JSON.parse(init.body)).toEqual({ name: "Весь курс", group_ids: ["g1", "g3"] });
  });

  it("changes the stream composition", async () => {
    const { user, fetchMock } = openStreams();
    const list = await table();

    await user.click(within(list).getByRole("button", { name: "Изменить: 301 + 302" }));
    const dialog = await screen.findByRole("dialog", { name: "Изменить поток" });
    expect(within(dialog).getByLabelText("301 (25)").checked).toBe(true);
    await user.click(within(dialog).getByLabelText("302 (20)"));
    await user.click(within(dialog).getByLabelText("303 (18)"));
    await user.click(within(dialog).getByRole("button", { name: "Сохранить" }));

    expect(await within(list).findByText("301, 303")).toBeTruthy();
    const [url, init] = fetchMock.mock.calls.find(isStreamWrite);
    expect(url).toBe("/api/projects/42/streams/st1");
    expect(JSON.parse(init.body)).toEqual({ name: "301 + 302", group_ids: ["g1", "g3"] });
  });

  it("keeps a stream that the server refuses to delete", async () => {
    const { user } = openStreams(undefined, { blockedDeletes: ["st1"] });
    const list = await table();

    await user.click(within(list).getByRole("button", { name: "Удалить: 301 + 302" }));
    const dialog = await screen.findByRole("dialog", { name: "Удалить?" });
    await user.click(within(dialog).getByRole("button", { name: "Удалить" }));

    expect(await within(dialog).findByText("Используется в нагрузке")).toBeTruthy();
    expect(within(list).getByText("301 + 302")).toBeTruthy();
  });
});
