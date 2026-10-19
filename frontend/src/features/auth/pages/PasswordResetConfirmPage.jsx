import { Link } from "@mui/material";
import { Link as RouterLink } from "react-router";

import { paths } from "../../../app/paths.js";
import PlaceholderPage from "../../../components/PlaceholderPage.jsx";

export default function PasswordResetConfirmPage() {
  return (
    <PlaceholderPage
      title="Новый пароль"
      planned={["Ввод нового пароля от 6 до 20 символов (F_Auth_6)"]}
    >
      <Link component={RouterLink} to={paths.login}>
        Вернуться ко входу
      </Link>
    </PlaceholderPage>
  );
}
