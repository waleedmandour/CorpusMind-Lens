import { useEffect, useState } from "react";
import { useShell } from "../shell";
import { api, batteryExportUrl } from "../lib/api";
import { ExportButtons, RowsTable, EmptyState } from "../components/ui";
/**
 * Vision Analysis (v0.3) — the analysis half of the old Workbench, on its
 * own page: the statistical battery over visual annotations, Kress & van
 * Leeuwen's visual grammar, and the twelve discourse lenses.
 * (Corpus building and annotation live on the Images page.)
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

export function VisionAnalysisView() {
  const { t, activeSetId: sid } = useShell();
  const [tab, setTab] = useState<"measures" | "grammar" | "lenses">("measures");
  const [images, setImages] = useState<any[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<any>(null);
  const [dim, setDim] = useState("shot_scale");
  const [battery, setBattery] = useState<any>(null);
  const [busy, setBusy] = useState("");
  const [vg, setVg] = useState<any>(null);
  const [frameworks, setFrameworks] = useState<any[]>([]);
  const [framework, setFramework] = useState("kress-van-leeuwen");
  const [claims, setClaims] = useState<any>(null);
  // v0.3.2: the discourse lens now exposes BOTH modes in the UI. The engine
  // always supported mode=llm; the view previously hard-coded "heuristic",
  // so the local-LLM interpretation was silently unreachable.
  const [mode, setMode] = useState<"heuristic" | "llm">("heuristic");
  const [chatModel, setChatModel] = useState("");
  // v0.3.2: inline, actionable run errors (previously unhandled rejections).
  const [runError, setRunError] = useState<{ where: string; message: string } | null>(null);

  useEffect(() => {
    api.modelDefaults().then((s) => setChatModel(s?.chat_model ?? "")).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!sid) return;
    setSelected(null);
    setAnalysis(null);
    setBattery(null);
    setVg(null);
    setClaims(null);
    const load = () => api.listImages(sid).then(setImages).catch(() => undefined);
    load();
    api.discourseFrameworks().then(setFrameworks).catch(() => undefined);
    const iv = setInterval(load, 3000);
    return () => clearInterval(iv);
  }, [sid]);

  useEffect(() => {
    if (!selected) return;
    api.getAnalysis(selected).then(setAnalysis).catch(() => undefined);
  }, [selected]);

  const runBattery = async () => {
    if (!sid) return;
    setBusy("battery");
    setRunError(null);
    try {
      setBattery(await api.fullBattery(sid, dim));
    } catch (e: any) {
      setRunError({ where: "battery", message: String(e?.message ?? e) });
    } finally {
      setBusy("");
    }
  };

  const runVG = async () => {
    if (!selected) return;
    setBusy("vg");
    setRunError(null);
    try {
      setVg(await api.visualGrammar(selected));
    } catch (e: any) {
      setRunError({ where: "vg", message: String(e?.message ?? e) });
    } finally {
      setBusy("");
    }
  };

  const runLens = async () => {
    if (!selected) return;
    setBusy("lens");
    setRunError(null);
    try {
      setClaims(await api.discourseAnalyse(selected, framework, mode));
    } catch (e: any) {
      const msg = String(e?.message ?? e);
      setRunError({
        where: "lens",
        message: mode === "llm"
          ? `${t.vision.llmError} (${msg})`
          : msg,
      });
    } finally {
      setBusy("");
    }
  };

  const ready = images.filter((i) => i.status === "ready");

  return (
    <div>
      <h2>{t.vision.title}</h2>
      <p className="muted" style={{ maxWidth: 760, marginTop: 0 }}>{t.vision.intro}</p>

      <div className="card">
        <div className="row" style={{ flexWrap: "wrap" }}>
          <SetPicker />
          {sid && (
            <select value={selected ?? ""} onChange={(e) => setSelected(e.target.value || null)}
                    style={{ padding: 8, borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface-2)" }}>
              <option value="">{t.images.gallery} ({ready.length}/{images.length})</option>
              {ready.map((img) => (
                <option key={img.id} value={img.id}>{img.filename}</option>
              ))}
            </select>
          )}
        </div>
        {!sid && <p className="notice" style={{ marginTop: 10, marginBottom: 0 }}>{t.vision.needSet}</p>}
      </div>

      {sid && (
        <>
          <div className="tabs" role="tablist">
            {([["measures", t.vision.tabMeasures], ["grammar", t.vision.tabGrammar],
                ["lenses", t.vision.tabLenses]] as const).map(([id, label]) => (
              <button key={id} role="tab" aria-selected={tab === id}
                      className={tab === id ? "active" : ""} onClick={() => setTab(id)}>
                {label}
              </button>
            ))}
          </div>

          {tab === "measures" && (
            <div className="card">
              <h3>{t.workbench.tabMeasures}</h3>
              <div className="row" style={{ marginBottom: 10 }}>
                <select value={dim} onChange={(e) => setDim(e.target.value)}
                        style={{ padding: 8, borderRadius: 8, border: "1px solid var(--border)",
                                 background: "var(--surface-2)" }}>
                  {DIMS.map((d) => <option key={d} value={d}>{d.replace(/_/g, " ")}</option>)}
                </select>
                <button className="btn" onClick={runBattery} disabled={busy === "battery"}>
                  {busy === "battery" ? t.common.processing : t.workbench.run}
                </button>
              </div>
              {runError?.where === "battery" && (
                <p className="notice" style={{ marginTop: 8, marginBottom: 10 }} role="alert">{runError.message}</p>
              )}
              {battery && (
                <>
                  <h3 style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
                    <span>{t.workbench.frequency}</span>
                    <ExportButtons
                      build={(fmt) => ({
                        url: batteryExportUrl(sid!, "frequency", fmt, { dim }),
                        filename: `lens-battery-frequency-${sid}.${fmt}`,
                      })}
                    />
                  </h3>
                  <RowsTable
                    columns={[
                      { key: "category", label: t.workbench.dimension },
                      { key: "count", label: t.text.freq, align: "end" },
                      { key: "percent", label: "%", align: "end" },
                    ]}
                    rows={battery.frequency?.profile ?? []}
                  />
                  <h3 style={{ marginTop: 14 }}>{t.workbench.diversity}</h3>
                  <p className="evidence">
                    TTR {battery.diversity?.ttr} · Guiraud R {battery.diversity?.guiraud_r} ·
                    MATTR {battery.diversity?.mattr} · STTR {battery.diversity?.sttr}
                  </p>
                  <h3 style={{ marginTop: 14, display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
                    <span>{t.workbench.ngrams}</span>
                    <ExportButtons
                      build={(fmt) => ({
                        url: batteryExportUrl(sid!, "ngrams", fmt, { dim, min_count: 1 }),
                        filename: `lens-battery-ngrams-${sid}.${fmt}`,
                      })}
                    />
                  </h3>
                  <RowsTable
                    columns={[{ key: "gram", label: "n-gram" }, { key: "count", label: t.text.freq, align: "end" }]}
                    rows={(battery.ngrams?.grams ?? []).map((g: any) => ({ gram: g.gram.join(" → "), count: g.count }))}
                    max={30}
                  />
                  <h3 style={{ marginTop: 14, display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
                    <span>{t.workbench.dispersion}</span>
                    <ExportButtons
                      build={(fmt) => ({
                        url: batteryExportUrl(sid!, "dispersion", fmt, { dim }),
                        filename: `lens-battery-dispersion-${sid}.${fmt}`,
                      })}
                    />
                  </h3>
                  <RowsTable
                    columns={[
                      { key: "category", label: t.workbench.dimension },
                      { key: "juillands_d", label: "D", align: "end" },
                      { key: "gries_dp", label: "DP", align: "end" },
                    ]}
                    rows={(battery.dispersion?.rows ?? []).map((r: any) => ({
                      ...r, bins: undefined, per_bin: undefined,
                    }))}
                  />
                </>
              )}
            </div>
          )}

          {tab === "grammar" && (
            <div className="card">
              <h3>{t.vision.vgTitle}</h3>
              {!selected ? (
                <EmptyState glyph="◎" title={t.vision.needSet} />
              ) : (
                <>
                  <button className="btn" onClick={runVG} disabled={busy === "vg"}>
                    {busy === "vg" ? t.common.processing : t.vision.vgRun}
                  </button>
                  {runError?.where === "vg" && (
                    <p className="notice" style={{ marginTop: 8 }} role="alert">{runError.message}</p>
                  )}
                  {vg && (
                    <div style={{ marginTop: 10 }}>
                      {Object.entries(vg.metafunctions).map(([mf, list]: [string, any]) => (
                        <div key={mf} style={{ marginBottom: 8 }}>
                          <strong>{mf}</strong>
                          {list.map((c: any, i: number) => (
                            <p key={i} style={{ margin: "4px 0" }}>
                              {c.claim}
                              <br />
                              <span className="evidence">{c.evidence.join(" · ")}</span>{" "}
                              <span className="chip">conf {c.confidence}</span>
                            </p>
                          ))}
                        </div>
                      ))}
                      <p className="muted" style={{ fontSize: 12 }}>{vg.explanation}</p>
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {tab === "lenses" && (
            <div className="card">
              <h3>{t.vision.tabLenses}</h3>
              {!selected ? (
                <EmptyState glyph="⚖" title={t.vision.needSet} />
              ) : (
                <>
                  <div className="row" style={{ marginBottom: 10, flexWrap: "wrap" }}>
                    <select value={framework} onChange={(e) => setFramework(e.target.value)}
                            style={{ padding: 8, borderRadius: 8, border: "1px solid var(--border)",
                                     background: "var(--surface-2)", minWidth: 220 }}
                            aria-label={t.vision.framework}>
                      {frameworks.map((f) => <option key={f.id} value={f.id}>{f.full_name}</option>)}
                    </select>
                    {/* v0.3.2: heuristic vs local-LLM mode, explicit and labelled. */}
                    <select value={mode} onChange={(e) => setMode(e.target.value as "heuristic" | "llm")}
                            style={{ padding: 8, borderRadius: 8, border: "1px solid var(--border)",
                                     background: "var(--surface-2)" }}
                            aria-label={t.vision.mode}>
                      <option value="heuristic">{t.vision.modeHeuristic}</option>
                      <option value="llm">{t.vision.modeLlm}</option>
                    </select>
                    {mode === "llm" && chatModel && (
                      <span className="chip" title={t.settings.mdChat}>
                        {chatModel}
                      </span>
                    )}
                    <button className="btn" onClick={runLens} disabled={busy === "lens"}>
                      {busy === "lens" ? t.common.processing : t.workbench.run}
                    </button>
                  </div>
                  {mode === "llm" && (
                    <p className="muted" style={{ fontSize: 12, marginTop: 0 }}>
                      {t.vision.llmModeNote}
                    </p>
                  )}
                  {runError?.where === "lens" && (
                    <p className="notice" style={{ marginTop: 8 }} role="alert">{runError.message}</p>
                  )}
                  {claims?.claims?.map((c: any, i: number) => (
                    <p key={i} style={{ margin: "6px 0" }}>
                      {c.claim}
                      <br />
                      <span className="evidence">{c.evidence.join(" · ")}</span>{" "}
                      <span className="chip">conf {c.confidence}</span>
                      {c.ungrounded && <span className="chip ungrounded">{t.workbench.ungroundedFlag}</span>}
                      {claims.person_descriptive_redacted && (
                        <span className="chip ungrounded">{t.vision.consentRedacted}</span>
                      )}
                    </p>
                  ))}
                </>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
