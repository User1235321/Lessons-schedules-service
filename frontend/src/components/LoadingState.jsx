import { Box, CircularProgress, Typography } from "@mui/material";

export default function LoadingState({ label = "Загрузка…", fullPage = false }) {
  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 2,
        py: 6,
        minHeight: fullPage ? "100vh" : undefined
      }}
    >
      <CircularProgress aria-label={label} />
      <Typography color="text.secondary">{label}</Typography>
    </Box>
  );
}
