import { Box, Button, Typography } from "@mui/material";
import { Link as RouterLink } from "react-router";

import { paths } from "../app/paths.js";

export default function NotFoundPage() {
  return (
    <Box sx={{ py: 8, textAlign: "center" }}>
      <Typography component="h1" variant="h4" gutterBottom>
        Страница не найдена
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Возможно, ссылка устарела или проект был удалён.
      </Typography>
      <Button component={RouterLink} to={paths.projects} variant="contained">
        К списку проектов
      </Button>
    </Box>
  );
}
