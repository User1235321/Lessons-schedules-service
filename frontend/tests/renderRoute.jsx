import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";

import AppProviders from "../src/app/AppProviders.jsx";
import { routes } from "../src/app/routes.jsx";

// Рендерит приложение целиком с заданного URL на memory-роутере.
export function renderRoute(path, routeConfig = routes) {
  const router = createMemoryRouter(routeConfig, { initialEntries: [path] });
  const user = userEvent.setup();

  render(
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  );

  return { router, user };
}

// Страницы грузятся лениво, поэтому даём запас по времени на первый import().
export function findHeading(name) {
  return screen.findByRole("heading", { name }, { timeout: 3000 });
}
