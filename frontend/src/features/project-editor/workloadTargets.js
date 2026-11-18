
const TARGET_FIELDS = {
  GROUP: "group_id",
  SUBGROUP: "subgroup_id",
  STREAM: "stream_id"
};

export function targetFromWorkload(workload) {
  const type = Object.keys(TARGET_FIELDS).find((candidate) => workload?.[TARGET_FIELDS[candidate]]);
  return type ? { type, id: workload[TARGET_FIELDS[type]] } : null;
}

export function workloadTargetFields(type, id) {
  return Object.fromEntries(
    Object.entries(TARGET_FIELDS).map(([candidate, field]) => [field, candidate === type ? id : null])
  );
}
export function targetOptions({ groups, streams }) {
  return {
    GROUP: groups.map((group) => ({ id: group.id, label: group.name })),
    SUBGROUP: groups.flatMap((group) =>
      group.subgroups.map((subgroup) => ({ id: subgroup.id, label: `${group.name} / ${subgroup.name}` }))
    ),
    STREAM: streams.map((stream) => ({ id: stream.id, label: `Поток ${stream.name}` }))
  };
}

export function targetLabel(options, workload) {
  const target = targetFromWorkload(workload);
  return options[target?.type]?.find((option) => option.id === target.id)?.label ?? "—";
}
