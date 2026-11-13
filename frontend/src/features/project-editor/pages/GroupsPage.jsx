import { useParams } from "react-router";

import GroupDialog from "../components/GroupDialog.jsx";
import ResourceSection from "../components/ResourceSection.jsx";
import SubgroupsDialog from "../components/SubgroupsDialog.jsx";

export default function GroupsPage() {
  const { projectId } = useParams();

  return (
    <ResourceSection
      title="Группы и подгруппы"
      description="Учебные группы и их разбиение на подгруппы."
      projectId={projectId}
      resource="groups"
      columns={[
        { label: "Группа", render: (group) => group.name },
        { label: "Студентов", render: (group) => group.student_count },
        {
          label: "Подгруппы",
          render: (group) =>
            group.subgroups.map((subgroup) => `${subgroup.name} (${subgroup.student_count})`).join(", ") ||
            "—"
        }
      ]}
      itemLabel={(group) => group.name}
      addLabel="Добавить группу"
      emptyText="Групп пока нет. Добавьте первую."
      deleteText={(group) =>
        `Группа «${group.name}» будет удалена вместе с подгруппами. Если она используется в нагрузке или потоке, сервер откажет.`
      }
      FormDialog={GroupDialog}
      rowActions={[{ label: "Подгруппы", Dialog: SubgroupsDialog }]}
    />
  );
}
