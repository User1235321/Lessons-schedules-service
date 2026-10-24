import { Link } from "@mui/material";
import { Link as RouterLink } from "react-router";

import { paths } from "../../../app/paths.js";
import { useAuth } from "../AuthProvider.jsx";
import CredentialsForm from "../components/CredentialsForm.jsx";
import {
  collectErrors,
  MAX_PASSWORD_LENGTH,
  MIN_PASSWORD_LENGTH,
  validateEmail,
  validateNewPassword
} from "../validation.js";

const validate = ({ email, password }) =>
  collectErrors({ email: validateEmail(email), password: validateNewPassword(password) });

export default function RegisterPage() {
  const { register } = useAuth();

  return (
    <CredentialsForm
      title="Регистрация"
      submitLabel="Зарегистрироваться"
      passwordAutoComplete="new-password"
      passwordHelperText={`От ${MIN_PASSWORD_LENGTH} до ${MAX_PASSWORD_LENGTH} символов`}
      validate={validate}
      onSubmit={register}
    >
      <Link component={RouterLink} to={paths.login}>
        Уже есть аккаунт? Войти
      </Link>
    </CredentialsForm>
  );
}
