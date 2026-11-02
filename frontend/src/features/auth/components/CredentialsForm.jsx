import { useState } from "react";
import { Alert, Box, Button, Stack, TextField, Typography } from "@mui/material";

import { toFormErrors } from "../formErrors.js";

const FIELDS = ["email", "password"];

// Форма email + пароль для входа и регистрации. validate возвращает ошибки по полям,
// onSubmit отправляет данные и бросает ApiError, если сервер их не принял
export default function CredentialsForm({
  title,
  submitLabel,
  passwordAutoComplete,
  passwordHelperText,
  validate,
  onSubmit,
  children
}) {
  const [values, setValues] = useState({ email: "", password: "" });
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setValues((current) => ({ ...current, [name]: value }));
    setErrors((current) => ({ ...current, [name]: undefined }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setFormError(null);

    const credentials = { email: values.email.trim(), password: values.password };
    const validationErrors = validate(credentials);
    setErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) {
      return;
    }

    setSubmitting(true);
    try {
      await onSubmit(credentials);
    } catch (error) {
      const { fields, form } = toFormErrors(error, FIELDS);
      setErrors(fields);
      setFormError(form);
      setSubmitting(false);
    }
  };

  return (
    <Box component="form" noValidate onSubmit={handleSubmit}>
      <Typography component="h2" variant="h5" sx={{ mb: 3 }}>
        {title}
      </Typography>

      <Stack spacing={2}>
        {formError && <Alert severity="error">{formError}</Alert>}

        <TextField
          name="email"
          type="email"
          label="Электронная почта"
          autoComplete="email"
          value={values.email}
          onChange={handleChange}
          error={Boolean(errors.email)}
          helperText={errors.email}
          autoFocus
          fullWidth
        />
        <TextField
          name="password"
          type="password"
          label="Пароль"
          autoComplete={passwordAutoComplete}
          value={values.password}
          onChange={handleChange}
          error={Boolean(errors.password)}
          helperText={errors.password ?? passwordHelperText}
          fullWidth
        />

        <Button type="submit" variant="contained" size="large" disabled={submitting}>
          {submitLabel}
        </Button>

        {children}
      </Stack>
    </Box>
  );
}
