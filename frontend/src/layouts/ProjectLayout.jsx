import { Box, Breadcrumbs, Button, Link, Stack, Tab, Tabs, Typography } from "@mui/material";
import { Link as RouterLink, Outlet, useLocation, useParams } from "react-router";

import { paths, projectSections } from "../app/paths.js";

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

  // TODO(projects): загрузить проект через GET /projects/{projectId} и показать его имя.
  const projectName = `Проект ${projectId}`;

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
