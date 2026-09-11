import { useEffect, useState } from "react";
import { ShellProvider, useShell } from "./shell";
import { OverviewView } from "./views/OverviewView";
import { ImageSetsView } from "./views/ImageSetsView";
import { WorkbenchView } from "./views/WorkbenchView";
import { AssistantView } from "./views/AssistantView";
import { SettingsView } from "./views/SettingsView";
import { api, ENGINE_URL } from "./lib/api";

function Ribbon() {
  const { t, view, setView, theme, setTheme, lang, setLang } = useShell();
  const [engineOk, setEngineOk] = useState<boolean | null>(null);
  useEffect(() => {
    api.health().then((h) => setEngineOk(h.status === "ok")).catch(() => setEngineOk(false));
  }, []);

  return (
    <header className="lens-ribbon">
      <div className="lens-brand">
        <img src="/icon-lens.svg" alt="" aria-hidden />
        <span>{t.app}</span>
        <span className="lens-badge">Lens</span>
      </div>
      <div className="row" style={{ marginInlineStart: "auto" }}>
        <span
          className="chip"
          title={engineOk ? `Engine OK at ${ENGINE_URL}` : "Engine unreachable"}
          style={{
            color: engineOk ? "var(--ok)" : "var(--danger)",
            border: `1px solid ${engineOk ? "var(--ok)" : "var(--danger)"}`,
          }}
        >
          {engineOk === null ? "…" : engineOk ? "● engine" : "● offline"}
        </span>
        <button className="btn secondary" onClick={() => setLang(lang === "en" ? "ar" : "en")}>
          {lang === "en" ? "العربية" : "English"}
        </button>
        <button
          className="btn secondary"
          aria-label={t.settings.theme}
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        >
          {theme === "dark" ? "☀" : "☾"}
        </button>
        <button className="btn secondary" onClick={() => setView(view)} title="Ctrl/⌘+K">
          ⌘K
        </button>
      </div>
    </header>
  );
}

function Sidebar() {
  const { t, view, setView } = useShell();
  const items: [string, any][] = [
    [t.nav.overview, "overview"],
    [t.nav.imageSets, "imagesets"],
    [t.nav.workbench, "workbench"],
    [t.nav.assistant, "assistant"],
    [t.nav.settings, "settings"],
  ];
  return (
    <nav className="lens-sidebar" aria-label="Primary">
      {items.map(([label, id]) => (
        <button
          key={id}
          className={view === id ? "active" : ""}
          onClick={() => setView(id as any)}
        >
          {label}
        </button>
      ))}
    </nav>
  );
}

function Main() {
  const { view } = useShell();
  switch (view) {
    case "overview":
      return <OverviewView />;
    case "imagesets":
      return <ImageSetsView />;
    case "workbench":
      return <WorkbenchView />;
    case "assistant":
      return <AssistantView />;
    case "settings":
      return <SettingsView />;
  }
}

export default function App() {
  return (
    <ShellProvider>
      <div className="lens-shell">
        <Ribbon />
        <div className="lens-body">
          <Sidebar />
          <main className="lens-main">
            <Main />
          </main>
        </div>
      </div>
    </ShellProvider>
  );
}
