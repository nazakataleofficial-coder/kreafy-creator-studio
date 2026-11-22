import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Localhost only: the dev server binds to 127.0.0.1, never 0.0.0.0.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
  },
});
