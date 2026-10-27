import { Navigate, Outlet, useLocation } from "react-router";

import { paths } from "../../app/paths.js";
import LoadingState from "../../components/LoadingState.jsx";
import { useAuth } from "./AuthProvider.jsx";

// Пускает дальше только вошедшего пользователя. Остальных отправляет на вход,
// запомнив адрес, чтобы после входа вернуть на него
export default function RequireAuth() {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return <LoadingState fullPage />;
  }
  if (status === "anonymous") {
    return <Navigate to={paths.login} replace state={{ from: location }} />;
  }
  return <Outlet />;
}
