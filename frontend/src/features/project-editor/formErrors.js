import { ApiError } from "../../api/client.js";

// Раскладывает ошибку API на ошибки полей формы и общее сообщение над формой.
// Доменные ошибки бэкенда несут поле в details.field, а текст на русском
export function toFormErrors(error) {
  if (!(error instanceof ApiError)) {
    return { fields: {}, form: "Что-то пошло не так. Повторите попытку" };
  }

  const field = error.details?.field;
  if (typeof field === "string") {
    return { fields: { [field]: error.message }, form: null };
  }

  // VALIDATION_ERROR от pydantic: причины на английском, поэтому показываем только поля
  if (error.code === "VALIDATION_ERROR") {
    const fields = Object.fromEntries(
      (error.details?.fields ?? []).map(({ field: name }) => [name.split(".")[0], "Некорректное значение"])
    );
    return { fields, form: error.message };
  }

  return { fields: {}, form: error.message };
}
