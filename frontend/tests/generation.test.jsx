import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { findHeading, renderRoute } from "./renderRoute.jsx";

const isStart = ([url, init]) =>
  /^\/api\/projects\/[^/]+\/generation-jobs$/.test(url) && init?.method === "POST";

async function openGeneration(backend) {
  const rendered = renderRoute("/projects/42/generation", undefined, backend);
  await findHeading("Построение расписания");
  return rendered;
}

describe("Generation: start", () => {
  it("starts a single-variant calculation and shows it queued", async () => {
    const { user, fetchMock } = await openGeneration();

    await user.click(screen.getByRole("button", { name: "Запустить расчёт" }));

    expect(await screen.findByText("В очереди")).toBeTruthy();
    const [url, init] = fetchMock.mock.calls.find(isStart);
    expect(url).toBe("/api/projects/42/generation-jobs");
    expect(JSON.parse(init.body)).toEqual({ result_mode: "SINGLE", top_n: null });
  });

  it("starts TOP-N with the chosen number (F_Gen_4)", async () => {
    const { user, fetchMock } = await openGeneration();

    await user.click(screen.getByRole("radio", { name: "TOP-N лучших вариантов" }));
    const count = screen.getByLabelText("Число вариантов (N)");
    expect(count.value).toBe("5");
    await user.clear(count);
    await user.type(count, "3");
    await user.click(screen.getByRole("button", { name: "Запустить расчёт" }));

    expect(await screen.findByText("В очереди")).toBeTruthy();
    const [, init] = fetchMock.mock.calls.find(isStart);
    expect(JSON.parse(init.body)).toEqual({ result_mode: "TOP_N", top_n: 3 });
  });

  it("does not start TOP-N without a positive number", async () => {
    const { user, fetchMock } = await openGeneration();

    await user.click(screen.getByRole("radio", { name: "TOP-N лучших вариантов" }));
    const count = screen.getByLabelText("Число вариантов (N)");
    await user.clear(count);
    await user.type(count, "0");
    await user.click(screen.getByRole("button", { name: "Запустить расчёт" }));

    expect(screen.getByText("Укажите целое число вариантов больше нуля")).toBeTruthy();
    expect(fetchMock.mock.calls.some(isStart)).toBe(false);
  });

  it("shows a start error from the server", async () => {
    const { user, fetchMock } = await openGeneration();
    const respond = fetchMock.getMockImplementation();
    fetchMock.mockImplementation(async (url, init) =>
      isStart([url, init])
        ? new Response(
            JSON.stringify({
              code: "INVALID_VALUE",
              message: "Не хватает данных для расчёта",
              details: { field: "project" }
            }),
            { status: 422 }
          )
        : respond(url, init)
    );

    await user.click(screen.getByRole("button", { name: "Запустить расчёт" }));

    expect(await screen.findByText("Не хватает данных для расчёта")).toBeTruthy();
    expect(screen.queryByText("В очереди")).toBeNull();
  });
});
