import { Box, Container, Paper, Typography } from "@mui/material";
import { Outlet } from "react-router";

export default function AuthLayout() {
  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        bgcolor: "grey.100"
      }}
    >
      <Container maxWidth="xs">
        <Typography
          component="p"
          variant="h6"
          sx={{ textAlign: "center", mb: 2, fontWeight: 600 }}
        >
          Расписание занятий
        </Typography>
        <Paper sx={{ p: 4 }}>
          <Outlet />
        </Paper>
      </Container>
    </Box>
  );
}
