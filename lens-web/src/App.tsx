import { useEffect, useState } from "react";
import { ShellProvider, useShell, type ViewId } from "./shell";
import { OverviewView } from "./views/OverviewView";
import { ImageSetsView } from "./views/ImageSetsView";
import { WorkbenchView } from "./views/WorkbenchView";
import { SocialView } from "./views/SocialView";
import { AssistantView } from "./views/AssistantView";
import { SettingsView } from "./views/SettingsView";
import { api, discoverEnginePort, engineUrl, shell } from "./lib/api";

/* Compact inline icon set (stroke follows currentColor; no icon dependency). */
function Icon({ d, size = 17 }: { d: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d={d} />
    </svg>
  );
}

const ICONS: Record<ViewId, string> = {
  overview: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z",
  imagesets: "M3 5h13v11H3zM16 8h5v11H8M6 9l3 3 2.5-2.5L15 14",
  workbench: "M9 3h6M10 3v5.5L4.5 18a2 2 0 0 0 1.8 3h11.4a2 2 0 0 0 1.8-3L14 8.5V3M7.5 14h9",
  social: "M21 12a8 8 0 0 1-8 8H4l2.4-2.9A8 8 0 1 1 21 12zM8 10h8M8 13.5h5",
  assistant: "M12 3l1.9 4.6L18.5 9l-4.6 1.9L12 15.5l-1.9-4.6L5.5 9l4.6-1.4zM19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9z",
  settings: "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM19 12a7 7 0 0 0-.1-1.2l2-1.6-2-3.4-2.4 1a7 7 0 0 0-2-1.2L14 3h-4l-.5 2.6a7 7 0 0 0-2 1.2l-2.4-1-2 3.4 2 1.6A7 7 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.6 2 3.4 2.4-1a7 7 0 0 0 2 1.2L10 21h4l.5-2.6a7 7 0 0 0 2-1.2l2.4 1 2-3.4-2-1.6c.1-.4.1-.8.1-1.2z",
};

function Ribbon() {
  const { t, view, setView, theme, setTheme, lang, setLang } = useShell();
  const [engineOk, setEngineOk] = useState<boolean | null>(null);
  useEffect(() => {
    // The engine boots asynchronously (PyInstaller first-run scans can take
    // tens of seconds), so poll with patience instead of a single strike.
    let alive = true;
    let tries = 0;
    const tick = async () => {
      if (!alive) return;
      try {
        const h = await api.health();
        if (alive) setEngineOk(h.status === "ok");
        return;
      } catch {
        tries += 1;
        if (alive && tries < 40) window.setTimeout(tick, 3000);
        else if (alive) setEngineOk(false);
      }
    };
    tick();
    return () => {
      alive = false;
    };
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
          title={engineOk ? `Engine OK at ${engineUrl()}` : "Engine unreachable"}
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
  const { t, view, setView, openWelcome, engine } = useShell();
  const items: [ViewId, string][] = [
    ["overview", t.nav.overview],
    ["imagesets", t.nav.imageSets],
    ["workbench", t.nav.workbench],
    ["social", t.nav.social],
    ["assistant", t.nav.assistant],
    ["settings", t.nav.settings],
  ];
  return (
    <nav className="lens-sidebar lens-sidebar-pro" aria-label="Primary">
      {items.map(([id, label]) => (
        <button
          key={id}
          className={view === id ? "active" : ""}
          onClick={() => setView(id as ViewId)}
          title={label}
        >
          <Icon d={ICONS[id]} />
          <span>{label}</span>
        </button>
      ))}
      <div className="lens-sidebar-foot">
        <button className="lens-link" onClick={openWelcome} title={t.settings.replayWelcome}>
          {t.welcome.skip === "تخطّي" ? "دليل البدء" : "Getting started"}
        </button>
        <span className="muted" style={{ fontSize: 11 }}>
          v{engine.version}
        </span>
      </div>
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
    case "social":
      return <SocialView />;
    case "assistant":
      return <AssistantView />;
    case "settings":
      return <SettingsView />;
  }
}

export default function App() {
  useEffect(() => {
    // Adopt the port the desktop shell actually started the engine on
    // (8765 may be taken by a Companion engine or a stale process).
    discoverEnginePort();
  }, []);
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
