import { Link, Stack } from "@mui/material";
import { Link as RouterLink } from "react-router";

import { paths } from "../../../app/paths.js";
import { useAuth } from "../AuthProvider.jsx";
import CredentialsForm from "../components/CredentialsForm.jsx";
import { collectErrors, validateEmail, validatePassword } from "../validation.js";

const validate = ({ email, password }) =>
  collectErrors({ email: validateEmail(email), password: validatePassword(password) });

export default function LoginPage() {
  const { login } = useAuth();

  return (
    <CredentialsForm
      title="Вход"
      submitLabel="Войти"
      passwordAutoComplete="current-password"
      validate={validate}
      onSubmit={login}
    >
      <Stack spacing={1}>
        <Link component={RouterLink} to={paths.register}>
          Нет аккаунта? Зарегистрироваться
        </Link>
        <Link component={RouterLink} to={paths.passwordReset}>
          Забыли пароль?
        </Link>
      </Stack>
    </CredentialsForm>
  );
}
