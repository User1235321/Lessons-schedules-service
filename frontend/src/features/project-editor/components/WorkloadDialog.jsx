import { Alert, Link, Stack, TextField } from "@mui/material";
import { Link as RouterLink } from "react-router";

import { paths } from "../../../app/paths.js";
import { resourceApi } from "../api.js";
import { LESSON_FORMATS, LESSON_TYPES, TARGET_TYPES } from "../intervals.js";
import { useResourceForm } from "../useResourceForm.js";
import { validatePositiveInteger } from "../validation.js";
import ResourceFormDialog from "./ResourceFormDialog.jsx";

const nativeSelect = { select: { native: true } };

function SelectField({ label, value, onChange, options, error, disabled }) {
  return (
    <TextField
      select
      label={label}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      error={Boolean(error)}
      helperText={error}
      disabled={disabled}
      slotProps={nativeSelect}
      fullWidth
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </TextField>
  );
}

// Элемент учебной нагрузки (F_Data_16, F_Data_17). Длительность задаётся только в режиме
// INDIVIDUAL, иначе берётся из настроек проекта. Несколько преподавателей — только на лабораторной
export default function WorkloadDialog({
  open,
  item,
  projectId,
  subjects,
  targets,
  individualDuration,
  projectDuration,
  onClose,
  onSaved
}) {
  const firstTarget = (type) => targets[type][0]?.id ?? "";

  const form = useResourceForm({
    open,
    initialValues: {
      target_type: item?.target.type ?? "GROUP",
      target_id: item?.target.id ?? firstTarget("GROUP"),
      subject_id: item?.subject_id ?? subjects[0]?.id ?? "",
      lesson_type: item?.lesson_type ?? LESSON_TYPES[0].value,
      format: item?.format ?? LESSON_FORMATS[0].value,
      occurrences_per_cycle: String(item?.occurrences_per_cycle ?? "1"),
      duration_minutes: String(item?.duration_minutes ?? ""),
      required_teacher_count: String(item?.required_teacher_count ?? "1")
    },
    validate: (values) => {
      const errors = {
        target_id: values.target_id ? null : "Выберите, для кого нагрузка",
        subject_id: values.subject_id ? null : "Выберите дисциплину",
        occurrences_per_cycle: validatePositiveInteger(
          values.occurrences_per_cycle,
          "Нужно положительное число занятий"
        ),
        duration_minutes: individualDuration
          ? validatePositiveInteger(values.duration_minutes, "Нужна положительная длительность в минутах")
          : null,
        required_teacher_count:
          values.lesson_type === "LAB"
            ? validatePositiveInteger(values.required_teacher_count, "Нужен хотя бы один преподаватель")
            : null
      };
      return Object.fromEntries(Object.entries(errors).filter(([, error]) => error));
    },
    onSubmit: async (values) => {
      const api = resourceApi(projectId, "workloads");
      const body = {
        target: { type: values.target_type, id: values.target_id },
        subject_id: values.subject_id,
        lesson_type: values.lesson_type,
        format: values.format,
        occurrences_per_cycle: Number(values.occurrences_per_cycle),
        // В режиме UNIFORM сохранённая длительность не трогается: она пригодится, если режим сменят обратно
        duration_minutes: individualDuration
          ? Number(values.duration_minutes)
          : (item?.duration_minutes ?? null),
        required_teacher_count: values.lesson_type === "LAB" ? Number(values.required_teacher_count) : 1
      };
      onSaved(item ? await api.update(item.id, body) : await api.create(body));
    }
  });

  const { values, errors, setValue } = form;
  const options = targets[values.target_type];

  const changeTargetType = (type) => {
    setValue("target_type", type);
    setValue("target_id", firstTarget(type));
  };

  return (
    <ResourceFormDialog
      open={open}
      title={item ? "Изменить нагрузку" : "Новая нагрузка"}
      submitLabel={item ? "Сохранить" : "Добавить"}
      form={form}
      onClose={onClose}
      maxWidth="sm"
    >
      {subjects.length === 0 && (
        <Alert severity="warning">
          Сначала добавьте дисциплины в разделе{" "}
          <Link component={RouterLink} to={paths.projectSection(projectId, "subjects")}>
            «Дисциплины»
          </Link>
          .
        </Alert>
      )}

      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        <SelectField
          label="Для кого"
          value={values.target_type}
          onChange={changeTargetType}
          options={TARGET_TYPES}
        />
        <SelectField
          label={TARGET_TYPES.find((type) => type.value === values.target_type).label}
          value={values.target_id}
          onChange={(next) => setValue("target_id", next)}
          options={options.map((option) => ({ value: option.id, label: option.label }))}
          error={errors.target_id ?? (options.length === 0 ? "Список пуст" : null)}
          disabled={options.length === 0}
        />
      </Stack>
      <SelectField
        label="Дисциплина"
        value={values.subject_id}
        onChange={(next) => setValue("subject_id", next)}
        options={subjects.map((subject) => ({ value: subject.id, label: subject.name }))}
        error={errors.subject_id}
        disabled={subjects.length === 0}
      />
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        <SelectField
          label="Тип занятия"
          value={values.lesson_type}
          onChange={(next) => setValue("lesson_type", next)}
          options={LESSON_TYPES}
        />
        <SelectField
          label="Формат"
          value={values.format}
          onChange={(next) => setValue("format", next)}
          options={LESSON_FORMATS}
        />
      </Stack>
      <TextField
        label="Занятий за двухнедельный цикл"
        value={values.occurrences_per_cycle}
        onChange={(event) => setValue("occurrences_per_cycle", event.target.value)}
        error={Boolean(errors.occurrences_per_cycle)}
        helperText={errors.occurrences_per_cycle}
        slotProps={{ htmlInput: { inputMode: "numeric" } }}
        fullWidth
      />
      {individualDuration ? (
        <TextField
          label="Длительность, минут"
          value={values.duration_minutes}
          onChange={(event) => setValue("duration_minutes", event.target.value)}
          error={Boolean(errors.duration_minutes)}
          helperText={errors.duration_minutes}
          slotProps={{ htmlInput: { inputMode: "numeric" } }}
          fullWidth
        />
      ) : (
        <Alert severity="info">
          Длительность занятий едина для проекта{projectDuration ? `: ${projectDuration} мин` : ""}. Её
          можно изменить в разделе{" "}
          <Link component={RouterLink} to={paths.projectSection(projectId, "settings")}>
            «Настройки»
          </Link>
          .
        </Alert>
      )}
      {values.lesson_type === "LAB" && (
        <TextField
          label="Число преподавателей"
          value={values.required_teacher_count}
          onChange={(event) => setValue("required_teacher_count", event.target.value)}
          error={Boolean(errors.required_teacher_count)}
          helperText={errors.required_teacher_count ?? "На лекции и практике всегда один преподаватель"}
          slotProps={{ htmlInput: { inputMode: "numeric" } }}
          fullWidth
        />
      )}
    </ResourceFormDialog>
  );
}
