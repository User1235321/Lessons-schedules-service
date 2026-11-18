import { screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { POLL_INTERVAL_MS } from "../src/features/generation/useGenerationJob.js";
import { findHeading, renderRoute } from "./renderRoute.jsx";

const isStart = ([url, init]) =>
  /^\/api\/projects\/[^/]+\/generation-jobs$/.test(url) && init?.method === "POST";

const isJobGet = ([url, init]) =>
  /^\/api\/generation-jobs\/[^/]+$/.test(url) && (init?.method ?? "GET") === "GET";

const isScheduleGet = ([url, init]) =>
  /^\/api\/generation-jobs\/[^/]+\/schedules$/.test(url) &&
  (init?.method ?? "GET") === "GET";

beforeEach(() => {
  sessionStorage.clear();
  vi.useFakeTimers({ shouldAdvanceTime: true });
});
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

  it("rejects TOP-N values outside the safe integer range", async () => {
    const { user, fetchMock } = await openGeneration();

    await user.click(screen.getByRole("radio", { name: "TOP-N лучших вариантов" }));
    const count = screen.getByLabelText("Число вариантов (N)");
    await user.clear(count);
    await user.type(count, "9007199254740992");
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

  it("starts consecutive polls two seconds apart when responses take 500 ms", async () => {
    const { fetchMock } = await startCalculation();
    const respond = fetchMock.getMockImplementation();
    const startedAt = [];

    fetchMock.mockImplementation(async (url, init) => {
      if (!isJobGet([url, init])) {
        return respond(url, init);
      }
      startedAt.push(Date.now());
      await new Promise((resolve) => setTimeout(resolve, 500));
      return respond(url, init);
    });

    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 3 + 750);

    expect(startedAt).toHaveLength(3);
    expect(startedAt[1] - startedAt[0]).toBe(POLL_INTERVAL_MS);
    expect(startedAt[2] - startedAt[1]).toBe(POLL_INTERVAL_MS);
  });

  it("never starts concurrent polls even when the server takes over two seconds", async () => {
    const { fetchMock } = await startCalculation();
    const respond = fetchMock.getMockImplementation();
    let requestsInFlight = 0;
    let maxConcurrent = 0;

    fetchMock.mockImplementation(async (url, init) => {
      if (!isJobGet([url, init])) {
        return respond(url, init);
      }
      requestsInFlight += 1;
      maxConcurrent = Math.max(maxConcurrent, requestsInFlight);
      await new Promise((resolve) => setTimeout(resolve, 2500));
      requestsInFlight -= 1;
      return respond(url, init);
    });

    await vi.advanceTimersByTimeAsync(7600);

    expect(maxConcurrent).toBe(1);
    expect(fetchMock.mock.calls.filter(isJobGet).length).toBeGreaterThanOrEqual(2);
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

  it("shows completion and stops polling", async () => {
    const job = { status: "QUEUED", progress: null, error_message: null };
    const { fetchMock } = await startCalculation({ job });

    job.status = "COMPLETED";
    await nextPoll();
    expect(await screen.findByText("Расчёт завершён.")).toBeTruthy();
    const polls = fetchMock.mock.calls.filter(isJobGet).length;

    await nextPoll();
    await nextPoll();
    expect(fetchMock.mock.calls.filter(isJobGet).length).toBe(polls);

    const link = await screen.findByRole("link", { name: "Открыть расписание" });
    expect(link.getAttribute("href")).toBe("/projects/42/schedules/schedule-1");
    expect(fetchMock.mock.calls.some(isScheduleGet)).toBe(true);
  });

  it("navigates to the actual schedule after the job completes", async () => {
    const job = { status: "QUEUED", progress: null, error_message: null };
    const { user } = await startCalculation({ job, schedules: [{ id: "schedule-real", result_index: 1 }] });

    job.status = "COMPLETED";
    await nextPoll();

    const link = await screen.findByRole("link", { name: "Открыть расписание" });
    expect(link.getAttribute("href")).toBe("/projects/42/schedules/schedule-real");
    await user.click(link);
    expect(await screen.findByText("Расписание schedule-real")).toBeTruthy();
  });

  it("reports when the calculation completed without an admissible schedule", async () => {
    const job = { status: "QUEUED", progress: null, error_message: null };
    await startCalculation({ job, schedules: [] });

    job.status = "COMPLETED";
    await nextPoll();

    expect(await screen.findByText("Допустимое расписание не найдено.")).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Открыть расписание" })).toBeNull();
  });

  it("retries loading schedules after an API failure", async () => {
    const job = { status: "QUEUED", progress: null, error_message: null };
    const { user, fetchMock } = await startCalculation({ job });
    const respond = fetchMock.getMockImplementation();
    let attempts = 0;

    fetchMock.mockImplementation(async (url, init) => {
      if (isScheduleGet([url, init]) && ++attempts === 1) {
        return new Response(
          JSON.stringify({ code: "LOAD_FAILED", message: "Временный сбой", details: {} }),
          { status: 500 }
        );
      }
      return respond(url, init);
    });

    job.status = "COMPLETED";
    await nextPoll();

    expect(await screen.findByText(/Не удалось загрузить результаты: Временный сбой/)).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Повторить загрузку" }));

    expect(await screen.findByRole("link", { name: "Открыть расписание" })).toBeTruthy();
    expect(attempts).toBe(2);
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

describe("Generation: cancel", () => {
  const isCancel = ([url, init]) =>
    /^\/api\/generation-jobs\/[^/]+\/cancel$/.test(url) && init?.method === "POST";

  it("cancels a running calculation (F_Gen_10)", async () => {
    const { user, fetchMock } = await startCalculation();

    await user.click(screen.getByRole("button", { name: "Отменить расчёт" }));

    expect(await screen.findByText("Расчёт отменён.")).toBeTruthy();
    expect(screen.getByText("Отменён")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Отменить расчёт" })).toBeNull();
    expect(fetchMock.mock.calls.filter(isCancel)).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Запустить расчёт" }).disabled).toBe(false);
  });

  it("waits for the worker when the cancel is only accepted", async () => {
    const job = { status: "QUEUED", progress: null, error_message: null };
    const { user, fetchMock } = await startCalculation({ job });
    const respond = fetchMock.getMockImplementation();
    fetchMock.mockImplementation(async (url, init) =>
      isCancel([url, init])
        ? new Response(
            JSON.stringify({ id: "job-1", project_id: "42", job_type: "GENERATE", status: "RUNNING", progress: 55, error_message: null }),
            { status: 202 }
          )
        : respond(url, init)
    );

    await user.click(screen.getByRole("button", { name: "Отменить расчёт" }));

    expect(await screen.findByText(/Отмена запрошена/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Отменить расчёт" }).disabled).toBe(true);

    job.status = "CANCELLED";
    await nextPoll();
    expect(await screen.findByText("Расчёт отменён.")).toBeTruthy();
    expect(screen.queryByText(/Отмена запрошена/)).toBeNull();
  });

  it("shows the real outcome when the calculation finished before the cancel", async () => {
    const job = { status: "QUEUED", progress: null, error_message: null };
    const { user } = await startCalculation({ job });

    job.status = "COMPLETED"; // интерфейс ещё не знает: опрос не успел
    await user.click(screen.getByRole("button", { name: "Отменить расчёт" }));

    expect(await screen.findByText("Расчёт уже завершён и не может быть отменён")).toBeTruthy();
    expect(await screen.findByText("Расчёт завершён.")).toBeTruthy();
  });

  it("ignores an older poll response after cancellation has been accepted", async () => {
    const { user, fetchMock } = await startCalculation();
    const respond = fetchMock.getMockImplementation();
    let releasePoll;

    fetchMock.mockImplementation((url, init) => {
      if (isJobGet([url, init]) && !releasePoll) {
        return new Promise((resolve) => {
          releasePoll = () => resolve(new Response(
            JSON.stringify({
              id: "job-1",
              project_id: "42",
              job_type: "GENERATE",
              status: "QUEUED",
              progress: null,
              error_message: null
            }),
            { status: 200 }
          ));
        });
      }
      if (/^\/api\/generation-jobs\/[^/]+\/cancel$/.test(url) && init?.method === "POST") {
        return Promise.resolve(new Response(
          JSON.stringify({
            id: "job-1",
            project_id: "42",
            job_type: "GENERATE",
            status: "RUNNING",
            progress: 20,
            error_message: null
          }),
          { status: 202 }
        ));
      }
      return respond(url, init);
    });

    await nextPoll();
    expect(releasePoll).toBeTypeOf("function");

    await user.click(screen.getByRole("button", { name: "Отменить расчёт" }));
    expect(await screen.findByText("Выполняется")).toBeTruthy();
    expect(await screen.findByText(/Отмена запрошена/)).toBeTruthy();

    releasePoll();
    await Promise.resolve();
    await Promise.resolve();

    expect(screen.queryByText("В очереди")).toBeNull();
    expect(screen.getByText("Выполняется")).toBeTruthy();
  });

  it("shows a cancel error and lets the user try again", async () => {
    const { user, fetchMock } = await startCalculation();
    const respond = fetchMock.getMockImplementation();
    fetchMock.mockImplementation(async (url, init) =>
      isCancel([url, init]) ? Promise.reject(new TypeError("Failed to fetch")) : respond(url, init)
    );

    await user.click(screen.getByRole("button", { name: "Отменить расчёт" }));

    expect(await screen.findByText(/Сервер недоступен/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Отменить расчёт" }).disabled).toBe(false);
  });
});

describe("Generation: returning to the page", () => {
  const RUNNING = () => ({ status: "RUNNING", progress: 60, error_message: null });

  it("restores the calculation after switching project tabs", async () => {
    const job = { status: "QUEUED", progress: null, error_message: null };
    const { user, fetchMock } = await startCalculation({ job });

    await user.click(screen.getByRole("tab", { name: "Настройки" }));
    await findHeading("Настройки проекта");
    Object.assign(job, RUNNING());
    await user.click(screen.getByRole("tab", { name: "Расчёт" }));

    expect(await screen.findByText("Выполняется")).toBeTruthy();
    expect(screen.getByText("60%")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Запустить расчёт" }).disabled).toBe(true);
    expect(fetchMock.mock.calls.some(isJobGet)).toBe(true);
  });

  it("restores a calculation after a page reload", async () => {
    sessionStorage.setItem("generation-job:42", "job-1");

    renderRoute("/projects/42/generation", undefined, { job: RUNNING() });

    expect(await screen.findByText("Выполняется")).toBeTruthy();
    expect(screen.getByText("60%")).toBeTruthy();
  });

  it("forgets a job that no longer exists", async () => {
    sessionStorage.setItem("generation-job:42", "job-gone");

    renderRoute("/projects/42/generation");
    await findHeading("Построение расписания");

    await vi.waitFor(() =>
      expect(screen.getByRole("button", { name: "Запустить расчёт" }).disabled).toBe(false)
    );
    expect(sessionStorage.getItem("generation-job:42")).toBeNull();
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("keeps following the job when the state cannot be fetched at once", async () => {
    sessionStorage.setItem("generation-job:42", "job-1");
    const job = RUNNING();
    const { fetchMock } = renderRoute("/projects/42/generation", undefined, { job });
    const respond = fetchMock.getMockImplementation();
    fetchMock.mockImplementation(async (url, init) =>
      isJobGet([url, init]) ? Promise.reject(new TypeError("Failed to fetch")) : respond(url, init)
    );
    await findHeading("Построение расписания");

    expect(await screen.findByText("Неизвестно")).toBeTruthy();
    expect(screen.getByText(/Не удаётся получить состояние расчёта/)).toBeTruthy();

    fetchMock.mockImplementation(respond);
    await nextPoll();
    expect(await screen.findByText("Выполняется")).toBeTruthy();
  });

  it("does not show a calculation of another project", async () => {
    sessionStorage.setItem("generation-job:42", "job-1");

    const { fetchMock } = renderRoute("/projects/43/generation", undefined, { job: RUNNING() });
    await findHeading("Построение расписания");

    expect(screen.queryByRole("status")).toBeNull();
    expect(fetchMock.mock.calls.some(isJobGet)).toBe(false);
    expect(screen.getByRole("button", { name: "Запустить расчёт" }).disabled).toBe(false);
  });
});
