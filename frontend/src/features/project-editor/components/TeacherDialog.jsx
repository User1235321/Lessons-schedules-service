import { Alert, Link, TextField } from "@mui/material";
import { Link as RouterLink } from "react-router";

import { paths } from "../../../app/paths.js";
import { resourceApi } from "../api.js";
import { validateCapabilities, validateIntervals } from "../intervals.js";
import { useResourceForm } from "../useResourceForm.js";
import { MAX_NAME_LENGTH, validateName } from "../validation.js";
import CapabilitiesField from "./CapabilitiesField.jsx";
import IntervalsField from "./IntervalsField.jsx";
import ResourceFormDialog from "./ResourceFormDialog.jsx";

const copy = (items) => items.map((item) => ({ ...item }));

// Преподаватель: ФИО, пары «дисциплина + тип занятия» и доступность обязательны (F_Data_4),
// предпочтительное время необязательно
export default function TeacherDialog({ open, item, projectId, subjects, onClose, onSaved }) {
  const form = useResourceForm({
    open,
    initialValues: {
      full_name: item?.full_name ?? "",
      capabilities: copy(item?.capabilities ?? []),
      availability: copy(item?.availability ?? []),
      preferences: copy(item?.preferences ?? [])
    },
    validate: (values) => {
      const errors = {
        full_name: validateName(values.full_name, "Укажите ФИО преподавателя"),
        capabilities: validateCapabilities(values.capabilities, { required: true }),
        availability: validateIntervals(values.availability, { required: true }),
        preferences: validateIntervals(values.preferences, { required: false })
      };
      return Object.fromEntries(Object.entries(errors).filter(([, error]) => error));
    },
    onSubmit: async (values) => {
      const api = resourceApi(projectId, "teachers");
      const body = { ...values, full_name: values.full_name.trim() };
      onSaved(item ? await api.update(item.id, body) : await api.create(body));
    }
  });

  return (
    <ResourceFormDialog
      open={open}
      title={item ? "Изменить преподавателя" : "Новый преподаватель"}
      submitLabel={item ? "Сохранить" : "Добавить"}
      form={form}
      onClose={onClose}
      maxWidth="md"
    >
      <TextField
        label="ФИО"
        value={form.values.full_name}
        onChange={(event) => form.setValue("full_name", event.target.value)}
        error={Boolean(form.errors.full_name)}
        helperText={form.errors.full_name}
        slotProps={{ htmlInput: { maxLength: MAX_NAME_LENGTH } }}
        autoFocus
        fullWidth
      />

      {subjects.length === 0 && (
        <Alert severity="warning">
          Сначала добавьте дисциплины в разделе{" "}
          <Link component={RouterLink} to={paths.projectSection(projectId, "subjects")}>
            «Дисциплины»
          </Link>
          : без них нельзя указать, что ведёт преподаватель.
        </Alert>
      )}
      <CapabilitiesField
        label="Что ведёт"
        hint="Дисциплина и тип занятия, которые преподаватель может проводить."
        subjects={subjects}
        value={form.values.capabilities}
        onChange={(next) => form.setValue("capabilities", next)}
        error={form.errors.capabilities}
      />
      <IntervalsField
        label="Доступность"
        hint="Когда преподаватель может проводить занятия."
        value={form.values.availability}
        onChange={(next) => form.setValue("availability", next)}
        error={form.errors.availability}
      />
      <IntervalsField
        label="Предпочтительное время"
        hint="Необязательно: учитывается, если выбран критерий оптимизации."
        value={form.values.preferences}
        onChange={(next) => form.setValue("preferences", next)}
        error={form.errors.preferences}
      />
    </ResourceFormDialog>
  );
}
