// Варианты цели нагрузки по типу. Подгруппа подписывается вместе с группой:
// названия подгрупп разных групп могут совпадать
export function targetOptions({ groups, streams }) {
  return {
    GROUP: groups.map((group) => ({ id: group.id, label: group.name })),
    SUBGROUP: groups.flatMap((group) =>
      group.subgroups.map((subgroup) => ({ id: subgroup.id, label: `${group.name} / ${subgroup.name}` }))
    ),
    STREAM: streams.map((stream) => ({ id: stream.id, label: `Поток ${stream.name}` }))
  };
}

export function targetLabel(options, target) {
  return options[target.type]?.find((option) => option.id === target.id)?.label ?? "—";
}
