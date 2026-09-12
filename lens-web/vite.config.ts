import { readFileSync } from "node:fs";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Lens's own PWA build (§8). The engine base URL is injected at build time
// for self-hosted deployments; local development talks to 127.0.0.1:8765.
// The version is read from package.json so the UI can never drift back to
// a stale hard-coded value (the 0.2.0 rebuild shipped showing 0.1.0).
const pkg = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf-8"));

export default defineConfig({
  plugins: [react()],
  define: {
    __LENS_VERSION__: JSON.stringify(pkg.version),
    __ENGINE_BASE_URL__: JSON.stringify(
      process.env.LENS_ENGINE_URL ?? "http://127.0.0.1:8765"
    ),
  },
  server: { port: 5173 },
  build: { outDir: "dist", sourcemap: true },
});
