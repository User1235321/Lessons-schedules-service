import { Button } from "@mui/material";
import { Link as RouterLink, useParams } from "react-router";

import { paths } from "../../../app/paths.js";
import PlaceholderPage from "../../../components/PlaceholderPage.jsx";

export default function ScheduleViewerPage() {
  const { projectId, scheduleId } = useParams();

  return (
    <PlaceholderPage
      title="Просмотр расписания"
      description={`Расписание ${scheduleId}`}
      planned={[
        "Нечётная и чётная недели (F_Edit_1)",
        "Переключение вариантов TOP-N (F_Edit_3)",
        "Очные и дистанционные занятия (F_Edit_2)"
      ]}
    >
      <Button
        variant="contained"
        component={RouterLink}
        to={paths.scheduleEdit(projectId, scheduleId)}
      >
        Редактировать
      </Button>
    </PlaceholderPage>
  );
}
