import { TextField } from "@mui/material";

import { resourceApi } from "../api.js";
import { useResourceForm } from "../useResourceForm.js";
import { MAX_NAME_LENGTH, validateName } from "../validation.js";
import ResourceFormDialog from "./ResourceFormDialog.jsx";

export default function SubjectDialog({ open, item, projectId, onClose, onSaved }) {
  const form = useResourceForm({
    open,
    initialValues: { name: item?.name ?? "" },
    validate: ({ name }) => {
      const error = validateName(name, "Укажите название дисциплины");
      return error ? { name: error } : {};
    },
    onSubmit: async ({ name }) => {
      const api = resourceApi(projectId, "subjects");
      onSaved(item ? await api.update(item.id, { name: name.trim() }) : await api.create({ name: name.trim() }));
    }
  });

  return (
    <ResourceFormDialog
      open={open}
      title={item ? "Изменить дисциплину" : "Новая дисциплина"}
      submitLabel={item ? "Сохранить" : "Добавить"}
      form={form}
      onClose={onClose}
    >
      <TextField
        label="Название дисциплины"
        value={form.values.name}
        onChange={(event) => form.setValue("name", event.target.value)}
        error={Boolean(form.errors.name)}
        helperText={form.errors.name}
        slotProps={{ htmlInput: { maxLength: MAX_NAME_LENGTH } }}
        autoFocus
        fullWidth
      />
    </ResourceFormDialog>
  );
}
