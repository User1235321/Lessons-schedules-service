import { Navigate } from "react-router";

import LoadingState from "../components/LoadingState.jsx";
import RouteErrorBoundary from "../components/RouteErrorBoundary.jsx";
import RequireAuth from "../features/auth/RequireAuth.jsx";
import AppLayout from "../layouts/AppLayout.jsx";
import AuthLayout from "../layouts/AuthLayout.jsx";
import ProjectLayout from "../layouts/ProjectLayout.jsx";
import NotFoundPage from "../pages/NotFoundPage.jsx";
import { DEFAULT_PROJECT_SECTION, paths } from "./paths.js";

// Страницы грузятся лениво: каждая функциональная область попадает в свой chunk,
// а пока chunk загружается, в AppLayout показывается полоса прогресса.
const page = (load) => () => load().then((module) => ({ Component: module.default }));

export const routes = [
  {
    path: paths.home,
    errorElement: <RouteErrorBoundary fullPage />,
    HydrateFallback: () => <LoadingState fullPage />,
    children: [
      { index: true, element: <Navigate to={paths.projects} replace /> },

      {
        Component: AuthLayout,
        children: [
          {
            errorElement: <RouteErrorBoundary />,
            children: [
              {
                path: paths.login,
                lazy: page(() => import("../features/auth/pages/LoginPage.jsx"))
              },
              {
                path: paths.register,
                lazy: page(() => import("../features/auth/pages/RegisterPage.jsx"))
              },
              {
                path: paths.passwordReset,
                lazy: page(() =>
                  import("../features/auth/pages/PasswordResetRequestPage.jsx")
                )
              },
              {
                path: paths.passwordResetConfirm,
                lazy: page(() =>
                  import("../features/auth/pages/PasswordResetConfirmPage.jsx")
                )
              }
            ]
          }
        ]
      },

      {
        Component: RequireAuth,
        children: [
          {
            Component: AppLayout,
            children: [
              {
                errorElement: <RouteErrorBoundary />,
                children: [
                  {
                    path: paths.projects,
                    lazy: page(() =>
                      import("../features/projects/pages/ProjectsPage.jsx")
                    )
                  },
                  {
                    path: "projects/:projectId",
                    Component: ProjectLayout,
                    children: [
                      {
                        errorElement: <RouteErrorBoundary />,
                        children: [
                          {
                            index: true,
                            element: <Navigate to={DEFAULT_PROJECT_SECTION} replace />
                          },
                          {
                            path: "subjects",
                            lazy: page(() =>
                              import("../features/project-editor/pages/SubjectsPage.jsx")
                            )
                          },
                          {
                            path: "teachers",
                            lazy: page(() =>
                              import("../features/project-editor/pages/TeachersPage.jsx")
                            )
                          },
                          {
                            path: "rooms",
                            lazy: page(() =>
                              import("../features/project-editor/pages/RoomsPage.jsx")
                            )
                          },
                          {
                            path: "groups",
                            lazy: page(() =>
                              import("../features/project-editor/pages/GroupsPage.jsx")
                            )
                          },
                          {
                            path: "streams",
                            lazy: page(() =>
                              import("../features/project-editor/pages/StreamsPage.jsx")
                            )
                          },
                          {
                            path: "workloads",
                            lazy: page(() =>
                              import("../features/project-editor/pages/WorkloadsPage.jsx")
                            )
                          },
                          {
                            path: "settings",
                            lazy: page(() =>
                              import("../features/project-editor/pages/ProjectSettingsPage.jsx")
                            )
                          },
                          {
                            path: "constraints",
                            lazy: page(() =>
                              import("../features/constraints/pages/ConstraintsPage.jsx")
                            )
                          },
                          {
                            path: "generation",
                            lazy: page(() =>
                              import("../features/generation/pages/GenerationPage.jsx")
                            )
                          },
                          {
                            path: "schedules",
                            lazy: page(() =>
                              import("../features/schedule-viewer/pages/SchedulesPage.jsx")
                            )
                          },
                          {
                            path: "schedules/:scheduleId",
                            lazy: page(() =>
                              import("../features/schedule-viewer/pages/ScheduleViewerPage.jsx")
                            )
                          },
                          {
                            path: "schedules/:scheduleId/edit",
                            lazy: page(() =>
                              import("../features/schedule-editor/pages/ScheduleEditorPage.jsx")
                            )
                          },
                          {
                            path: "files",
                            lazy: page(() =>
                              import("../features/import-export/pages/FilesPage.jsx")
                            )
                          }
                        ]
                      }
                    ]
                  },
                  { path: "*", Component: NotFoundPage }
                ]
              }
            ]
          }
        ]
      }
    ]
  }
];
