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

// Подтверждение опасного действия. onConfirm — асинхронное действие: при ошибке диалог
// остаётся открытым и показывает сообщение, при успехе закрывается
export default function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel = "Удалить",
  onConfirm,
  onClose
}) {
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const handleClose = () => {
    if (!busy) {
      onClose();
    }
  };

  const handleConfirm = async () => {
    setError(null);
    setBusy(true);
    try {
      await onConfirm();
      onClose();
    } catch (apiError) {
      setError(apiError.message ?? "Не удалось выполнить действие");
    } finally {
      setBusy(false);
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
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        <DialogContentText>{children}</DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={busy}>
          Отмена
        </Button>
        <Button color="error" variant="contained" onClick={handleConfirm} disabled={busy}>
          {confirmLabel}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
