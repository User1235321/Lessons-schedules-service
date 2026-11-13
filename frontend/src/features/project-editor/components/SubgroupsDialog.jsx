import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  List,
  ListItem,
  ListItemText,
  Stack,
  TextField,
  Typography
} from "@mui/material";

import ConfirmDialog from "../../../components/ConfirmDialog.jsx";
import { resourceApi } from "../api.js";
import { toFormErrors } from "../formErrors.js";
import { MAX_NAME_LENGTH, validateName, validateStudentCount } from "../validation.js";

const total = (subgroups) => subgroups.reduce((sum, subgroup) => sum + subgroup.student_count, 0);
const EMPTY = { name: "", student_count: "" };

// Подгруппы одной группы (F_Data_11, F_Data_13). Сумма студентов в подгруппах не может
// превышать численность группы (F_Data_12). Каждое действие сразу уходит на сервер,
// а список группы обновляется через onChanged
export default function SubgroupsDialog({ open, item: group, projectId, onClose, onChanged }) {
  const api = useMemo(() => resourceApi(projectId, "subgroups"), [projectId]);
  const [editing, setEditing] = useState(null);
  const [values, setValues] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [deletion, setDeletion] = useState({ open: false, subgroup: null });

  const subgroups = group?.subgroups ?? [];
  const free = group ? group.student_count - total(subgroups.filter((s) => s.id !== editing?.id)) : 0;

  const resetForm = () => {
    setEditing(null);
    setValues(EMPTY);
    setErrors({});
    setFormError(null);
  };

  useEffect(() => {
    if (open) {
      resetForm();
      setBusy(false);
    }
  }, [open]);

  const startEditing = (subgroup) => {
    setEditing(subgroup);
    setValues({ name: subgroup.name, student_count: String(subgroup.student_count) });
    setErrors({});
    setFormError(null);
  };

  const setValue = (name, value) => {
    setValues((current) => ({ ...current, [name]: value }));
    setErrors((current) => ({ ...current, [name]: undefined }));
  };

  const replaceSubgroups = (next) => onChanged({ ...group, subgroups: next });

  const handleSubmit = async (event) => {
    event.preventDefault();
    setFormError(null);

    const found = {
      name: validateName(values.name, "Укажите название подгруппы"),
      student_count: validateStudentCount(values.student_count)
    };
    if (!found.student_count && Number(values.student_count) > free) {
      found.student_count = `Сумма студентов в подгруппах не должна превышать численность группы (свободно: ${free})`;
    }
    const failed = Object.fromEntries(Object.entries(found).filter(([, error]) => error));
    setErrors(failed);
    if (Object.keys(failed).length > 0) {
      return;
    }

    const body = { name: values.name.trim(), student_count: Number(values.student_count) };
    setBusy(true);
    try {
      const saved = editing
        ? await api.update(editing.id, body)
        : await api.create({ group_id: group.id, ...body });
      const entry = { id: saved.id, name: saved.name, student_count: saved.student_count };
      replaceSubgroups(
        editing ? subgroups.map((s) => (s.id === entry.id ? entry : s)) : [...subgroups, entry]
      );
      resetForm();
    } catch (error) {
      const { fields, form } = toFormErrors(error);
      setErrors(fields);
      setFormError(form);
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    const { subgroup } = deletion;
    try {
      await api.remove(subgroup.id);
    } catch (error) {
      if (error.code !== "NOT_FOUND") {
        throw error;
      }
    }
    replaceSubgroups(subgroups.filter((s) => s.id !== subgroup.id));
    if (editing?.id === subgroup.id) {
      resetForm();
    }
  };

  return (
    <Dialog open={open} onClose={busy ? undefined : onClose} fullWidth maxWidth="sm">
      <DialogTitle>Подгруппы: {group?.name}</DialogTitle>
      <DialogContent>
        <Typography color="text.secondary" sx={{ mb: 1 }}>
          Распределено {total(subgroups)} из {group?.student_count} студентов
        </Typography>

        {subgroups.length === 0 ? (
          <Typography sx={{ mb: 2 }}>Подгрупп пока нет.</Typography>
        ) : (
          <List aria-label="Подгруппы" dense>
            {subgroups.map((subgroup) => (
              <ListItem
                key={subgroup.id}
                disableGutters
                secondaryAction={
                  <>
                    <Button
                      size="small"
                      aria-label={`Изменить подгруппу: ${subgroup.name}`}
                      onClick={() => startEditing(subgroup)}
                    >
                      Изменить
                    </Button>
                    <Button
                      size="small"
                      color="error"
                      aria-label={`Удалить подгруппу: ${subgroup.name}`}
                      onClick={() => setDeletion({ open: true, subgroup })}
                    >
                      Удалить
                    </Button>
                  </>
                }
              >
                <ListItemText primary={subgroup.name} secondary={`${subgroup.student_count} студентов`} />
              </ListItem>
            ))}
          </List>
        )}

        <form noValidate onSubmit={handleSubmit}>
          <Stack spacing={2} sx={{ pt: 1 }}>
            {formError && <Alert severity="error">{formError}</Alert>}
            <Typography variant="subtitle2">
              {editing ? `Изменить подгруппу «${editing.name}»` : "Новая подгруппа"}
            </Typography>
            <TextField
              label="Название подгруппы"
              value={values.name}
              onChange={(event) => setValue("name", event.target.value)}
              error={Boolean(errors.name)}
              helperText={errors.name}
              slotProps={{ htmlInput: { maxLength: MAX_NAME_LENGTH } }}
              fullWidth
            />
            <TextField
              label="Число студентов в подгруппе"
              value={values.student_count}
              onChange={(event) => setValue("student_count", event.target.value)}
              error={Boolean(errors.student_count)}
              helperText={errors.student_count}
              slotProps={{ htmlInput: { inputMode: "numeric" } }}
              fullWidth
            />
            <Stack direction="row" spacing={1}>
              <Button type="submit" variant="contained" disabled={busy}>
                {editing ? "Сохранить подгруппу" : "Добавить подгруппу"}
              </Button>
              {editing && (
                <Button onClick={resetForm} disabled={busy}>
                  Отменить изменение
                </Button>
              )}
            </Stack>
          </Stack>
        </form>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={busy}>
          Закрыть
        </Button>
      </DialogActions>

      <ConfirmDialog
        open={deletion.open}
        title="Удалить подгруппу?"
        onConfirm={handleDelete}
        onClose={() => setDeletion((current) => ({ ...current, open: false }))}
      >
        {deletion.subgroup && `Подгруппа «${deletion.subgroup.name}» будет удалена.`}
      </ConfirmDialog>
    </Dialog>
  );
}
