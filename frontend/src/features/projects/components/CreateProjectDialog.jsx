import { useState } from "react";
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField
} from "@mui/material";

import { projectsApi } from "../api.js";
import { MAX_PROJECT_NAME_LENGTH, validateProjectName } from "../validation.js";

// Диалог создания проекта. Настройки не спрашиваем: бэкенд подставит значения по умолчанию (F_Project_5)
export default function CreateProjectDialog({ open, onClose, onCreated }) {
  const [name, setName] = useState("");
  const [nameError, setNameError] = useState(null);
  const [formError, setFormError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const reset = () => {
    setName("");
    setNameError(null);
    setFormError(null);
    setSubmitting(false);
  };

  const handleClose = () => {
    if (!submitting) {
      onClose();
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setFormError(null);

    const error = validateProjectName(name);
    setNameError(error);
    if (error) {
      return;
    }

    setSubmitting(true);
    try {
      const project = await projectsApi.create({ name: name.trim() });
      onCreated(project);
    } catch (apiError) {
      if (apiError.code === "INVALID_VALUE" && apiError.details?.field === "name") {
        setNameError(apiError.message);
      } else {
        setFormError(apiError.message ?? "Не удалось создать проект");
      }
      setSubmitting(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      fullWidth
      maxWidth="xs"
      slotProps={{ transition: { onExited: reset } }}
    >
      <form noValidate onSubmit={handleSubmit}>
        <DialogTitle>Новый проект</DialogTitle>
        <DialogContent>
          {formError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {formError}
            </Alert>
          )}
          <TextField
            label="Название проекта"
            value={name}
            onChange={(event) => {
              setName(event.target.value);
              setNameError(null);
            }}
            error={Boolean(nameError)}
            helperText={nameError}
            slotProps={{ htmlInput: { maxLength: MAX_PROJECT_NAME_LENGTH } }}
            autoFocus
            fullWidth
            margin="dense"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose} disabled={submitting}>
            Отмена
          </Button>
          <Button type="submit" variant="contained" disabled={submitting}>
            Создать
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
