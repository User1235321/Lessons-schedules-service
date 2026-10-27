import { CssBaseline, ThemeProvider } from "@mui/material";

import { AuthProvider } from "../features/auth/AuthProvider.jsx";
import { theme } from "./theme.js";

// Сюда же позже добавится QueryClientProvider и т. п.
export default function AppProviders({ children }) {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AuthProvider>{children}</AuthProvider>
    </ThemeProvider>
  );
}
