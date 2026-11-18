import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderRoute } from "./renderRoute.jsx";

describe("ResourceSection resource loading", () => {
  it("disables creation after a failed list request", async () => {
    const { fetchMock } = renderRoute("/projects/42/subjects", undefined, {
      failedResourceLoads: ["subjects"]
    });

    expect(await screen.findByText("Не удалось загрузить ресурсы")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Добавить дисциплину" }).disabled).toBe(true);
    expect(fetchMock.mock.calls.some(([url, init]) =>
      url === "/api/projects/42/subjects" && init?.method === "POST"
    )).toBe(false);
  });
});
