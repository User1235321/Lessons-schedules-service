import { Link } from "@mui/material";
import { Link as RouterLink } from "react-router";

import { paths } from "../../../app/paths.js";
import PlaceholderPage from "../../../components/PlaceholderPage.jsx";

export default function RegisterPage() {
  return (
    <PlaceholderPage
      title="Регистрация"
      planned={["Email и пароль от 6 до 20 символов (F_Auth_2)", "Ошибка при занятом email (F_Auth_3)"]}
    >
      <Link component={RouterLink} to={paths.login}>
        Уже есть аккаунт? Войти
      </Link>
    </PlaceholderPage>
  );
}
