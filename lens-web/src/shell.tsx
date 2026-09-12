import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { isRTL, STRINGS, type Lang } from "./i18n/strings";
import { engineUrl, LENS_VERSION } from "./lib/api";
import { WelcomeFlow } from "./components/Welcome";

export type ViewId = "overview" | "imagesets" | "workbench" | "social" | "assistant" | "settings";

interface Toast {
  id: number;
  message: string;
  kind: "ok" | "error";
}

interface ShellState {
  view: ViewId;
  setView: (v: ViewId) => void;
  lang: Lang;
  setLang: (l: Lang) => void;
  theme: "light" | "dark";
  setTheme: (t: "light" | "dark") => void;
  activeSetId: string | null;
  setActiveSetId: (id: string | null) => void;
  t: (typeof STRINGS)["en"];
  engine: { url: string; version: string };
  toast: (message: string, kind?: "ok" | "error") => void;
  welcomeOpen: boolean;
  openWelcome: () => void;
  closeWelcome: () => void;
}

const Ctx = createContext<ShellState | null>(null);

export function useShell(): ShellState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useShell outside provider");
  return v;
}

function CommandPalette({ onClose }: { onClose: () => void }) {
  const { setView, t } = useShell();
  const [q, setQ] = useState("");
  const targets: [string, ViewId][] = [
    [t.nav.overview, "overview"],
    [t.nav.imageSets, "imagesets"],
    [t.nav.workbench, "workbench"],
    [t.nav.social, "social"],
    [t.nav.assistant, "assistant"],
    [t.nav.settings, "settings"],
  ];
  const hits = targets.filter(([label]) => label.toLowerCase().includes(q.toLowerCase()));
  return (
    <div
      role="dialog"
      aria-modal="true"
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,.35)",
        display: "grid", placeItems: "start center", paddingTop: "12vh", zIndex: 50,
      }}
    >
      <div className="card" style={{ width: 420, margin: 0 }} onClick={(e) => e.stopPropagation()}>
        <input
          autoFocus
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="⌘K"
          aria-label="Command palette"
          style={{
            width: "100%", padding: "10px 12px", borderRadius: 8,
            border: "1px solid var(--border)", background: "var(--surface-2)", outline: "none",
          }}
        />
        <div style={{ marginTop: 8 }}>
          {hits.map(([label, id]) => (
            <button
              key={id}
              className="btn secondary"
              style={{ display: "block", width: "100%", textAlign: "start", marginBottom: 4 }}
              onClick={() => { setView(id); onClose(); }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function ToastHost({ toasts }: { toasts: Toast[] }) {
  return (
    <div aria-live="polite" style={{ position: "fixed", bottom: 18, insetInlineEnd: 18, zIndex: 60, display: "grid", gap: 8 }}>
      {toasts.map((t) => (
        <div
          key={t.id}
          className="lens-toast"
          role="status"
          style={{
            background: "var(--surface)", color: "var(--text)",
            border: "1px solid var(--border)",
            borderInlineStart: `4px solid ${t.kind === "error" ? "var(--danger)" : "var(--ok)"}`,
            borderRadius: 10, padding: "10px 14px", fontSize: 13, maxWidth: 380,
            boxShadow: "0 8px 24px rgba(0,0,0,.18)",
          }}
        >
          {t.message}
        </div>
      ))}
    </div>
  );
}

export function ShellProvider({ children }: { children: React.ReactNode }) {
  const [view, setView] = useState<ViewId>("overview");
  const [lang, setLang] = useState<Lang>(() =>
    (localStorage.getItem("lens.lang") as Lang) || "en");
  const [theme, setTheme] = useState<"light" | "dark">(() =>
    (localStorage.getItem("lens.theme") as "light" | "dark") ||
    (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
  const [activeSetId, setActiveSetId] = useState<string | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  // The welcome guide shows once per major version (v2 = this UX rebuild);
  // replayable from Settings at any time.
  const [welcomeOpen, setWelcomeOpen] = useState(
    () => localStorage.getItem("lens.welcome.v2.done") !== "1"
  );

  const toast = (message: string, kind: "ok" | "error" = "ok") => {
    const id = Date.now() + Math.random();
    setToasts((ts) => [...ts, { id, message, kind }]);
    window.setTimeout(() => setToasts((ts) => ts.filter((t) => t.id !== id)), 4000);
  };

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("lens.theme", theme);
  }, [theme]);

  useEffect(() => {
    // Full RTL mirroring (§9.16): document direction flips, not just text.
    document.documentElement.setAttribute("dir", isRTL(lang) ? "rtl" : "ltr");
    document.documentElement.setAttribute("lang", lang);
    localStorage.setItem("lens.lang", lang);
  }, [lang]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const value = useMemo<ShellState>(
    () => ({
      view, setView, lang, setLang, theme, setTheme, activeSetId, setActiveSetId,
      t: STRINGS[lang],
      engine: { url: engineUrl(), version: LENS_VERSION },
      toast,
      welcomeOpen,
      openWelcome: () => setWelcomeOpen(true),
      closeWelcome: () => {
        setWelcomeOpen(false);
        localStorage.setItem("lens.welcome.v2.done", "1");
      },
    }),
    [view, lang, theme, activeSetId, welcomeOpen, toasts.length]
  );

  return (
    <Ctx.Provider value={value}>
      {children}
      {paletteOpen && <CommandPalette onClose={() => setPaletteOpen(false)} />}
      {welcomeOpen && <WelcomeFlow />}
      <ToastHost toasts={toasts} />
    </Ctx.Provider>
  );
}
