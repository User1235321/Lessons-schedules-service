import { ApiError } from "../../api/client.js";

export function toFormErrors(error) {
  if (!(error instanceof ApiError)) {
    return { fields: {}, form: "Что-то пошло не так. Повторите попытку" };
  }

  const field = error.details?.field;
  if (typeof field === "string") {
    return { fields: { [field.split(".")[0]]: error.message }, form: null };
  }

  if (error.code === "VALIDATION_ERROR") {
    const fields = Object.fromEntries(
      (error.details?.fields ?? []).map(({ field: name }) => [name.split(".")[0], "Некорректное значение"])
    );
    return { fields, form: error.message };
  }

  return { fields: {}, form: error.message };
}
