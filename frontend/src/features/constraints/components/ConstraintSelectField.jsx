import { TextField } from "@mui/material";

const nativeSelect = { select: { native: true } };

export default function ConstraintSelectField({ label, value, onChange, options, error, disabled }) {
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
      {(value === "" || options.length === 0) && (
        <option value="">{options.length ? "Выберите..." : "Нет доступных элементов"}</option>
      )}
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </TextField>
  );
}
