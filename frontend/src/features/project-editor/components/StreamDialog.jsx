import {
  Alert,
  Box,
  Checkbox,
  FormControlLabel,
  FormGroup,
  FormHelperText,
  Link,
  TextField,
  Typography
} from "@mui/material";
import { Link as RouterLink } from "react-router";

import { paths } from "../../../app/paths.js";
import { resourceApi } from "../api.js";
import { useResourceForm } from "../useResourceForm.js";
import { MAX_NAME_LENGTH, validateName } from "../validation.js";
import ResourceFormDialog from "./ResourceFormDialog.jsx";

// Поток: группы, которые слушают занятия вместе. Собирается только вручную (F_Data_14, F_Data_15).
// Нужна хотя бы одна группа, поток из одной группы допустим
export default function StreamDialog({ open, item, projectId, groups, onClose, onSaved }) {
  const form = useResourceForm({
    open,
    initialValues: { name: item?.name ?? "", group_ids: [...(item?.group_ids ?? [])] },
    validate: ({ name, group_ids: groupIds }) => {
      const errors = {
        name: validateName(name, "Укажите название потока"),
        group_ids: groupIds.length === 0 ? "Выберите хотя бы одну группу" : null
      };
      return Object.fromEntries(Object.entries(errors).filter(([, error]) => error));
    },
    onSubmit: async ({ name, group_ids: groupIds }) => {
      const api = resourceApi(projectId, "streams");
      const body = { name: name.trim(), group_ids: groupIds };
      onSaved(item ? await api.update(item.id, body) : await api.create(body));
    }
  });

  const selected = form.values.group_ids;
  const toggle = (groupId) =>
    form.setValue(
      "group_ids",
      selected.includes(groupId) ? selected.filter((id) => id !== groupId) : [...selected, groupId]
    );

  return (
    <ResourceFormDialog
      open={open}
      title={item ? "Изменить поток" : "Новый поток"}
      submitLabel={item ? "Сохранить" : "Добавить"}
      form={form}
      onClose={onClose}
    >
      <TextField
        label="Название потока"
        value={form.values.name}
        onChange={(event) => form.setValue("name", event.target.value)}
        error={Boolean(form.errors.name)}
        helperText={form.errors.name}
        slotProps={{ htmlInput: { maxLength: MAX_NAME_LENGTH } }}
        autoFocus
        fullWidth
      />

      <Box component="fieldset" sx={{ border: 0, p: 0, m: 0 }}>
        <Typography component="legend" variant="subtitle2" sx={{ mb: 0.5 }}>
          Группы потока
        </Typography>
        {groups.length === 0 ? (
          <Alert severity="warning">
            Сначала добавьте группы в разделе{" "}
            <Link component={RouterLink} to={paths.projectSection(projectId, "groups")}>
              «Группы»
            </Link>
            .
          </Alert>
        ) : (
          <FormGroup>
            {groups.map((group) => (
              <FormControlLabel
                key={group.id}
                control={
                  <Checkbox checked={selected.includes(group.id)} onChange={() => toggle(group.id)} />
                }
                label={`${group.name} (${group.student_count})`}
              />
            ))}
          </FormGroup>
        )}
        {form.errors.group_ids && <FormHelperText error>{form.errors.group_ids}</FormHelperText>}
      </Box>
    </ResourceFormDialog>
  );
}
