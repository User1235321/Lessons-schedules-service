import { Autocomplete, Stack, TextField } from "@mui/material";

import ResourceFormDialog from "../project-editor/components/ResourceFormDialog.jsx";
import { LESSON_FORMATS, WEEKDAYS, WEEKS } from "../project-editor/intervals.js";
import { useResourceForm } from "../project-editor/useResourceForm.js";

const storedRoom = "stored-room";
const teacherKey = (item) => item.teacher_id ?? `name:${item.display_name}`;

function entryChanges(entry, values) {
  const changes = {};
  for (const field of ["week", "weekday", "start_time", "end_time", "lesson_format"]) {
    if ((entry[field] ?? "") !== values[field]) changes[field] = values[field];
  }
  if (values.lesson_format === "REMOTE" && changes.lesson_format) {
    changes.room_id = null;
    changes.room_name = null;
  } else if (values.room !== (entry.room_id ?? (entry.room_name ? storedRoom : ""))) {
    changes.room_id = values.room || null;
    if (!changes.room_id) changes.room_name = null;
  }
  if (values.teachers !== entry.teachers) changes.teachers = values.teachers;
  return changes;
}

export default function EntryDialog({ entry, rooms, teachers, onSave, onClose }) {
  const form = useResourceForm({
    open: true,
    initialValues: {
      week: entry.week,
      weekday: entry.weekday,
      start_time: entry.start_time,
      end_time: entry.end_time,
      lesson_format: entry.lesson_format ?? "",
      room: entry.room_id ?? (entry.room_name ? storedRoom : ""),
      teachers: entry.teachers
    },
    errorAliases: { room_id: "room", room_name: "room" },
    validate: ({ start_time, end_time }) => {
      const errors = {};
      if (!start_time) errors.start_time = "Укажите время начала";
      if (!end_time) errors.end_time = "Укажите время окончания";
      else if (start_time && end_time <= start_time) errors.end_time = "Окончание должно быть позже начала";
      return errors;
    },
    onSubmit: (values) => onSave(entryChanges(entry, values))
  });
  const { values, errors, setValue, submitting } = form;
  const options = teachers.map((item) => ({ teacher_id: item.id, display_name: item.full_name }));
  const known = new Set(options.map(teacherKey));
  options.push(...entry.teachers.filter((item) => !known.has(teacherKey(item))));

  function field(name) {
    return {
      value: values[name],
      onChange: (event) => setValue(name, event.target.value),
      error: Boolean(errors[name]),
      helperText: errors[name],
      disabled: submitting,
      fullWidth: true
    };
  }
  const native = { select: { native: true }, inputLabel: { shrink: true } };
  const originalRoomMissing = entry.room_id && !rooms.some((item) => item.id === entry.room_id);

  return (
    <ResourceFormDialog open title={`Изменить занятие · ${entry.subject_name || "Без названия"}`}
      form={form} onClose={onClose} maxWidth="sm">
      <Stack spacing={2} direction={{ xs: "column", sm: "row" }}>
        <TextField select label="Неделя" slotProps={native} {...field("week")}>
          {WEEKS.filter((item) => item.value !== "ANY").map(({ value, label }) =>
            <option key={value} value={value}>{label}</option>)}
        </TextField>
        <TextField select label="День" slotProps={native} {...field("weekday")}>
          {WEEKDAYS.map(({ value, label }) => <option key={value} value={value}>{label}</option>)}
        </TextField>
      </Stack>
      <Stack spacing={2} direction={{ xs: "column", sm: "row" }}>
        <TextField type="time" label="Начало" slotProps={{ inputLabel: { shrink: true } }} {...field("start_time")} />
        <TextField type="time" label="Окончание" slotProps={{ inputLabel: { shrink: true } }} {...field("end_time")} />
      </Stack>
      <TextField select label="Формат" slotProps={native} {...field("lesson_format")}>
        {!entry.lesson_format && <option value="" disabled>Не указан</option>}
        {LESSON_FORMATS.map(({ value, label }) => <option key={value} value={value}>{label}</option>)}
      </TextField>
      {values.lesson_format !== "REMOTE" && (
        <TextField select label="Аудитория" slotProps={native} {...field("room")}>
          <option value="">Не назначена</option>
          {(originalRoomMissing || (!entry.room_id && entry.room_name)) &&
            <option value={entry.room_id ?? storedRoom}>{entry.room_name || entry.room_id}</option>}
          {rooms.map((room) => <option key={room.id} value={room.id}>{room.name}</option>)}
        </TextField>
      )}
      <Autocomplete multiple filterSelectedOptions options={options} value={values.teachers}
        disabled={submitting} getOptionLabel={(item) => item.display_name} getOptionKey={teacherKey}
        isOptionEqualToValue={(a, b) => teacherKey(a) === teacherKey(b)}
        onChange={(_, next) => setValue("teachers", next)}
        renderInput={(params) => <TextField {...params} label="Преподаватели"
          error={Boolean(errors.teachers)} helperText={errors.teachers} />} />
    </ResourceFormDialog>
  );
}
