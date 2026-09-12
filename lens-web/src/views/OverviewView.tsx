import { useEffect, useState } from "react";
import { useShell } from "../shell";
import { api } from "../lib/api";

export function OverviewView() {
  const { t, setActiveSetId, setView } = useShell();
  const [projects, setProjects] = useState<any[]>([]);
  const [name, setName] = useState("");
  const [sets, setSets] = useState<Record<string, any[]>>({});
  const [aiMissing, setAiMissing] = useState(false);
  const [bannerDismissed, setBannerDismissed] = useState(
    () => localStorage.getItem("lens.ai-banner-dismissed") === "1"
  );

  const refresh = async () => {
    const ps = await api.listProjects();
    setProjects(ps);
    const m: Record<string, any[]> = {};
    await Promise.all(
      ps.map(async (p) => {
        m[p.id] = await api.listImageSets(p.id);
      })
    );
    setSets(m);
  };
  useEffect(() => {
    refresh().catch(() => undefined);
    // Graceful no-AI state (v0.2): deterministic features work everywhere;
    // the banner just points at the Setup card when no backend answers.
    api.providersStatus()
      .then((s) => setAiMissing(!s.ollama.reachable && !s.lmstudio.reachable))
      .catch(() => setAiMissing(false));
  }, []);

  const dismiss = () => {
    localStorage.setItem("lens.ai-banner-dismissed", "1");
    setBannerDismissed(true);
  };

  return (
    <div>
      <h2>{t.overview.title}</h2>
      <p className="muted" style={{ maxWidth: 720 }}>{t.overview.intro}</p>

      {aiMissing && !bannerDismissed && (
        <div className="card" style={{ borderInlineStart: "4px solid #f59e0b" }}>
          <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap" }}>
            <span style={{ fontSize: 13, maxWidth: 640 }}>{t.settings.noAiBanner}</span>
            <span className="row">
              <button className="btn secondary" onClick={() => setView("settings")}>{t.nav.settings}</button>
              <button className="btn secondary" onClick={dismiss}>✕</button>
            </span>
          </div>
        </div>
      )}

      <div className="card">
        <h3>{t.overview.projects}</h3>
        <div className="row" style={{ marginBottom: 12 }}>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t.overview.newProject}
            aria-label={t.overview.newProject}
            style={{
              padding: "8px 10px", borderRadius: 8,
              border: "1px solid var(--border)", background: "var(--surface-2)",
            }}
          />
          <button
            className="btn"
            disabled={!name.trim()}
            onClick={async () => {
              await api.createProject(name.trim());
              setName("");
              refresh();
            }}
          >
            {t.common.create}
          </button>
        </div>

        {projects.map((p) => (
          <div key={p.id} style={{ marginBottom: 14 }}>
            <div className="row">
              <strong>{p.name}</strong>
              <span className="chip">{(sets[p.id] ?? []).length} {t.common.images}</span>
              <button
                className="btn secondary"
                onClick={async () => {
                  const s = await api.createImageSet({
                    project_id: p.id,
                    name: `${p.name} — ${new Date().toISOString().slice(0, 10)}`,
                  });
                  setActiveSetId(s.id);
                  setView("workbench");
                }}
              >
                {t.overview.createSet}
              </button>
            </div>
            {(sets[p.id] ?? []).map((s) => (
              <div className="row" key={s.id} style={{ marginInlineStart: 14, marginTop: 6 }}>
                <span>{s.name}</span>
                <button
                  className="btn secondary"
                  onClick={() => {
                    setActiveSetId(s.id);
                    setView("workbench");
                  }}
                >
                  {t.nav.workbench} →
                </button>
              </div>
            ))}
          </div>
        ))}
        {projects.length === 0 && (
          <p className="muted">{t.common.loading} / {t.overview.newProject} →</p>
        )}
      </div>
    </div>
  );
}
