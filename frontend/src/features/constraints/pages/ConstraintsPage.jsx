import { useParams } from "react-router";

import ErrorState from "../../../components/ErrorState.jsx";
import LoadingState from "../../../components/LoadingState.jsx";
import ResourceSection from "../../project-editor/components/ResourceSection.jsx";
import { useResourceList } from "../../project-editor/useSubjects.js";
import ConstraintDialog from "../components/ConstraintDialog.jsx";
import {
  constraintParametersLabel,
  constraintScopeLabel,
  constraintTypeLabel,
  createScopeOptions
} from "../constraintModel.js";

function ConstraintsEditor({ projectId }) {
  const groups = useResourceList(projectId, "groups");
  const streams = useResourceList(projectId, "streams");
  const workloads = useResourceList(projectId, "workloads");
  const subjects = useResourceList(projectId, "subjects");
  const resources = [groups, streams, workloads, subjects];
  const failed = resources.find((resource) => resource.error);

  if (failed) {
    return (
      <ErrorState
        title="Не удалось загрузить исходные данные"
        message={failed.error.message}
        onRetry={() => resources.forEach((resource) => resource.error && resource.reload())}
      />
    );
  }
  if (resources.some((resource) => resource.items === null)) {
    return <LoadingState label="Загружаем данные" />;
  }

  const options = createScopeOptions({
    groups: groups.items,
    streams: streams.items,
    workloads: workloads.items,
    subjects: subjects.items
  });

  return (
    <ResourceSection
      title="Ограничения"
      description="Дополнительные обязательные ограничения расписания."
      projectId={projectId}
      resource="constraints"
      columns={[
        { label: "Тип", render: (item) => constraintTypeLabel(item.constraint_type) },
        { label: "Для кого", render: (item) => constraintScopeLabel(item, options) },
        { label: "Условия", render: (item) => constraintParametersLabel(item, options) }
      ]}
      itemLabel={(item) => constraintTypeLabel(item.constraint_type)}
      addLabel="Добавить ограничение"
      emptyText="Ограничений пока нет. Добавьте первое ограничение."
      deleteText={(item) => `Ограничение «${constraintTypeLabel(item.constraint_type)}» будет удалено.`}
      FormDialog={ConstraintDialog}
      dialogProps={{ options }}
    />
  );
}

export default function ConstraintsPage() {
  const { projectId } = useParams();
  return <ConstraintsEditor key={projectId} projectId={projectId} />;
}
