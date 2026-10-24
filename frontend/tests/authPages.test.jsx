import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { findHeading, renderRoute, TEST_PASSWORD, TEST_USER } from "./renderRoute.jsx";

const anonymous = { authenticated: false };

async function fillCredentials(user, email, password) {
  if (email) {
    await user.type(screen.getByLabelText("Электронная почта"), email);
  }
  if (password) {
    await user.type(screen.getByLabelText("Пароль"), password);
  }
}

function calledUrls(fetchMock) {
  return fetchMock.mock.calls.map(([url]) => url);
}

describe("LoginPage", () => {
  it("validates the form without calling the API", async () => {
    const { user, fetchMock } = renderRoute("/login", undefined, anonymous);
    await findHeading("Вход");

    await fillCredentials(user, "ivan");
    await user.click(screen.getByRole("button", { name: "Войти" }));

    expect(screen.getByText("Некорректный адрес электронной почты")).toBeTruthy();
    expect(screen.getByText("Введите пароль")).toBeTruthy();
    expect(calledUrls(fetchMock)).not.toContain("/api/auth/login");
  });

  it("shows the backend error for wrong credentials (F_Auth_5)", async () => {
    const { user } = renderRoute("/login", undefined, anonymous);
    await findHeading("Вход");

    await fillCredentials(user, TEST_USER.email, "wrong-password");
    await user.click(screen.getByRole("button", { name: "Войти" }));

    expect(await screen.findByText("Неверный адрес или пароль")).toBeTruthy();
  });

  it("logs in through the auth API", async () => {
    const { user, fetchMock } = renderRoute("/login", undefined, anonymous);
    await findHeading("Вход");

    await fillCredentials(user, TEST_USER.email, TEST_PASSWORD);
    await user.click(screen.getByRole("button", { name: "Войти" }));

    await screen.findByRole("button", { name: "Войти" });
    expect(calledUrls(fetchMock)).toContain("/api/auth/login");
  });
});
