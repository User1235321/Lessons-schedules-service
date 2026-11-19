import {
  Alert,
  Button,
  Checkbox,
  FormControlLabel,
  FormGroup,
  Stack,
  TextField,
  Typography
} from "@mui/material";

import { WEEKDAYS, WEEKS } from "../../project-editor/intervals.js";
import {
  allowedScopeTypes,
  CONSTRAINT_TYPES,
  NEW_WINDOW,
  SCOPE_TYPES
} from "../constraintModel.js";

const nativeSelect = { select: { native: true } };

function SelectField({ label, value, onChange, options, error, disabled }) {
  return (
    <TextField
      select
      fullWidth
      label={label}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      error={Boolean(error)}
      helperText={error}
      disabled={disabled}
      slotProps={nativeSelect}
    >
      {options.length === 0 && <option value="">Нет доступных элементов</option>}
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </TextField>
  );
}

export default function ConstraintFields({ values, errors, setValue, options }) {
  const scopeTypes = allowedScopeTypes(values.kind);
  const workloadOnly = scopeTypes.length === 1;
  const relatedTypes = ["CONSECUTIVE", "NOT_CONSECUTIVE", "MIN_GAP", "BEFORE"];
  const changeKind = (kind) => {
    setValue("kind", kind);
    if (allowedScopeTypes(kind).length === 1 && values.scopeType !== "WORKLOAD") {
      setValue("scopeType", "WORKLOAD");
      setValue("scopeId", options.WORKLOAD[0]?.id ?? "");
    }
  };
  const changeScopeType = (type) => {
    setValue("scopeType", type);
    setValue("scopeId", options[type]?.[0]?.id ?? "");
  };
  const changeWindow = (index, field, value) => {
    setValue("windows", values.windows.map((window, position) =>
      position === index ? { ...window, [field]: value } : window
    ));
  };
  const relatedOptions = options.WORKLOAD.filter((item) => item.id !== values.scopeId)
    .map((item) => ({ value: item.id, label: item.label }));

  return (
    <>
      <SelectField
        label="Тип ограничения"
        value={values.kind}
        onChange={changeKind}
        options={CONSTRAINT_TYPES}
      />
      <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
        <SelectField
          label="Область применения"
          value={values.scopeType}
          onChange={changeScopeType}
          options={scopeTypes.map((type) => ({ ...type }))}
          disabled={workloadOnly}
        />
        {values.scopeType !== "PROJECT" && (
          <SelectField
            label={SCOPE_TYPES.find((scope) => scope.value === values.scopeType)?.label ?? "Ресурс"}
            value={options[values.scopeType]?.some((item) => item.id === values.scopeId)
              ? values.scopeId : ""}
            onChange={(id) => setValue("scopeId", id)}
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
        <Stack spacing={2}>
          <Typography>Допустимые интервалы</Typography>
          {values.windows.map((window, index) => (
            <Stack key={index} spacing={2} sx={{ border: 1, borderColor: "divider", borderRadius: 1, p: 2 }}>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                <SelectField
                  label="Неделя"
                  value={window.week}
                  onChange={(value) => changeWindow(index, "week", value)}
                  options={WEEKS}
                />
                <SelectField
                  label="День"
                  value={window.day}
                  onChange={(value) => changeWindow(index, "day", value)}
                  options={WEEKDAYS}
                />
              </Stack>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                <TextField
                  label="Начало"
                  type="time"
                  value={window.start}
                  onChange={(event) => changeWindow(index, "start", event.target.value)}
                  slotProps={{ inputLabel: { shrink: true } }}
                  fullWidth
                />
                <TextField
                  label="Конец"
                  type="time"
                  value={window.end}
                  onChange={(event) => changeWindow(index, "end", event.target.value)}
                  slotProps={{ inputLabel: { shrink: true } }}
                  fullWidth
                />
              </Stack>
              <Button
                color="error"
                size="small"
                onClick={() => setValue("windows", values.windows.filter((_, position) => position !== index))}
              >
                Удалить интервал
              </Button>
            </Stack>
          ))}
          {errors.windows && <Alert severity="error">{errors.windows}</Alert>}
          <Button onClick={() => setValue("windows", [...values.windows, { ...NEW_WINDOW }])}>
            Добавить интервал
          </Button>
        </Stack>
      )}
      {relatedTypes.includes(values.kind) && (
        <>
          {relatedOptions.length === 0 && (
            <Alert severity="warning">
              Для этого ограничения нужны две разные учебные нагрузки.
            </Alert>
          )}
          <SelectField
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
          <SelectField
            label="День"
            value={values.day}
            onChange={(value) => setValue("day", value)}
            options={WEEKDAYS}
          />
          <SelectField
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
