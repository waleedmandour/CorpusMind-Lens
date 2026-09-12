import { useEffect, useRef, useState } from "react";
import { useShell } from "../shell";
import { api, isDesktopShell, shell } from "../lib/api";

export function OverviewView() {
  const { t, setActiveSetId, setView, toast } = useShell();
  const [projects, setProjects] = useState<any[]>([]);
  const [name, setName] = useState("");
  const [sets, setSets] = useState<Record<string, any[]>>({});
  const [aiMissing, setAiMissing] = useState(false);
  const [bannerDismissed, setBannerDismissed] = useState(
    () => localStorage.getItem("lens.ai-banner-dismissed") === "1"
  );
  const [engineDown, setEngineDown] = useState(false);
  const [checking, setChecking] = useState(false);
  const aliveRef = useRef(true);

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

  // Reachability probe: silent while the sidecar boots (Defender first-run
  // scans can take tens of seconds), then an explicit, actionable banner.
  const probe = async (announce: boolean) => {
    setChecking(true);
    let ok = false;
    for (let i = 0; i < 8 && aliveRef.current; i++) {
      try {
        await api.health();
        ok = true;
        break;
      } catch {
        await new Promise((r) => setTimeout(r, 1500));
      }
    }
    if (!aliveRef.current) return;
    setEngineDown(!ok);
    setChecking(false);
    if (ok && announce) {
      toast("Engine connected");
      refresh().catch(() => undefined);
    }
  };

  useEffect(() => {
    aliveRef.current = true;
    probe(false);
    api.providersStatus()
      .then((s) => setAiMissing(!s.ollama.reachable && !s.lmstudio.reachable))
      .catch(() => setAiMissing(false));
    return () => {
      aliveRef.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const dismiss = () => {
    localStorage.setItem("lens.ai-banner-dismissed", "1");
    setBannerDismissed(true);
  };

  return (
    <div>
      <h2>{t.overview.title}</h2>
      <p className="muted" style={{ maxWidth: 720 }}>{t.overview.intro}</p>

      {engineDown && (
        <div className="card" style={{ borderInlineStart: "4px solid var(--danger, #b91c1c)" }}>
          <strong style={{ display: "block", marginBottom: 6 }}>{t.offline.title}</strong>
          <p className="muted" style={{ fontSize: 13, maxWidth: 680, marginTop: 0, lineHeight: 1.6 }}>
            {t.offline.body}
          </p>
          <div className="row" style={{ flexWrap: "wrap" }}>
            <button className="btn" disabled={checking} onClick={() => probe(true)}>
              {checking ? t.offline.starting : t.offline.retry}
            </button>
            {isDesktopShell() && (
              <button
                className="btn secondary"
                disabled={checking}
                onClick={async () => {
                  try {
                    await shell.startEngine();
                  } catch {
                    /* probe reports the outcome */
                  }
                  probe(true);
                }}
              >
                {t.offline.startEngine}
              </button>
            )}
          </div>
          <p className="muted" style={{ fontSize: 12, marginBottom: 0 }}>{t.offline.logHint}</p>
        </div>
      )}

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
              try {
                await api.createProject(name.trim());
                setName("");
                await refresh();
              } catch (e: any) {
                toast(`${t.common.error}: ${e?.message ?? e}. ${t.offline.title}.`, "error");
              }
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
