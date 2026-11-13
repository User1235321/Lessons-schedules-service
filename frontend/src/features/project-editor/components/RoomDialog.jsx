import { Alert, Link, TextField } from "@mui/material";
import { Link as RouterLink } from "react-router";

import { paths } from "../../../app/paths.js";
import { resourceApi } from "../api.js";
import {
  ROOM_TYPES,
  roomTypeHasCapabilities,
  validateCapabilities,
  validateIntervals
} from "../intervals.js";
import { useResourceForm } from "../useResourceForm.js";
import { MAX_NAME_LENGTH, validateName, validatePositiveInteger } from "../validation.js";
import CapabilitiesField from "./CapabilitiesField.jsx";
import IntervalsField from "./IntervalsField.jsx";
import ResourceFormDialog from "./ResourceFormDialog.jsx";

const copy = (items) => items.map((item) => ({ ...item }));

// Аудитория: название, вместимость, тип и доступность обязательны (F_Data_7, F_Data_8).
// Пары «дисциплина + тип занятия» есть только у специализированных и лабораторий (F_Data_9)
export default function RoomDialog({ open, item, projectId, subjects, onClose, onSaved }) {
  const form = useResourceForm({
    open,
    initialValues: {
      name: item?.name ?? "",
      capacity: String(item?.capacity ?? ""),
      type: item?.type ?? ROOM_TYPES[0].value,
      availability: copy(item?.availability ?? []),
      capabilities: copy(item?.capabilities ?? [])
    },
    validate: (values) => {
      const errors = {
        name: validateName(values.name, "Укажите номер или название аудитории"),
        capacity: validatePositiveInteger(values.capacity, "Нужна положительная вместимость"),
        availability: validateIntervals(values.availability, { required: true }),
        capabilities: roomTypeHasCapabilities(values.type)
          ? validateCapabilities(values.capabilities, { required: false })
          : null
      };
      return Object.fromEntries(Object.entries(errors).filter(([, error]) => error));
    },
    onSubmit: async (values) => {
      const api = resourceApi(projectId, "rooms");
      const body = {
        name: values.name.trim(),
        capacity: Number(values.capacity),
        type: values.type,
        availability: values.availability,
        // Тип и пары меняются вместе: у остальных типов пар быть не должно
        capabilities: roomTypeHasCapabilities(values.type) ? values.capabilities : []
      };
      onSaved(item ? await api.update(item.id, body) : await api.create(body));
    }
  });

  const withCapabilities = roomTypeHasCapabilities(form.values.type);

  return (
    <ResourceFormDialog
      open={open}
      title={item ? "Изменить аудиторию" : "Новая аудитория"}
      submitLabel={item ? "Сохранить" : "Добавить"}
      form={form}
      onClose={onClose}
      maxWidth="md"
    >
      <TextField
        label="Номер или название"
        value={form.values.name}
        onChange={(event) => form.setValue("name", event.target.value)}
        error={Boolean(form.errors.name)}
        helperText={form.errors.name}
        slotProps={{ htmlInput: { maxLength: MAX_NAME_LENGTH } }}
        autoFocus
        fullWidth
      />
      <TextField
        label="Вместимость"
        value={form.values.capacity}
        onChange={(event) => form.setValue("capacity", event.target.value)}
        error={Boolean(form.errors.capacity)}
        helperText={form.errors.capacity}
        slotProps={{ htmlInput: { inputMode: "numeric" } }}
        fullWidth
      />
      <TextField
        select
        label="Тип аудитории"
        value={form.values.type}
        onChange={(event) => form.setValue("type", event.target.value)}
        slotProps={{ select: { native: true } }}
        fullWidth
      >
        {ROOM_TYPES.map((type) => (
          <option key={type.value} value={type.value}>
            {type.label}
          </option>
        ))}
      </TextField>

      {withCapabilities && subjects.length === 0 && (
        <Alert severity="warning">
          Чтобы указать допустимые дисциплины, сначала добавьте их в разделе{" "}
          <Link component={RouterLink} to={paths.projectSection(projectId, "subjects")}>
            «Дисциплины»
          </Link>
          .
        </Alert>
      )}
      {withCapabilities && (
        <CapabilitiesField
          label="Допустимые занятия"
          hint="Какие дисциплины и типы занятий можно проводить в этой аудитории."
          subjects={subjects}
          value={form.values.capabilities}
          onChange={(next) => form.setValue("capabilities", next)}
          error={form.errors.capabilities}
        />
      )}
      <IntervalsField
        label="Доступность"
        hint="Когда в аудитории можно проводить занятия."
        value={form.values.availability}
        onChange={(next) => form.setValue("availability", next)}
        error={form.errors.availability}
      />
    </ResourceFormDialog>
  );
}
