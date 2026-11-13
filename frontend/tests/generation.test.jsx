import { screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { POLL_INTERVAL_MS } from "../src/features/generation/useGenerationJob.js";
import { findHeading, renderRoute } from "./renderRoute.jsx";

const isStart = ([url, init]) =>
  /^\/api\/projects\/[^/]+\/generation-jobs$/.test(url) && init?.method === "POST";

const isJobGet = ([url, init]) =>
  /^\/api\/generation-jobs\/[^/]+$/.test(url) && (init?.method ?? "GET") === "GET";

// Опрос идёт по таймеру: часы подменены, но идут сами, чтобы работали ожидания Testing Library
beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
afterEach(() => vi.useRealTimers());

const nextPoll = () => vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS);

async function startCalculation(backend) {
  const rendered = await openGeneration(backend);
  await rendered.user.click(screen.getByRole("button", { name: "Запустить расчёт" }));
  await screen.findByText("В очереди");
  return rendered;
}

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

describe("Generation: progress and result", () => {
  it("polls the job and shows its status and progress (F_Gen_9)", async () => {
    const job = { status: "QUEUED", progress: null, error_message: null };
    await startCalculation({ job });

    Object.assign(job, { status: "RUNNING", progress: 40 });
    await nextPoll();
    expect(await screen.findByText("Выполняется")).toBeTruthy();
    expect(screen.getByRole("progressbar", { name: "Прогресс расчёта" }).getAttribute("aria-valuenow")).toBe("40");
    expect(screen.getByText("40%")).toBeTruthy();

    job.progress = 70;
    await nextPoll();
    expect(await screen.findByText("70%")).toBeTruthy();
  });

  it("shows an unknown progress when the server has none", async () => {
    const job = { status: "QUEUED", progress: null, error_message: null };
    await startCalculation({ job });

    Object.assign(job, { status: "RUNNING", progress: null });
    await nextPoll();

    expect(await screen.findByText("Процент выполнения пока неизвестен")).toBeTruthy();
    expect(screen.getByRole("progressbar", { name: "Прогресс расчёта" }).hasAttribute("aria-valuenow")).toBe(false);
  });

  it("does not allow a second start while the calculation runs", async () => {
    await startCalculation();

    expect(screen.getByRole("button", { name: "Запустить расчёт" }).disabled).toBe(true);
  });

  it("offers the test result when the calculation completes and stops polling", async () => {
    const job = { status: "QUEUED", progress: null, error_message: null };
    const { user, router, fetchMock } = await startCalculation({ job });

    job.status = "COMPLETED";
    await nextPoll();
    expect(await screen.findByText("Расчёт завершён.")).toBeTruthy();
    const polls = fetchMock.mock.calls.filter(isJobGet).length;

    await nextPoll();
    await nextPoll();
    expect(fetchMock.mock.calls.filter(isJobGet).length).toBe(polls);

    await user.click(screen.getByRole("link", { name: "Перейти к тестовому результату" }));
    expect(await findHeading("Просмотр расписания")).toBeTruthy();
    expect(router.state.location.pathname).toBe("/projects/42/schedules/test");
  });

  it("shows why the calculation failed and allows a new start", async () => {
    const job = { status: "QUEUED", progress: null, error_message: null };
    await startCalculation({ job });

    Object.assign(job, { status: "FAILED", error_message: "Не хватает аудиторий" });
    await nextPoll();

    expect(await screen.findByText(/Расчёт завершился ошибкой\. Не хватает аудиторий/)).toBeTruthy();
    expect(screen.getByText("Ошибка")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Запустить расчёт" }).disabled).toBe(false);
  });

  it("shows a cancelled calculation", async () => {
    const job = { status: "QUEUED", progress: null, error_message: null };
    await startCalculation({ job });

    job.status = "CANCELLED";
    await nextPoll();

    expect(await screen.findByText("Расчёт отменён.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Запустить расчёт" }).disabled).toBe(false);
  });

  it("keeps polling after a temporary failure", async () => {
    const job = { status: "QUEUED", progress: null, error_message: null };
    const { fetchMock } = await startCalculation({ job });
    const respond = fetchMock.getMockImplementation();
    fetchMock.mockImplementation(async (url, init) =>
      isJobGet([url, init]) ? Promise.reject(new TypeError("Failed to fetch")) : respond(url, init)
    );

    await nextPoll();
    expect(await screen.findByText(/Не удаётся получить состояние расчёта/)).toBeTruthy();

    fetchMock.mockImplementation(respond);
    Object.assign(job, { status: "RUNNING", progress: 10 });
    await nextPoll();

    expect(await screen.findByText("Выполняется")).toBeTruthy();
    expect(screen.queryByText(/Не удаётся получить состояние расчёта/)).toBeNull();
  });

  it("stops following a job that disappeared on the server", async () => {
    const { fetchMock } = await startCalculation();
    const respond = fetchMock.getMockImplementation();
    fetchMock.mockImplementation(async (url, init) =>
      isJobGet([url, init])
        ? new Response(
            JSON.stringify({ code: "NOT_FOUND", message: "Задание не найдено", details: {} }),
            { status: 404 }
          )
        : respond(url, init)
    );

    await nextPoll();

    expect(await screen.findByText("Задание не найдено")).toBeTruthy();
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.getByRole("button", { name: "Запустить расчёт" }).disabled).toBe(false);
  });
});
