import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
import "./styles/tokens.css";

// ─── Service worker policy (v0.2.0 rebuild) ────────────────────────────────
// The v0.2.0 release shipped a white screen on upgraded installs: the PWA
// service worker registered inside the Tauri WebView (http://tauri.localhost
// is a secure context), and its cache-first shell served the PREVIOUS
// build's index.html, which pointed at hashed assets that no longer exist.
// Result: blank white window. Two-part policy:
//   1. Inside the desktop shell the SW is NEVER registered, and any SW or
//      shell cache a previous version left behind is removed (self-healing
//      for machines that already have the poisoned state).
//   2. In browsers the SW stays a progressive enhancement, and sw.js is
//      network-first for navigations so index.html can never go stale.
const IN_TAURI =
  typeof (window as any).__TAURI_INTERNALS__ !== "undefined" ||
  typeof (window as any).__TAURI__ !== "undefined";

async function removeStaleShellState(): Promise<void> {
  try {
    if ("serviceWorker" in navigator) {
      const regs = await navigator.serviceWorker.getRegistrations();
      await Promise.all(regs.map((r) => r.unregister()));
    }
    if (typeof caches !== "undefined") {
      const keys = await caches.keys();
      await Promise.all(keys.filter((k) => k.startsWith("lens-")).map((k) => caches.delete(k)));
    }
  } catch {
    /* best-effort cleanup */
  }
}

if (IN_TAURI) {
  void removeStaleShellState();
} else if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      /* offline caching is progressive enhancement */
    });
  });
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
