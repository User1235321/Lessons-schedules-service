import { describe, expect, it } from "vitest";

import { ApiError } from "../src/api/client.js";
import { toFormErrors } from "../src/features/project-editor/formErrors.js";

const apiError = (status, code, message, details = {}) =>
  new ApiError({ status, code, message, details });

describe("toFormErrors (project editor)", () => {
  it("puts a domain error on its field", () => {
    const error = apiError(409, "SUBJECT_NAME_TAKEN", "Такая дисциплина уже есть", { field: "name" });

    expect(toFormErrors(error)).toEqual({
      fields: { name: "Такая дисциплина уже есть" },
      form: null
    });
  });

  it("marks top-level fields of a request validation error", () => {
    const error = apiError(422, "VALIDATION_ERROR", "Проверьте введённые данные", {
      fields: [{ field: "availability.0.start", reason: "bad time" }]
    });

    expect(toFormErrors(error)).toEqual({
      fields: { availability: "Некорректное значение" },
      form: "Проверьте введённые данные"
    });
  });

  it("shows errors without a field above the form", () => {
    const error = apiError(409, "SUBJECT_IN_USE", "Дисциплина используется");

    expect(toFormErrors(error)).toEqual({ fields: {}, form: "Дисциплина используется" });
  });

  it("falls back to a generic message", () => {
    expect(toFormErrors(new Error("boom")).form).toBe("Что-то пошло не так. Повторите попытку");
  });
});
