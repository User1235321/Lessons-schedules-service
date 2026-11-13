import { TextField } from "@mui/material";

import { resourceApi } from "../api.js";
import { useResourceForm } from "../useResourceForm.js";
import { MAX_NAME_LENGTH, validateName, validateStudentCount } from "../validation.js";
import ResourceFormDialog from "./ResourceFormDialog.jsx";

const total = (subgroups) => subgroups.reduce((sum, subgroup) => sum + subgroup.student_count, 0);

// Группа: название и число студентов (F_Data_10). Подгруппы добавляются отдельно
export default function GroupDialog({ open, item, projectId, onClose, onSaved }) {
  const subgroupsTotal = total(item?.subgroups ?? []);

  const form = useResourceForm({
    open,
    initialValues: { name: item?.name ?? "", student_count: String(item?.student_count ?? "") },
    validate: ({ name, student_count: count }) => {
      const errors = {
        name: validateName(name, "Укажите название группы"),
        student_count: validateStudentCount(count)
      };
      // F_Data_12: подгруппы не могут вместить больше студентов, чем в группе
      if (!errors.student_count && Number(count) < subgroupsTotal) {
        errors.student_count = `Меньше суммы студентов в подгруппах (${subgroupsTotal})`;
      }
      return Object.fromEntries(Object.entries(errors).filter(([, error]) => error));
    },
    onSubmit: async ({ name, student_count: count }) => {
      const api = resourceApi(projectId, "groups");
      const body = { name: name.trim(), student_count: Number(count) };
      onSaved(item ? await api.update(item.id, body) : await api.create(body));
    }
  });

  return (
    <ResourceFormDialog
      open={open}
      title={item ? "Изменить группу" : "Новая группа"}
      submitLabel={item ? "Сохранить" : "Добавить"}
      form={form}
      onClose={onClose}
    >
      <TextField
        label="Название группы"
        value={form.values.name}
        onChange={(event) => form.setValue("name", event.target.value)}
        error={Boolean(form.errors.name)}
        helperText={form.errors.name}
        slotProps={{ htmlInput: { maxLength: MAX_NAME_LENGTH } }}
        autoFocus
        fullWidth
      />
      <TextField
        label="Число студентов"
        value={form.values.student_count}
        onChange={(event) => form.setValue("student_count", event.target.value)}
        error={Boolean(form.errors.student_count)}
        helperText={form.errors.student_count}
        slotProps={{ htmlInput: { inputMode: "numeric" } }}
        fullWidth
      />
    </ResourceFormDialog>
  );
}
