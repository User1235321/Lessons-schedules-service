import { Alert, AlertTitle, Box, Button } from "@mui/material";

// Общий блок ошибки. Подходит и для ошибок маршрута, и для ошибок загрузки данных
// (сообщение можно брать из поля `message` единого формата ошибок API).
export default function ErrorState({
  title = "Не удалось загрузить данные",
  message,
  onRetry,
  retryLabel = "Повторить",
  action
}) {
  return (
    <Box sx={{ py: 4 }}>
      <Alert
        severity="error"
        action={
          action ??
          (onRetry && (
            <Button color="inherit" size="small" onClick={onRetry}>
              {retryLabel}
            </Button>
          ))
        }
      >
        <AlertTitle>{title}</AlertTitle>
        {message}
      </Alert>
    </Box>
  );
}
