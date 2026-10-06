import { Container, Stack, Typography } from "@mui/material";

export default function App() {
  return (
    <Container maxWidth="md">
      <Stack spacing={2} sx={{ py: 4 }}>
        <Typography component="h1" variant="h4">
          Lessons schedules service
        </Typography>
        <Typography>
          Сервис автоматического составления расписания занятий.
        </Typography>
      </Stack>
    </Container>
  );
}
