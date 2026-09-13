import { useEffect, useState } from "react";
import { ShellProvider, useShell, type ViewId } from "./shell";
import { HomeView } from "./views/HomeView";
import { ImagesView } from "./views/ImagesView";
import { TextAnalysisView } from "./views/TextAnalysisView";
import { VisionAnalysisView } from "./views/VisionAnalysisView";
import { SocialView } from "./views/SocialView";
import { AssistantView } from "./views/AssistantView";
import { ExportView } from "./views/ExportView";
import { GuideView } from "./views/GuideView";
import { AboutView } from "./views/AboutView";
import { SettingsView } from "./views/SettingsView";
import { api, discoverEnginePort, engineUrl } from "./lib/api";
import { startTaskBar } from "./state/taskbar";
import { TaskBar } from "./components/TaskBar";

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
  home: "M3 10.5 12 3l9 7.5M5 9.5V21h5v-6h4v6h5V9.5",
  images: "M3 5h13v11H3zM16 8h5v11H8M6 9l3 3 2.5-2.5L15 14",
  text: "M4 5h16M4 10h10M4 15h13M4 20h7",
  vision: "M9 3h6M10 3v5.5L4.5 18a2 2 0 0 0 1.8 3h11.4a2 2 0 0 0 1.8-3L14 8.5V3M7.5 14h9",
  social: "M21 12a8 8 0 0 1-8 8H4l2.4-2.9A8 8 0 1 1 21 12zM8 10h8M8 13.5h5",
  assistant: "M12 3l1.9 4.6L18.5 9l-4.6 1.9L12 15.5l-1.9-4.6L5.5 9l4.6-1.4zM19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9z",
  export: "M12 3v12M7 10l5 5 5-5M4 21h16",
  settings: "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM19 12a7 7 0 0 0-.1-1.2l2-1.6-2-3.4-2.4 1a7 7 0 0 0-2-1.2L14 3h-4l-.5 2.6a7 7 0 0 0-2 1.2l-2.4-1-2 3.4 2 1.6A7 7 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.6 2 3.4 2.4-1a7 7 0 0 0 2 1.2L10 21h4l.5-2.6a7 7 0 0 0 2-1.2l2.4 1 2-3.4-2-1.6c.1-.4.1-.8.1-1.2z",
  guide: "M4 4h7a2 2 0 0 1 2 2v14a2 2 0 0 0-2-2H4zM20 4h-7a2 2 0 0 0-2 2v14a2 2 0 0 1 2-2h7z",
  about: "M12 8h.01M11 12h1v4h1M12 21a9 9 0 1 1 0-18 9 9 0 0 1 0 18z",
};

/**
 * The v0.3 sidebar: the FULL functional menu, grouped in research-workflow
 * order. Nothing is hidden behind tabs-of-tabs — the user picks a tool and
 * goes. (User decision, v0.3 plan: "provide full functional menu, and the
 * user chooses what to do".)
 */
function Sidebar() {
  const { t, view, setView, openWelcome, engine } = useShell();
  const groups: { label: string; items: [ViewId, string][] }[] = [
    { label: t.navGroups.start, items: [["home", t.nav.home]] },
    {
      label: t.navGroups.build,
      items: [["images", t.nav.images], ["social", t.nav.social]],
    },
    {
      label: t.navGroups.analyse,
      items: [["text", t.nav.text], ["vision", t.nav.vision], ["assistant", t.nav.assistant]],
    },
    { label: t.navGroups.share, items: [["export", t.nav.export]] },
    {
      label: t.navGroups.help,
      items: [["settings", t.nav.settings], ["guide", t.nav.guide], ["about", t.nav.about]],
    },
  ];
  return (
    <nav className="lens-sidebar lens-sidebar-pro" aria-label="Primary">
      {groups.map((g) => (
        <div key={g.label} className="lens-nav-group">
          <div className="lens-nav-group-label">{g.label}</div>
          {g.items.map(([id, label]) => (
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
        </div>
      ))}
      <div className="lens-sidebar-foot">
        <button className="lens-link" onClick={openWelcome} title={t.settings.replayWelcome}>
          {t.welcome.skip === "تخطٍّ" ? "دليل البدء" : "Getting started"}
        </button>
        <span className="muted" style={{ fontSize: 11 }}>
          v{engine.version}
        </span>
      </div>
    </nav>
  );
}

function Ribbon() {
  const { t, theme, setTheme, lang, setLang } = useShell();
  const [engineOk, setEngineOk] = useState<boolean | null>(null);
  useEffect(() => {
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
        {/* The official CorpusMind Lens artwork (same source as the desktop icon). */}
        <img src="/icon-64.png" alt="" aria-hidden />
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
      </div>
    </header>
  );
}

function Main() {
  const { view } = useShell();
  switch (view) {
    case "home":
      return <HomeView />;
    case "images":
      return <ImagesView />;
    case "text":
      return <TextAnalysisView />;
    case "vision":
      return <VisionAnalysisView />;
    case "social":
      return <SocialView />;
    case "assistant":
      return <AssistantView />;
    case "export":
      return <ExportView />;
    case "guide":
      return <GuideView />;
    case "about":
      return <AboutView />;
    case "settings":
      return <SettingsView />;
  }
}

export default function App() {
  useEffect(() => {
    // Adopt the port the desktop shell actually started the engine on
    // (8765 may be taken by a Companion engine or a stale process).
    discoverEnginePort();
    // Task bar: API error capture + 15 s health poll. Returns cleanup.
    return startTaskBar();
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
        <TaskBar />
      </div>
    </ShellProvider>
  );
}
