import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// uvicorn по умолчанию слушает 127.0.0.1. С "localhost" Node может выбрать ::1 и не достучаться
const API_TARGET = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Пути API (/projects, /auth/...) совпадают с маршрутами SPA, поэтому запросы к бэкенду
      // идут через префикс /api, который здесь срезается
      "/api": {
        target: API_TARGET,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
        // Бэкенд ставит refresh-cookie с Path=/auth, а браузер видит путь /api/auth
        cookiePathRewrite: { "/auth": "/api/auth" }
      }
    }
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.js"]
  }
});
