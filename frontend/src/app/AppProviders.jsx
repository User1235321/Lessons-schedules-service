import { CssBaseline, ThemeProvider } from "@mui/material";

import { theme } from "./theme.js";

// Сюда же позже добавятся QueryClientProvider, AuthProvider и т. п.
export default function AppProviders({ children }) {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {children}
    </ThemeProvider>
  );
}
