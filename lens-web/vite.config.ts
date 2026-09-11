import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Lens's own PWA build (§8). The engine base URL is injected at build time
// for self-hosted deployments; local development talks to 127.0.0.1:8765.
export default defineConfig({
  plugins: [react()],
  define: {
    __LENS_VERSION__: JSON.stringify("0.1.0"),
    __ENGINE_BASE_URL__: JSON.stringify(
      process.env.LENS_ENGINE_URL ?? "http://127.0.0.1:8765"
    ),
  },
  server: { port: 5173 },
  build: { outDir: "dist", sourcemap: true },
});
