import { Link } from "@mui/material";
import { Link as RouterLink } from "react-router";

import { paths } from "../../../app/paths.js";
import PlaceholderPage from "../../../components/PlaceholderPage.jsx";

export default function PasswordResetRequestPage() {
  return (
    <PlaceholderPage
      title="Восстановление пароля"
      planned={["Отправка письма со ссылкой на email (F_Auth_6)"]}
    >
      <Link component={RouterLink} to={paths.login}>
        Вернуться ко входу
      </Link>
    </PlaceholderPage>
  );
}
