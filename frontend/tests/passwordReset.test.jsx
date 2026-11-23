import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { findHeading, renderRoute, TEST_USER } from "./renderRoute.jsx";

const guest = { authenticated: false };
const requestUrl = "/api/auth/password-reset/request";

describe("Запрос на восстановление пароля", () => {
  it("открывается со страницы входа и проверяет адрес до отправки", async () => {
    const { user, fetchMock } = renderRoute("/login", undefined, guest);
    await user.click(await screen.findByRole("link", { name: "Забыли пароль?" }));
    await findHeading("Восстановление пароля");
    await user.type(screen.getByLabelText("Электронная почта"), "invalid");
    await user.click(screen.getByRole("button", { name: "Отправить ссылку" }));

    expect(screen.getByText("Некорректный адрес электронной почты")).toBeTruthy();
    expect(fetchMock.mock.calls.some(([url]) => url === requestUrl)).toBe(false);
  });

  it.each([TEST_USER.email, "unknown@example.com"])("показывает нейтральный ответ для %s", async (email) => {
    const { user, fetchMock } = renderRoute("/password-reset", undefined, guest);
    await findHeading("Восстановление пароля");
    await user.type(screen.getByLabelText("Электронная почта"), email);
    await user.click(screen.getByRole("button", { name: "Отправить ссылку" }));

    expect((await screen.findByRole("status")).textContent).toContain("Если аккаунт с таким адресом существует");
    expect(fetchMock).toHaveBeenCalledWith(requestUrl, expect.objectContaining({
      method: "POST", body: JSON.stringify({ email })
    }));
  });
});
