import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import ErrorState from "../src/components/ErrorState.jsx";
import LoadingState from "../src/components/LoadingState.jsx";
import RouteErrorBoundary from "../src/components/RouteErrorBoundary.jsx";
import { findHeading, renderRoute } from "./renderRoute.jsx";

describe("LoadingState", () => {
  it("renders a labelled progress indicator", () => {
    render(<LoadingState label="Загружаем проекты" />);

    expect(screen.getByRole("progressbar", { name: "Загружаем проекты" })).toBeTruthy();
    expect(screen.getByText("Загружаем проекты")).toBeTruthy();
  });
});

describe("ErrorState", () => {
  it("shows the message and calls onRetry", async () => {
    const onRetry = vi.fn();
    const user = userEvent.setup();

    render(<ErrorState message="Сервер недоступен" onRetry={onRetry} />);

    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByText("Сервер недоступен")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Повторить" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("hides the retry button when onRetry is not passed", () => {
    render(<ErrorState message="Ошибка" />);

    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("RouteErrorBoundary", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  function Broken() {
    throw new Error("Сломалось при рендере");
  }

  it("shows the error thrown by a route", async () => {
    // React и роутер логируют пойманную ошибку — в тесте это ожидаемо.
    vi.spyOn(console, "error").mockImplementation(() => {});

    renderRoute("/", [
      { path: "/", Component: Broken, errorElement: <RouteErrorBoundary /> }
    ]);

    expect(await screen.findByText("Что-то пошло не так")).toBeTruthy();
    expect(screen.getByText("Сломалось при рендере")).toBeTruthy();
  });

  it("renders not found page for 404 responses", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});

    renderRoute("/", [
      {
        path: "/",
        loader: () => {
          throw new Response("Not Found", { status: 404, statusText: "Not Found" });
        },
        Component: () => null,
        errorElement: <RouteErrorBoundary />
      }
    ]);

    expect(await findHeading("Страница не найдена")).toBeTruthy();
  });
});
