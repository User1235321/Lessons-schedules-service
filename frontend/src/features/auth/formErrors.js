import { ApiError } from "../../api/client.js";

const FIELD_ERRORS = {
  EMAIL_ALREADY_REGISTERED: { field: "email", message: "Этот адрес уже зарегистрирован" }
};

// Раскладывает ошибку API на ошибки полей формы и общее сообщение над формой
export function toFormErrors(error, knownFields) {
  if (!(error instanceof ApiError)) {
    return { fields: {}, form: "Что-то пошло не так. Повторите попытку" };
  }

  const known = FIELD_ERRORS[error.code];
  if (known) {
    return { fields: { [known.field]: known.message }, form: null };
  }

  // INVALID_VALUE от доменной проверки: одно поле и сообщение на русском
  if (error.code === "INVALID_VALUE" && knownFields.includes(error.details.field)) {
    return { fields: { [error.details.field]: error.message }, form: null };
  }

  // VALIDATION_ERROR от pydantic: причины на английском, поэтому показываем только поле
  if (error.code === "VALIDATION_ERROR") {
    const fields = Object.fromEntries(
      (error.details.fields ?? [])
        .filter(({ field }) => knownFields.includes(field))
        .map(({ field }) => [field, "Некорректное значение"])
    );
    return { fields, form: error.message };
  }

  return { fields: {}, form: error.message };
}
