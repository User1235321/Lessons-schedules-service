import { useCallback, useEffect, useState } from "react";
import { Box, Breadcrumbs, Button, Link, Stack, Tab, Tabs, Typography } from "@mui/material";
import { Link as RouterLink, Outlet, useLocation, useParams } from "react-router";

import { paths, projectSections } from "../app/paths.js";
import ErrorState from "../components/ErrorState.jsx";
import LoadingState from "../components/LoadingState.jsx";
import { projectsApi } from "../features/projects/api.js";
import NotFoundPage from "../pages/NotFoundPage.jsx";

function useCurrentSection(projectId) {
  const { pathname } = useLocation();
  const prefix = `${paths.project(projectId)}/`;
  const segment = pathname.startsWith(prefix)
    ? pathname.slice(prefix.length).split("/")[0]
    : undefined;

  return projectSections.some((section) => section.path === segment) ? segment : false;
}

export default function ProjectLayout() {
  const { projectId } = useParams();
  const currentSection = useCurrentSection(projectId);
  const [project, setProject] = useState(null);
  const [loadError, setLoadError] = useState(null);

  const load = useCallback(async () => {
    setProject(null);
    setLoadError(null);
    try {
      setProject(await projectsApi.get(projectId));
    } catch (error) {
      setLoadError(error);
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  // Чужой проект бэкенд тоже отдаёт как NOT_FOUND (F_Auth_7)
  if (loadError?.code === "NOT_FOUND") {
    return <NotFoundPage />;
  }
  if (loadError) {
    return (
      <ErrorState title="Не удалось открыть проект" message={loadError.message} onRetry={load} />
    );
  }
  if (!project) {
    return <LoadingState label="Открываем проект" />;
  }

  const projectName = project.name;

  return (
    <Box>
      <Breadcrumbs aria-label="Навигация по разделам" sx={{ mb: 1 }}>
        <Link component={RouterLink} to={paths.projects} underline="hover" color="inherit">
          Мои проекты
        </Link>
        <Typography color="text.primary">{projectName}</Typography>
      </Breadcrumbs>

      <Stack
        direction="row"
        spacing={2}
        sx={{ alignItems: "center", justifyContent: "space-between", mb: 2 }}
      >
        <Typography component="h1" variant="h4">
          {projectName}
        </Typography>
        <Button
          variant="contained"
          component={RouterLink}
          to={paths.projectSection(projectId, "generation")}
        >
          Рассчитать
        </Button>
      </Stack>

      <Box component="nav" aria-label="Разделы проекта" sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Tabs value={currentSection} variant="scrollable" scrollButtons="auto">
          {projectSections.map((section) => (
            <Tab
              key={section.path}
              value={section.path}
              label={section.label}
              component={RouterLink}
              to={paths.projectSection(projectId, section.path)}
            />
          ))}
        </Tabs>
      </Box>

      <Outlet />
    </Box>
  );
}
