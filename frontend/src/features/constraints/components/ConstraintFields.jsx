import {
  Alert,
  Checkbox,
  FormControlLabel,
  FormGroup,
  Stack,
  TextField,
  Typography
} from "@mui/material";

import { WEEKDAYS, WEEKS } from "../../project-editor/intervals.js";
import ConstraintSelectField from "./ConstraintSelectField.jsx";
import TimeWindowsFields from "./TimeWindowsFields.jsx";
import {
  allowedScopeTypes,
  CONSTRAINT_TYPES,
  SCOPE_TYPES
} from "../constraintModel.js";

export default function ConstraintFields({ values, errors, setValue, options }) {
  const scopeTypes = allowedScopeTypes(values.kind);
  const workloadOnly = scopeTypes.length === 1;
  const relatedTypes = ["CONSECUTIVE", "NOT_CONSECUTIVE", "MIN_GAP", "BEFORE"];
  const changeKind = (kind) => {
    setValue("kind", kind);
    if (kind === "MIN_START_TIME") setValue("time", "08:00");
    if (kind === "MAX_END_TIME") setValue("time", "18:00");
    const workloadOnly = allowedScopeTypes(kind).length === 1;
    const scopeId = workloadOnly
      ? values.scopeType === "WORKLOAD" ? values.scopeId : options.WORKLOAD[0]?.id ?? ""
      : values.scopeId;
    if (workloadOnly && values.scopeType !== "WORKLOAD") {
      setValue("scopeType", "WORKLOAD");
      setValue("scopeId", scopeId);
    }
    if (relatedTypes.includes(kind) &&
      !options.WORKLOAD.some((item) => item.id === values.relatedWorkloadId && item.id !== scopeId)) {
      setValue("relatedWorkloadId", options.WORKLOAD.find((item) => item.id !== scopeId)?.id ?? "");
    }
  };
  const changeScopeId = (id) => {
    setValue("scopeId", id);
    if (relatedTypes.includes(values.kind) && id === values.relatedWorkloadId) {
      setValue("relatedWorkloadId", options.WORKLOAD.find((item) => item.id !== id)?.id ?? "");
    }
  };
  const changeScopeType = (type) => {
    setValue("scopeType", type);
    changeScopeId(options[type]?.[0]?.id ?? "");
  };
  const relatedOptions = options.WORKLOAD.filter((item) => item.id !== values.scopeId)
    .map((item) => ({ value: item.id, label: item.label }));

  return (
    <>
      <ConstraintSelectField
        label="Тип ограничения"
        value={values.kind}
        onChange={changeKind}
        options={CONSTRAINT_TYPES}
      />
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        <ConstraintSelectField
          label="Область применения"
          value={values.scopeType}
          onChange={changeScopeType}
          options={scopeTypes}
          disabled={workloadOnly}
        />
        {values.scopeType !== "PROJECT" && (
          <ConstraintSelectField
            label={SCOPE_TYPES.find((scope) => scope.value === values.scopeType)?.label ?? "Ресурс"}
            value={options[values.scopeType]?.some((item) => item.id === values.scopeId)
              ? values.scopeId : ""}
            onChange={changeScopeId}
            options={(options[values.scopeType] ?? []).map((item) => ({ value: item.id, label: item.label }))}
            error={errors.scopeId}
          />
        )}
      </Stack>
      {["MIN_START_TIME", "MAX_END_TIME"].includes(values.kind) && (
        <TextField
          label="Время"
          type="time"
          value={values.time}
          onChange={(event) => setValue("time", event.target.value)}
          error={Boolean(errors.time)}
          helperText={errors.time}
          slotProps={{ inputLabel: { shrink: true } }}
          fullWidth
        />
      )}
      {values.kind === "ALLOWED_DAYS" && (
        <Stack spacing={1}>
          <Typography>Допустимые дни</Typography>
          <FormGroup row>
            {WEEKDAYS.map((day) => (
              <FormControlLabel
                key={day.value}
                label={day.label}
                control={
                  <Checkbox
                    checked={values.days.includes(day.value)}
                    onChange={(event) => setValue("days", event.target.checked
                      ? [...values.days, day.value]
                      : values.days.filter((current) => current !== day.value))}
                  />
                }
              />
            ))}
          </FormGroup>
          {errors.days && <Alert severity="error">{errors.days}</Alert>}
        </Stack>
      )}
      {values.kind === "TIME_RANGE" && (
        <TimeWindowsFields
          windows={values.windows}
          error={errors.windows}
          onChange={(windows) => setValue("windows", windows)}
        />
      )}
      {relatedTypes.includes(values.kind) && (
        <>
          {relatedOptions.length === 0 && (
            <Alert severity="warning">
              Для этого ограничения нужны две разные учебные нагрузки.
            </Alert>
          )}
          <ConstraintSelectField
            label="Вторая учебная нагрузка"
            value={relatedOptions.some((item) => item.value === values.relatedWorkloadId)
              ? values.relatedWorkloadId : ""}
            onChange={(value) => setValue("relatedWorkloadId", value)}
            options={relatedOptions}
            error={errors.relatedWorkloadId}
          />
        </>
      )}
      {values.kind === "MIN_GAP" && (
        <TextField
          label="Минимальный интервал, минут"
          value={values.minutes}
          onChange={(event) => setValue("minutes", event.target.value)}
          error={Boolean(errors.minutes)}
          helperText={errors.minutes}
          slotProps={{ htmlInput: { inputMode: "numeric" } }}
          fullWidth
        />
      )}
      {values.kind === "FIXED_DAY" && (
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
          <ConstraintSelectField
            label="День"
            value={values.day}
            onChange={(value) => setValue("day", value)}
            options={WEEKDAYS}
          />
          <ConstraintSelectField
            label="Неделя"
            value={values.week}
            onChange={(value) => setValue("week", value)}
            options={WEEKS}
          />
        </Stack>
      )}
      {(errors.parameters || errors.scope || errors.constraint_type) && (
        <Alert severity="error">
          {errors.parameters ?? errors.scope ?? errors.constraint_type}
        </Alert>
      )}
    </>
  );
}
