import { useState } from "react";
import { Alert, Button, Link, Stack, TextField, Typography } from "@mui/material";
import { Link as RouterLink } from "react-router";

import { authApi } from "../../../api/auth.js";
import { paths } from "../../../app/paths.js";
import { toFormErrors } from "../formErrors.js";
import { validateEmail } from "../validation.js";

export default function PasswordResetRequestPage() {
  const [email, setEmail] = useState("");
  const [emailError, setEmailError] = useState(null);
  const [formError, setFormError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    const error = validateEmail(email);
    setEmailError(error);
    setFormError(null);
    if (error || submitting) return;

    setSubmitting(true);
    try {
      const response = await authApi.requestPasswordReset(email.trim());
      setMessage(response.message);
    } catch (error) {
      const { fields, form } = toFormErrors(error, ["email"]);
      setEmailError(fields.email);
      setFormError(form);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Stack spacing={2}>
      <Typography component="h2" variant="h5">Восстановление пароля</Typography>
      {message ? (
        <Alert severity="success" role="status">{message}</Alert>
      ) : (
        <Stack component="form" spacing={2} noValidate onSubmit={handleSubmit}>
          <Typography>Введите адрес электронной почты, указанный при регистрации.</Typography>
          {formError && <Alert severity="error">{formError}</Alert>}
          <TextField
            label="Электронная почта"
            name="email"
            type="email"
            autoComplete="email"
            autoFocus
            value={email}
            onChange={(event) => {
              setEmail(event.target.value);
              setEmailError(null);
            }}
            disabled={submitting}
            error={Boolean(emailError)}
            helperText={emailError}
          />
          <Button type="submit" variant="contained" size="large" disabled={submitting}>
            Отправить ссылку
          </Button>
        </Stack>
      )}
      <Link component={RouterLink} to={paths.login}>Вернуться ко входу</Link>
    </Stack>
  );
}
