import { useCallback, useEffect, useRef, useState } from "react";
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
  const [loadedProject, setLoadedProject] = useState(null);
  const requestSequence = useRef(0);
  const [loadError, setLoadError] = useState(null);

  const load = useCallback(async () => {
    const requestId = ++requestSequence.current;
    setLoadedProject(null);
    setLoadError(null);
    try {
      const project = await projectsApi.get(projectId);
      if (requestId === requestSequence.current) {
        setLoadedProject({ requestedId: projectId, project });
      }
    } catch (error) {
      if (requestId === requestSequence.current) {
        setLoadError(error);
      }
    }
  }, [projectId]);

  useEffect(() => {
    load();
    return () => {
      requestSequence.current += 1;
    };
  }, [load]);

  const updateProject = useCallback((updated) => {
    setLoadedProject((current) =>
      current?.project.id === updated.id ? { ...current, project: updated } : current
    );
  }, []);

  // Чужой проект бэкенд тоже отдаёт как NOT_FOUND (F_Auth_7)
  if (loadError?.code === "NOT_FOUND") {
    return <NotFoundPage />;
  }
  if (loadError) {
    return (
      <ErrorState title="Не удалось открыть проект" message={loadError.message} onRetry={load} />
    );
  }
  if (!loadedProject || loadedProject.requestedId !== projectId) {
    return <LoadingState label="Открываем проект" />;
  }

  const project = loadedProject.project;
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

      <Outlet key={project.id} context={{ project, updateProject }} />
    </Box>
  );
}
