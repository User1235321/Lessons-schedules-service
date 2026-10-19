import { Box, Chip, List, ListItem, ListItemText, Stack, Typography } from "@mui/material";

// Временная страница-заглушка: показывает, что будет в разделе.
// Заменяется реальной страницей по мере реализации функциональной области.
export default function PlaceholderPage({ title, description, planned = [], children }) {
  return (
    <Box sx={{ py: 2 }}>
      <Stack direction="row" spacing={1} sx={{ alignItems: "center", mb: 1 }}>
        <Typography component="h2" variant="h5">
          {title}
        </Typography>
        <Chip label="В разработке" size="small" variant="outlined" />
      </Stack>

      {description && <Typography color="text.secondary">{description}</Typography>}

      {planned.length > 0 && (
        <List dense aria-label="Планируемые функции">
          {planned.map((item) => (
            <ListItem key={item} disableGutters>
              <ListItemText primary={`• ${item}`} />
            </ListItem>
          ))}
        </List>
      )}

      {children}
    </Box>
  );
}
