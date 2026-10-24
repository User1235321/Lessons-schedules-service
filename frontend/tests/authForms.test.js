import { describe, expect, it } from "vitest";

import { ApiError } from "../src/api/client.js";
import { toFormErrors } from "../src/features/auth/formErrors.js";
import {
  collectErrors,
  validateEmail,
  validateNewPassword,
  validatePassword
} from "../src/features/auth/validation.js";

describe("validation", () => {
  it("checks email presence and format", () => {
    expect(validateEmail("")).toBe("Укажите адрес электронной почты");
    expect(validateEmail("ivan")).toBe("Некорректный адрес электронной почты");
    expect(validateEmail("ivan@mail")).toBe("Некорректный адрес электронной почты");
    expect(validateEmail(" Ivan@Mail.ru ")).toBeNull();
  });

  it("checks new password length from 6 to 20 (F_Auth_2)", () => {
    expect(validateNewPassword("12345")).not.toBeNull();
    expect(validateNewPassword("123456")).toBeNull();
    expect(validateNewPassword("x".repeat(20))).toBeNull();
    expect(validateNewPassword("x".repeat(21))).not.toBeNull();
  });

  it("only requires a password on login", () => {
    expect(validatePassword("")).toBe("Введите пароль");
    expect(validatePassword("1")).toBeNull();
  });

  it("collects only failed checks", () => {
    expect(collectErrors({ email: null, password: "Введите пароль" })).toEqual({
      password: "Введите пароль"
    });
  });
});

describe("toFormErrors", () => {
  const fields = ["email", "password"];
  const apiError = (status, code, message, details = {}) =>
    new ApiError({ status, code, message, details });

  it("puts a taken email on the email field (F_Auth_3)", () => {
    const error = apiError(409, "EMAIL_ALREADY_REGISTERED", "Адрес уже занят");

    expect(toFormErrors(error, fields)).toEqual({
      fields: { email: "Этот адрес уже зарегистрирован" },
      form: null
    });
  });

  it("puts a domain validation error on its field", () => {
    const error = apiError(422, "INVALID_VALUE", "Пароль должен содержать от 6 до 20 символов", {
      field: "password"
    });

    expect(toFormErrors(error, fields).fields).toEqual({
      password: "Пароль должен содержать от 6 до 20 символов"
    });
  });

  it("marks fields from a request validation error", () => {
    const error = apiError(422, "VALIDATION_ERROR", "Проверьте введённые данные", {
      fields: [{ field: "email", reason: "Field required" }]
    });

    expect(toFormErrors(error, fields)).toEqual({
      fields: { email: "Некорректное значение" },
      form: "Проверьте введённые данные"
    });
  });

  it("shows other errors above the form (F_Auth_5)", () => {
    const error = apiError(401, "INVALID_CREDENTIALS", "Неверный адрес или пароль");

    expect(toFormErrors(error, fields)).toEqual({
      fields: {},
      form: "Неверный адрес или пароль"
    });
  });

  it("falls back to a generic message for unknown errors", () => {
    expect(toFormErrors(new Error("boom"), fields).form).toBe(
      "Что-то пошло не так. Повторите попытку"
    );
  });
});
