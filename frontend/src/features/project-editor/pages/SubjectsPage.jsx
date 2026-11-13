import { useParams } from "react-router";

import ResourceSection from "../components/ResourceSection.jsx";
import SubjectDialog from "../components/SubjectDialog.jsx";

export default function SubjectsPage() {
  const { projectId } = useParams();

  return (
    <ResourceSection
      title="Дисциплины"
      description="Справочник дисциплин: нужен для возможностей преподавателей, аудиторий и учебной нагрузки."
      projectId={projectId}
      resource="subjects"
      columns={[{ label: "Название", render: (subject) => subject.name }]}
      itemLabel={(subject) => subject.name}
      addLabel="Добавить дисциплину"
      emptyText="Дисциплин пока нет. Добавьте первую."
      deleteText={(subject) =>
        `Дисциплина «${subject.name}» будет удалена. Если она уже используется, сервер откажет в удалении.`
      }
      FormDialog={SubjectDialog}
    />
  );
}
