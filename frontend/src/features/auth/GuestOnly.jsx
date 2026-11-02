import { Navigate, Outlet, useLocation } from "react-router";

import { paths } from "../../app/paths.js";
import LoadingState from "../../components/LoadingState.jsx";
import { useAuth } from "./AuthProvider.jsx";

// Страницы входа и регистрации. Как только пользователь вошёл (после отправки формы
// или уже был в сессии), возвращает его на адрес, запомненный RequireAuth
export default function GuestOnly() {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return <LoadingState />;
  }
  if (status === "authenticated") {
    return <Navigate to={location.state?.from ?? paths.projects} replace />;
  }
  return <Outlet />;
}
