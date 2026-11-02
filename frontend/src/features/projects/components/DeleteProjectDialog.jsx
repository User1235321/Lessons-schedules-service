import { useState } from "react";
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle
} from "@mui/material";

import { projectsApi } from "../api.js";

// Подтверждение удаления. Вместе с проектом удаляются все его данные и расписания
// project остаётся заданным и при закрытии, чтобы текст не пропадал во время анимации
export default function DeleteProjectDialog({ open, project, onClose, onDeleted }) {
  const [error, setError] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const handleClose = () => {
    if (!deleting) {
      onClose();
    }
  };

  const handleDelete = async () => {
    setError(null);
    setDeleting(true);
    try {
      await projectsApi.remove(project.id);
      onDeleted(project);
    } catch (apiError) {
      // Проекта уже нет (удалён в другой вкладке) — для пользователя это тот же результат
      if (apiError.code === "NOT_FOUND") {
        onDeleted(project);
        return;
      }
      setError(apiError.message ?? "Не удалось удалить проект");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="xs"
      fullWidth
      slotProps={{ transition: { onExited: () => setError(null) } }}
    >
      <DialogTitle>Удалить проект?</DialogTitle>
      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        <DialogContentText>
          Проект «{project?.name}» будет удалён вместе с исходными данными и расписаниями.
          Отменить это действие нельзя.
        </DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={deleting}>
          Отмена
        </Button>
        <Button color="error" variant="contained" onClick={handleDelete} disabled={deleting}>
          Удалить
        </Button>
      </DialogActions>
    </Dialog>
  );
}
