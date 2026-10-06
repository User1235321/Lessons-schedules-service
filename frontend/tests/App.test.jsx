import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "../src/App.jsx";

describe("App", () => {
  it("renders application title", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: "Lessons schedules service" })
    ).toBeTruthy();
  });
});
