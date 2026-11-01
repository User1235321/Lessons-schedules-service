import { useCallback, useEffect, useState } from "react";
import {
  Box,
  Button,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Paper,
  Stack,
  Typography
} from "@mui/material";
import { Link as RouterLink, useNavigate } from "react-router";

import { paths } from "../../../app/paths.js";
import ErrorState from "../../../components/ErrorState.jsx";
import LoadingState from "../../../components/LoadingState.jsx";
import { projectsApi } from "../api.js";
import CreateProjectDialog from "../components/CreateProjectDialog.jsx";

const formatDate = (value) => new Date(value).toLocaleDateString("ru-RU");

export default function ProjectsPage() {
  const [projects, setProjects] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [creating, setCreating] = useState(false);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setLoadError(null);
    setProjects(null);
    try {
      setProjects(await projectsApi.list());
    } catch (error) {
      setLoadError(error);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <Box>
      <Stack
        direction="row"
        spacing={2}
        sx={{ alignItems: "center", justifyContent: "space-between", mb: 3 }}
      >
        <Typography component="h1" variant="h4">
          Мои проекты
        </Typography>
        <Button variant="contained" onClick={() => setCreating(true)}>
          Создать проект
        </Button>
      </Stack>

      {loadError ? (
        <ErrorState
          title="Не удалось загрузить проекты"
          message={loadError.message}
          onRetry={load}
        />
      ) : projects === null ? (
        <LoadingState label="Загружаем проекты" />
      ) : projects.length === 0 ? (
        <Typography color="text.secondary">
          Проектов пока нет. Создайте первый, чтобы начать составлять расписание.
        </Typography>
      ) : (
        <Paper variant="outlined">
          <List aria-label="Проекты" disablePadding>
            {projects.map((project) => (
              <ListItem key={project.id} divider disablePadding>
                <ListItemButton component={RouterLink} to={paths.project(project.id)}>
                  <ListItemText
                    primary={project.name}
                    secondary={`Изменён ${formatDate(project.updated_at)}`}
                  />
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        </Paper>
      )}

      <CreateProjectDialog
        open={creating}
        onClose={() => setCreating(false)}
        // Новый проект сразу открывается: дальше пользователь заполняет его данные
        onCreated={(project) => navigate(paths.project(project.id))}
      />
    </Box>
  );
}
