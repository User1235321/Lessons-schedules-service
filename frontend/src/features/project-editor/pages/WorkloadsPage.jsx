import { useOutletContext, useParams } from "react-router";

import ErrorState from "../../../components/ErrorState.jsx";
import LoadingState from "../../../components/LoadingState.jsx";
import ResourceSection from "../components/ResourceSection.jsx";
import WorkloadDialog from "../components/WorkloadDialog.jsx";
import { lessonFormatLabel, lessonTypeLabel } from "../intervals.js";
import { useResourceList } from "../useSubjects.js";
import { targetLabel, targetOptions } from "../workloadTargets.js";

export default function WorkloadsPage() {
  const { projectId } = useParams();
  const { project } = useOutletContext();
  const subjects = useResourceList(projectId, "subjects");
  const groups = useResourceList(projectId, "groups");
  const streams = useResourceList(projectId, "streams");

  const failed = [subjects, groups, streams].find((list) => list.error);
  if (failed) {
    return (
      <ErrorState
        title="Не удалось загрузить исходные данные"
        message={failed.error.message}
        onRetry={() => [subjects, groups, streams].forEach((list) => list.error && list.reload())}
      />
    );
  }
  if (!subjects.items || !groups.items || !streams.items) {
    return <LoadingState label="Загружаем данные" />;
  }

  const targets = targetOptions({ groups: groups.items, streams: streams.items });
  const individualDuration = project.duration_mode?.type === "INDIVIDUAL";
  const projectDuration = project.duration_mode?.duration_minutes ?? null;
  const subjectName = (id) => subjects.items.find((subject) => subject.id === id)?.name ?? "—";

  return (
    <ResourceSection
      title="Учебная нагрузка"
      description="Какие занятия и сколько раз за двухнедельный цикл нужно провести каждой группе, подгруппе или потоку."
      projectId={projectId}
      resource="workloads"
      columns={[
        { label: "Дисциплина", render: (workload) => subjectName(workload.subject_id) },
        {
          label: "Занятие",
          render: (workload) =>
            `${lessonTypeLabel(workload.lesson_type)}, ${lessonFormatLabel(workload.format).toLowerCase()}`
        },
        { label: "Для кого", render: (workload) => targetLabel(targets, workload.target) },
        { label: "За цикл", render: (workload) => workload.occurrences_per_cycle },
        {
          label: "Длительность",
          render: (workload) =>
            individualDuration
              ? workload.duration_minutes
                ? `${workload.duration_minutes} мин`
                : "не задана"
              : `${projectDuration ?? "—"} мин`
        },
        { label: "Преподавателей", render: (workload) => workload.required_teacher_count }
      ]}
      itemLabel={(workload) => `${subjectName(workload.subject_id)}, ${targetLabel(targets, workload.target)}`}
      addLabel="Добавить нагрузку"
      emptyText="Нагрузки пока нет. Добавьте первое занятие."
      deleteText={(workload) =>
        `Нагрузка «${subjectName(workload.subject_id)}» для «${targetLabel(targets, workload.target)}» будет удалена.`
      }
      FormDialog={WorkloadDialog}
      dialogProps={{ subjects: subjects.items, targets, individualDuration, projectDuration }}
    />
  );
}
