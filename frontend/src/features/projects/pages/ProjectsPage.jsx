import { Button, Stack } from "@mui/material";
import { Link as RouterLink } from "react-router";

import { paths } from "../../../app/paths.js";
import PlaceholderPage from "../../../components/PlaceholderPage.jsx";

export default function ProjectsPage() {
  return (
    <PlaceholderPage
      title="Мои проекты"
      planned={[
        "Список проектов пользователя",
        "Создание проекта с обязательным именем (F_Project_1)",
        "Открытие и удаление проекта (F_Project_2)"
      ]}
    >
      <Stack direction="row" spacing={1}>
        {/* Временная ссылка, чтобы можно было пройти по разделам проекта до появления API. */}
        <Button variant="outlined" component={RouterLink} to={paths.project("demo")}>
          Открыть демо-проект
        </Button>
        <Button variant="contained" disabled>
          Создать проект
        </Button>
      </Stack>
    </PlaceholderPage>
  );
}
