import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { findHeading, renderRoute, TEST_USER } from "./renderRoute.jsx";

const guest = { authenticated: false };
const requestUrl = "/api/auth/password-reset/request";
const confirmUrl = "/api/auth/password-reset/confirm";

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

describe("Смена пароля по ссылке из письма", () => {
  it("проверяет длину пароля, отправляет токен из фрагмента и возвращает ко входу", async () => {
    const { user, fetchMock } = renderRoute("/password-reset/confirm#token=from-email", undefined, guest);
    await findHeading("Новый пароль");
    const password = screen.getByLabelText("Новый пароль");
    const submit = screen.getByRole("button", { name: "Сохранить пароль" });
    await user.type(password, "short");
    await user.click(submit);
    expect(screen.getByText("Пароль должен содержать от 6 до 20 символов")).toBeTruthy();
    expect(fetchMock.mock.calls.some(([url]) => url === confirmUrl)).toBe(false);

    await user.clear(password);
    await user.type(password, "new-password");
    await user.click(submit);
    expect((await screen.findByRole("status")).textContent).toContain("Пароль изменён");
    expect(fetchMock).toHaveBeenCalledWith(confirmUrl, expect.objectContaining({
      method: "POST", body: JSON.stringify({ token: "from-email", password: "new-password" })
    }));
    await user.click(screen.getByRole("link", { name: "Вернуться ко входу" }));
    expect(await findHeading("Вход")).toBeTruthy();
  });

  it("предлагает запросить новую ссылку, если токена нет", async () => {
    const { user, fetchMock } = renderRoute("/password-reset/confirm", undefined, guest);
    await findHeading("Новый пароль");
    expect(screen.queryByLabelText("Новый пароль")).toBeNull();
    expect(fetchMock.mock.calls.some(([url]) => url === confirmUrl)).toBe(false);
    await user.click(screen.getByRole("link", { name: "Запросить новую ссылку" }));
    expect(await findHeading("Восстановление пароля")).toBeTruthy();
  });

  it("обрабатывает отклонённый токен без повторного запроса и обновления сессии", async () => {
    const { user, fetchMock } = renderRoute("/password-reset/confirm#token=expired", undefined, guest);
    await findHeading("Новый пароль");
    await user.type(screen.getByLabelText("Новый пароль"), "new-password");
    fetchMock.mockClear();
    await user.click(screen.getByRole("button", { name: "Сохранить пароль" }));
    expect((await screen.findByRole("alert")).textContent).toContain("недействительна или устарела");
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([confirmUrl]);
    expect(screen.queryByLabelText("Новый пароль")).toBeNull();
  });
});
