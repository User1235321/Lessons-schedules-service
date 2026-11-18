import { useParams } from "react-router";

import ErrorState from "../../../components/ErrorState.jsx";
import LoadingState from "../../../components/LoadingState.jsx";
import ResourceSection from "../components/ResourceSection.jsx";
import TeacherDialog from "../components/TeacherDialog.jsx";
import { formatInterval, lessonTypeLabel } from "../intervals.js";
import { useSubjects } from "../useSubjects.js";

export default function TeachersPage() {
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
      title="Преподаватели"
      description="Кого и что ведёт преподаватель, когда он доступен и когда ему удобнее."
      projectId={projectId}
      resource="teachers"
      columns={[
        { label: "ФИО", render: (teacher) => teacher.full_name },
        {
          label: "Что ведёт",
          render: (teacher) =>
            teacher.capabilities
              .map((item) => `${subjectName(item.subject_id)} (${lessonTypeLabel(item.lesson_type).toLowerCase()})`)
              .join(", ")
        },
        {
          label: "Доступность",
          render: (teacher) => teacher.availability.map(formatInterval).join("; ")
        }
      ]}
      itemLabel={(teacher) => teacher.full_name}
      addLabel="Добавить преподавателя"
      emptyText="Преподавателей пока нет. Добавьте первого."
      deleteText={(teacher) => `Преподаватель «${teacher.full_name}» будет удалён.`}
      FormDialog={TeacherDialog}
      dialogProps={{ subjects }}
    />
  );
}
