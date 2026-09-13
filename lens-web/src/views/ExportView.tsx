import { useEffect, useState } from "react";
import { useShell } from "../shell";
import { api, downloadEngineFile, engineUrl } from "../lib/api";
import { ExportButtons } from "../components/ui";

/**
 * Export & Methods (v0.3) — one page for everything that leaves Lens:
 * the image-set archive, the extracted <doc>-marked corpus for external
 * tools, the battery tables, and the auto-drafted Methods section.
 */
const DIMS = ["visual_morphology", "attentional_framing", "shot_scale", "path_transition",
  "multimodal_integration"];

function SetPicker() {
  const { t, activeSetId, setActiveSetId } = useShell();
  const [sets, setSets] = useState<any[]>([]);
  useEffect(() => {
    (async () => {
      const ps = await api.listProjects().catch(() => []);
      const all: any[] = [];
      await Promise.all(ps.map(async (p) => (await api.listImageSets(p.id)).forEach((s: any) => all.push(s))));
      setSets(all);
    })();
  }, []);
  return (
    <select value={activeSetId ?? ""} onChange={(e) => setActiveSetId(e.target.value)}
            style={{ padding: 8, borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface-2)" }}
            aria-label={t.common.selectSet}>
      <option value="" disabled>{t.common.selectSet}…</option>
      {sets.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
    </select>
  );
}

export function ExportView() {
  const { t, activeSetId: sid, toast } = useShell();
  const [dim, setDim] = useState("shot_scale");
  const [methods, setMethods] = useState<string | null>(null);
  const [methodsBusy, setMethodsBusy] = useState(false);

  const grab = (url: string, filename: string) => {
    if (!sid) return;
    downloadEngineFile(url, filename)
      .then(() => toast(`${t.exportView.done}: ${filename}`))
      .catch((e: any) => toast(`${t.common.error}: ${e?.message ?? e}`, "error"));
  };

  const draftMethods = async () => {
    if (!sid) return;
    setMethodsBusy(true);
    try {
      const r = await api.methodsSection(sid);
      setMethods(typeof r === "string" ? r : (r.text ?? r.body ?? JSON.stringify(r, null, 2)));
    } catch (e: any) {
      toast(`${t.common.error}: ${e?.message ?? e}`, "error");
    } finally {
      setMethodsBusy(false);
    }
  };

  return (
    <div>
      <h2>{t.exportView.title}</h2>
      <p className="muted" style={{ maxWidth: 760, marginTop: 0 }}>{t.exportView.intro}</p>

      <div className="card">
        <div className="row" style={{ flexWrap: "wrap" }}>
          <SetPicker />
        </div>
        {!sid && <p className="notice" style={{ marginTop: 10, marginBottom: 0 }}>{t.vision.needSet}</p>}
      </div>

      {sid && (
        <>
          <div className="card">
            <h3>{t.exportView.setArchive}</h3>
            <p className="muted" style={{ fontSize: 13 }}>{t.exportView.setArchiveDesc}</p>
            <ExportButtons
              build={(f) => ({
                url: `${engineUrl()}/api/v1/imagesets/${sid}/export?format=${f}`,
                filename: `lens-set-${sid}.${f}`,
              })}
            />
          </div>

          <div className="card">
            <h3>{t.exportView.corpus}</h3>
            <p className="muted" style={{ fontSize: 13 }}>{t.exportView.corpusDesc}</p>
            <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
              <span className="muted" style={{ fontSize: 12 }}>{t.exportView.formats}:</span>
              {["txt", "json"].map((f) => (
                <button key={f} className="btn secondary" style={{ padding: "3px 10px", fontSize: 12 }}
                        onClick={() => grab(
                          `${engineUrl()}/api/v1/imagesets/${sid}/ocrtools/export-corpus?format=${f}`,
                          `lens-corpus-${sid}.${f}`)}>
                  {f.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          <div className="card">
            <h3>{t.exportView.battery}</h3>
            <p className="muted" style={{ fontSize: 13 }}>{t.exportView.batteryDesc}</p>
            <div className="row" style={{ marginBottom: 10 }}>
              <select value={dim} onChange={(e) => setDim(e.target.value)}
                      style={{ padding: 8, borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface-2)" }}>
                {DIMS.map((d) => <option key={d} value={d}>{d.replace(/_/g, " ")}</option>)}
              </select>
            </div>
            <div className="row" style={{ gap: 14, flexWrap: "wrap" }}>
              {["frequency", "diversity", "ngrams", "dispersion"].map((kind) => (
                <span key={kind} className="row" style={{ gap: 6 }}>
                  <strong style={{ fontSize: 13 }}>{kind}</strong>
                  <ExportButtons
                    build={(f) => ({
                      url: `${engineUrl()}/api/v1/imagesets/${sid}/battery-export/${kind}?format=${f}&dim=${dim}`,
                      filename: `lens-battery-${kind}-${sid}.${f}`,
                    })}
                  />
                </span>
              ))}
            </div>
          </div>

          <div className="card">
            <h3>{t.exportView.methods}</h3>
            <p className="muted" style={{ fontSize: 13 }}>{t.exportView.methodsDesc}</p>
            <button className="btn" onClick={draftMethods} disabled={methodsBusy}>
              {methodsBusy ? t.common.processing : t.exportView.methodsRun}
            </button>
            {methods && (
              <pre style={{
                marginTop: 10, whiteSpace: "pre-wrap", background: "var(--surface-2)",
                border: "1px solid var(--border)", borderRadius: 10, padding: 12, fontSize: 13,
                lineHeight: 1.6, maxHeight: 340, overflowY: "auto",
              }}>{methods}</pre>
            )}
          </div>
        </>
      )}
    </div>
  );
}
