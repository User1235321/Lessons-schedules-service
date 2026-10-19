import { Button } from "@mui/material";
import { Link as RouterLink, useParams } from "react-router";

import { paths } from "../../../app/paths.js";
import PlaceholderPage from "../../../components/PlaceholderPage.jsx";

export default function ScheduleEditorPage() {
  const { projectId, scheduleId } = useParams();

  return (
    <PlaceholderPage
      title="Редактирование расписания"
      description={`Расписание ${scheduleId}`}
      planned={[
        "Изменение дня, времени, формата, аудитории и преподавателей (F_Edit_4)",
        "Отображение конфликтов с причинами (F_Edit_5)",
        "Автоматическая корректировка (F_Edit_7)"
      ]}
    >
      <Button component={RouterLink} to={paths.schedule(projectId, scheduleId)}>
        Вернуться к просмотру
      </Button>
    </PlaceholderPage>
  );
}
