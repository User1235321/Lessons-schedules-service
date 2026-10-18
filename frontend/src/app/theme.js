import { createTheme } from "@mui/material/styles";
import { ruRU } from "@mui/material/locale";

export const theme = createTheme(
  {
    palette: {
      primary: { main: "#1565c0" }
    },
    shape: { borderRadius: 8 }
  },
  ruRU
);
