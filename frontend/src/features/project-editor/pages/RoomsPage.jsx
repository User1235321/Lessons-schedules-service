import { useParams } from "react-router";

import ErrorState from "../../../components/ErrorState.jsx";
import LoadingState from "../../../components/LoadingState.jsx";
import ResourceSection from "../components/ResourceSection.jsx";
import RoomDialog from "../components/RoomDialog.jsx";
import { formatInterval, lessonTypeLabel, roomTypeLabel } from "../intervals.js";
import { useSubjects } from "../useSubjects.js";

export default function RoomsPage() {
  const { projectId } = useParams();
  const { subjects, error, reload } = useSubjects(projectId);

  if (error) {
    return (
      <ErrorState title="Не удалось загрузить дисциплины" message={error.message} onRetry={reload} />
    );
  }
  if (!subjects) {
    return <LoadingState label="Загружаем данные" />;
  }

  const subjectName = (id) => subjects.find((subject) => subject.id === id)?.name ?? "—";

  return (
    <ResourceSection
      title="Аудитории"
      description="Где проходят занятия: вместимость, тип, допустимые дисциплины и доступное время."
      projectId={projectId}
      resource="rooms"
      columns={[
        { label: "Аудитория", render: (room) => room.name },
        { label: "Мест", render: (room) => room.capacity },
        { label: "Тип", render: (room) => roomTypeLabel(room.type) },
        {
          label: "Допустимые занятия",
          render: (room) =>
            room.capabilities
              .map((item) => `${subjectName(item.subject_id)} (${lessonTypeLabel(item.lesson_type).toLowerCase()})`)
              .join(", ") || "—"
        },
        {
          label: "Доступность",
          render: (room) => room.availability.map(formatInterval).join("; ")
        }
      ]}
      itemLabel={(room) => room.name}
      addLabel="Добавить аудиторию"
      emptyText="Аудиторий пока нет. Добавьте первую."
      deleteText={(room) => `Аудитория «${room.name}» будет удалена.`}
      FormDialog={RoomDialog}
      dialogProps={{ subjects }}
    />
  );
}
