import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { isRTL, STRINGS, type Lang } from "./i18n/strings";
import { ENGINE_URL, LENS_VERSION } from "./lib/api";

type ViewId = "overview" | "imagesets" | "workbench" | "assistant" | "settings";

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

export function ShellProvider({ children }: { children: React.ReactNode }) {
  const [view, setView] = useState<ViewId>("overview");
  const [lang, setLang] = useState<Lang>(() =>
    (localStorage.getItem("lens.lang") as Lang) || "en");
  const [theme, setTheme] = useState<"light" | "dark">(() =>
    (localStorage.getItem("lens.theme") as "light" | "dark") ||
    (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
  const [activeSetId, setActiveSetId] = useState<string | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);

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
      engine: { url: ENGINE_URL, version: LENS_VERSION },
    }),
    [view, lang, theme, activeSetId]
  );

  return (
    <Ctx.Provider value={value}>
      {children}
      {paletteOpen && <CommandPalette onClose={() => setPaletteOpen(false)} />}
    </Ctx.Provider>
  );
}
