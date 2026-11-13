import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack
} from "@mui/material";

// Оболочка диалога создания и изменения. Поля и состояние задаёт раздел через useResourceForm
export default function ResourceFormDialog({
  open,
  title,
  submitLabel = "Сохранить",
  form,
  onClose,
  maxWidth = "xs",
  children
}) {
  const handleClose = () => {
    if (!form.submitting) {
      onClose();
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} fullWidth maxWidth={maxWidth}>
      <form noValidate onSubmit={form.handleSubmit}>
        <DialogTitle>{title}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            {form.formError && <Alert severity="error">{form.formError}</Alert>}
            {children}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose} disabled={form.submitting}>
            Отмена
          </Button>
          <Button type="submit" variant="contained" disabled={form.submitting}>
            {submitLabel}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
