import { Button } from "@mui/material";
import { Link as RouterLink, useParams } from "react-router";

import { paths } from "../../../app/paths.js";
import PlaceholderPage from "../../../components/PlaceholderPage.jsx";

export default function SchedulesPage() {
  const { projectId } = useParams();

  return (
    <PlaceholderPage
      title="Расписания"
      planned={["Результаты расчётов проекта", "Загруженные расписания"]}
    >
      {/* Временная ссылка до появления API. */}
      <Button variant="outlined" component={RouterLink} to={paths.schedule(projectId, "demo-1")}>
        Открыть вариант 1
      </Button>
    </PlaceholderPage>
  );
}
