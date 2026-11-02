import { useState } from "react";
import {
  Alert,
  AlertTitle,
  AppBar,
  Box,
  Button,
  Container,
  LinearProgress,
  Menu,
  MenuItem,
  Toolbar,
  Typography
} from "@mui/material";
import { Link as RouterLink, Outlet, useNavigation } from "react-router";

import { paths } from "../app/paths.js";
import { useAuth } from "../features/auth/AuthProvider.jsx";

export default function AppLayout() {
  const navigation = useNavigation();
  const { logout } = useAuth();
  const [menuAnchor, setMenuAnchor] = useState(null);
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState(null);

  const closeMenu = () => setMenuAnchor(null);

  // После выхода RequireAuth сам отправит на страницу входа. Если сервер не подтвердил выход,
  // пользователь остаётся в системе и может повторить попытку
  const handleLogout = async () => {
    closeMenu();
    setLoggingOut(true);
    try {
      await logout();
    } catch (error) {
      setLogoutError(error);
      setLoggingOut(false);
    }
  };

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "grey.50" }}>
      <AppBar position="sticky" elevation={1}>
        <Toolbar>
          <Typography
            component={RouterLink}
            to={paths.projects}
            variant="h6"
            sx={{ color: "inherit", textDecoration: "none", flexGrow: 1 }}
          >
            Расписание
          </Typography>

          <Button color="inherit" component={RouterLink} to={paths.projects}>
            Мои проекты
          </Button>
          <Button
            color="inherit"
            aria-haspopup="menu"
            aria-controls={menuAnchor ? "profile-menu" : undefined}
            aria-expanded={menuAnchor ? "true" : undefined}
            onClick={(event) => setMenuAnchor(event.currentTarget)}
          >
            Профиль
          </Button>
          <Menu
            id="profile-menu"
            anchorEl={menuAnchor}
            open={Boolean(menuAnchor)}
            onClose={closeMenu}
          >
            <MenuItem onClick={handleLogout} disabled={loggingOut}>
              Выйти
            </MenuItem>
          </Menu>
        </Toolbar>
        {navigation.state !== "idle" && (
          <LinearProgress
            aria-label="Загрузка страницы"
            sx={{ position: "absolute", left: 0, right: 0, bottom: 0 }}
          />
        )}
      </AppBar>

      <Container component="main" maxWidth="lg" sx={{ py: 3 }}>
        {logoutError && (
          <Alert
            severity="error"
            sx={{ mb: 3 }}
            action={
              <Button color="inherit" size="small" onClick={handleLogout} disabled={loggingOut}>
                {loggingOut ? "Выходим…" : "Повторить"}
              </Button>
            }
          >
            <AlertTitle>Не удалось выйти</AlertTitle>
            Сервер не подтвердил завершение сессии, поэтому вы всё ещё в системе.{" "}
            {logoutError.message}
          </Alert>
        )}
        <Outlet />
      </Container>
    </Box>
  );
}
