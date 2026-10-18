import { Link, Stack } from "@mui/material";
import { Link as RouterLink } from "react-router";

import { paths } from "../../../app/paths.js";
import PlaceholderPage from "../../../components/PlaceholderPage.jsx";

export default function LoginPage() {
  return (
    <PlaceholderPage
      title="Вход"
      planned={["Email и пароль", "Сообщение о неверных данных (F_Auth_5)"]}
    >
      <Stack spacing={1}>
        <Link component={RouterLink} to={paths.register}>
          Нет аккаунта? Зарегистрироваться
        </Link>
        <Link component={RouterLink} to={paths.passwordReset}>
          Забыли пароль?
        </Link>
      </Stack>
    </PlaceholderPage>
  );
}
