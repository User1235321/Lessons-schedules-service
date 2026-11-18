import { useParams } from "react-router";

import ErrorState from "../../../components/ErrorState.jsx";
import LoadingState from "../../../components/LoadingState.jsx";
import ResourceSection from "../components/ResourceSection.jsx";
import StreamDialog from "../components/StreamDialog.jsx";
import { useResourceList } from "../useSubjects.js";

export default function StreamsPage() {
  const { projectId } = useParams();
  const { items: groups, error, reload } = useResourceList(projectId, "groups");

  if (error) {
    return <ErrorState title="Не удалось загрузить группы" message={error.message} onRetry={reload} />;
  }
  if (!groups) {
    return <LoadingState label="Загружаем данные" />;
  }

  const streamGroups = (stream) =>
    stream.group_ids.map((id) => groups.find((group) => group.id === id)).filter(Boolean);

  return (
    <ResourceSection
      title="Потоки"
      description="Группы, которые слушают занятия вместе. Потоки собираются вручную."
      projectId={projectId}
      resource="streams"
      columns={[
        { label: "Поток", render: (stream) => stream.name },
        {
          label: "Группы",
          render: (stream) =>
            streamGroups(stream)
              .map((group) => group.name)
              .join(", ") || "—"
        },
        {
          label: "Студентов",
          render: (stream) => streamGroups(stream).reduce((sum, group) => sum + group.student_count, 0)
        }
      ]}
      itemLabel={(stream) => stream.name}
      addLabel="Добавить поток"
      emptyText="Потоков пока нет. Добавьте первый."
      deleteText={(stream) =>
        `Поток «${stream.name}» будет удалён. Если он используется в нагрузке, сервер откажет.`
      }
      FormDialog={StreamDialog}
      dialogProps={{ groups }}
    />
  );
}
