import { useState } from "react";
import {
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
import { Link as RouterLink, Outlet, useNavigate, useNavigation } from "react-router";

import { paths } from "../app/paths.js";

export default function AppLayout() {
  const navigation = useNavigation();
  const navigate = useNavigate();
  const [menuAnchor, setMenuAnchor] = useState(null);

  const closeMenu = () => setMenuAnchor(null);

  const handleLogout = () => {
    closeMenu();
    // TODO(auth): вызвать POST /auth/logout и очистить токены.
    navigate(paths.login);
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
            <MenuItem onClick={handleLogout}>Выйти</MenuItem>
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
        <Outlet />
      </Container>
    </Box>
  );
}
