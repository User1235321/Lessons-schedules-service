import { CssBaseline } from "@mui/material";
import { createRoot } from "react-dom/client";

import App from "./App.jsx";

createRoot(document.getElementById("root")).render(
  <>
    <CssBaseline />
    <App />
  </>
);
