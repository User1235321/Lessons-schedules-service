import { useState } from "react";
import { Alert, Button, Link, Stack, TextField, Typography } from "@mui/material";
import { Link as RouterLink, useLocation } from "react-router";

import { authApi } from "../../../api/auth.js";
import { paths } from "../../../app/paths.js";
import { toFormErrors } from "../formErrors.js";
import { MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH, validateNewPassword } from "../validation.js";

function PasswordResetConfirmForm({ token }) {
  const [password, setPassword] = useState("");
  const [passwordError, setPasswordError] = useState(null);
  const [formError, setFormError] = useState(null);
  const [invalidLink, setInvalidLink] = useState(!token);
  const [submitting, setSubmitting] = useState(false);
  const [completed, setCompleted] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    const error = validateNewPassword(password);
    setPasswordError(error);
    setFormError(null);
    if (error || submitting) return;

    setSubmitting(true);
    try {
      await authApi.confirmPasswordReset(token, password);
      setPassword("");
      setCompleted(true);
    } catch (error) {
      if (error.code === "INVALID_PASSWORD_RESET_TOKEN") {
        setPassword("");
        setInvalidLink(true);
      } else {
        const { fields, form } = toFormErrors(error, ["password"]);
        setPasswordError(fields.password);
        setFormError(form);
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Stack spacing={2}>
      <Typography component="h2" variant="h5">Новый пароль</Typography>
      {invalidLink && (
        <>
          <Alert severity="error">Ссылка для восстановления пароля недействительна или устарела.</Alert>
          <Link component={RouterLink} to={paths.passwordReset}>Запросить новую ссылку</Link>
        </>
      )}
      {completed && <Alert severity="success" role="status">Пароль изменён. Теперь можно войти с новым паролем.</Alert>}
      {!invalidLink && !completed && (
        <Stack component="form" spacing={2} noValidate onSubmit={handleSubmit}>
          {formError && <Alert severity="error">{formError}</Alert>}
          <TextField
            name="password"
            label="Новый пароль"
            type="password"
            autoComplete="new-password"
            autoFocus
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
              setPasswordError(null);
            }}
            disabled={submitting}
            error={Boolean(passwordError)}
            helperText={passwordError ?? `От ${MIN_PASSWORD_LENGTH} до ${MAX_PASSWORD_LENGTH} символов`}
          />
          <Button type="submit" variant="contained" size="large" disabled={submitting}>
            Сохранить пароль
          </Button>
        </Stack>
      )}
      <Link component={RouterLink} to={paths.login}>Вернуться ко входу</Link>
    </Stack>
  );
}

export default function PasswordResetConfirmPage() {
  const { hash } = useLocation();
  const token = new URLSearchParams(hash.slice(1)).get("token");
  return <PasswordResetConfirmForm key={token} token={token} />;
}
