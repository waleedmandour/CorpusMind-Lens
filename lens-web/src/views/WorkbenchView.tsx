import { useEffect, useState } from "react";
import { useShell } from "../shell";
import { api, batteryExportUrl } from "../lib/api";
import { ExportButtons } from "../components/ui";

type Tab = "overview" | "set" | "measures" | "analysis";
const DIMS = ["visual_morphology", "attentional_framing", "shot_scale", "path_transition",
  "multimodal_integration"];

export function WorkbenchView() {
  const { t, activeSetId } = useShell();
  const [tab, setTab] = useState<Tab>("overview");
  const [images, setImages] = useState<any[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<any>(null);
  const [schema, setSchema] = useState<any>(null);
  const [dim, setDim] = useState("shot_scale");
  const [battery, setBattery] = useState<any>(null);
  const [vg, setVg] = useState<any>(null);
  const [frameworks, setFrameworks] = useState<any[]>([]);
  const [framework, setFramework] = useState("kress-van-leeuwen");
  const [claims, setClaims] = useState<any>(null);
  const [busy, setBusy] = useState("");

  const loadImages = () => {
    if (activeSetId) api.listImages(activeSetId).then(setImages).catch(() => undefined);
  };

  useEffect(() => {
    loadImages();
    api.annotationSchema().then(setSchema).catch(() => undefined);
    api.discourseFrameworks().then(setFrameworks).catch(() => undefined);
    const iv = setInterval(loadImages, 3000); // background-progress polling
    return () => clearInterval(iv);
  }, [activeSetId]);

  useEffect(() => {
    if (!selected) return;
    api.getAnalysis(selected).then(setAnalysis).catch(() => undefined);
  }, [selected]);

  const runBattery = async () => {
    if (!activeSetId) return;
    setBusy("battery");
    try {
      setBattery(await api.fullBattery(activeSetId, dim));
    } finally {
      setBusy("");
    }
  };

  const runVG = async () => {
    if (!selected) return;
    setBusy("vg");
    try {
      setVg(await api.visualGrammar(selected));
    } finally {
      setBusy("");
    }
  };

  const runLens = async () => {
    if (!selected) return;
    setBusy("lens");
    try {
      setClaims(await api.discourseAnalyse(selected, framework, "heuristic"));
    } finally {
      setBusy("");
    }
  };

  const setAnnotation = async (dimId: string, value: string) => {
    if (!selected) return;
    const current = analysis?.ocr ? await api.getAnnotations(selected) : { dimensions: {} };
    const block = (current.dimensions?.[dimId]) ?? { values: [], note: "" };
    const values = block.values.includes(value)
      ? block.values.filter((v: string) => v !== value)
      : [...block.values, value];
    await api.setAnnotations(selected, { dimensions: { [dimId]: { values, note: block.note ?? "" } }, tags: [] });
    setBusy("annotations");
    api.getAnalysis(selected).then(setAnalysis).finally(() => setBusy(""));
  };

  const dims = schema?.dimensions ?? [];

  return (
    <div>
      <h2>{t.nav.workbench}</h2>
      {!activeSetId && <div className="notice">← {t.nav.imageSets}</div>}
      {activeSetId && (
        <>
          <div className="tabs" role="tablist">
            {([["overview", t.workbench.tabOverview], ["set", t.workbench.tabSet],
               ["measures", t.workbench.tabMeasures], ["analysis", t.workbench.tabAnalysis]] as [Tab, string][])
              .map(([id, label]) => (
                <button key={id} role="tab" aria-selected={tab === id}
                        className={tab === id ? "active" : ""} onClick={() => setTab(id)}>
                  {label}
                </button>
              ))}
          </div>

          {tab === "overview" && (
            <div className="card">
              <h3>{t.nav.imageSets}</h3>
              <p className="muted">
                {images.length} {t.common.images} ·{" "}
                {images.filter((i) => i.status === "ready").length} {t.common.ready} ·{" "}
                {images.filter((i) => i.status === "processing").length} {t.common.processing}
              </p>
              <div className="progress">
                <div style={{
                  width: `${images.length
                    ? (images.filter((i) => i.status === "ready").length / images.length) * 100
                    : 0}%`,
                }} />
              </div>
              <div className="row" style={{ marginTop: 12 }}>
                {images.map((img) => (
                  <button
                    key={img.id}
                    onClick={() => setSelected(img.id)}
                    style={{
                      border: selected === img.id ? "2px solid var(--lens-accent)" : "1px solid var(--border)",
                      borderRadius: 8, padding: 4, background: "var(--surface)",
                    }}
                    title={`${img.filename} — ${img.status}`}
                  >
                    <img src={api.imageThumbnail(img.id)} alt={img.filename}
                         style={{ width: 84, height: 84, objectFit: "cover", borderRadius: 6 }} />
                    <div style={{ fontSize: 10, color: "var(--text-dim)" }}>{img.status}</div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {tab === "set" && selected && analysis && (
            <>
              <div className="card">
                <h3>{selected} — {analysis.status}</h3>
                <dl className="kv">
                  <dt>OCR</dt>
                  <dd>
                    {analysis.ocr?.engine} · conf {analysis.ocr?.confidence} ·{" "}
                    {analysis.ocr?.word_count} words — {analysis.ocr?.text?.slice(0, 120) || "—"}
                  </dd>
                  <dt>Colour</dt>
                  <dd>
                    {(analysis.colour?.dominant_colours ?? []).map((c: any) => (
                      <span key={c.hex} title={c.hex}
                            style={{ display: "inline-block", width: 16, height: 16,
                                     background: c.hex, borderRadius: 4, marginInlineEnd: 4 }} />
                    ))}
                    warm {analysis.colour?.warm_cold_balance} · bright {analysis.colour?.brightness}
                  </dd>
                  <dt>Info value</dt>
                  <dd className="evidence">
                    {JSON.stringify(analysis.composition?.information_value ?? {})}
                  </dd>
                  <dt>Detections</dt>
                  <dd>
                    {(analysis.detections ?? []).map((d: any, i: number) => (
                      <span className="chip" key={i}>{d.label} {d.confidence}</span>
                    )) || "—"}
                  </dd>
                  <dt>Typography</dt>
                  <dd className="evidence">{JSON.stringify(analysis.typography ?? {})}</dd>
                </dl>
              </div>

              <div className="card">
                <h3>{t.workbench.dimension} — annotate (multi-select)</h3>
                {dims.map((d: any) => (
                  <div key={d.id} style={{ marginBottom: 10 }}>
                    <strong>{d.label_en}</strong>{" "}
                    <span className="muted" style={{ fontSize: 12 }}>{d.label_ar}</span>
                    <div className="row" style={{ marginTop: 4 }}>
                      {d.categories.map((c: any) => {
                        const active = (analysis && null) || false; // values shown from analysis below
                        void active;
                        return (
                          <button
                            key={c.id}
                            className="btn secondary"
                            style={{ fontSize: 12, padding: "4px 10px" }}
                            onClick={() => setAnnotation(d.id, c.id)}
                            title={c.description_en}
                          >
                            {c.label_en}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
                <button className="btn secondary" onClick={() => api.bulkTag(activeSetId, ["reviewed"])}>
                  Bulk tag “reviewed”
                </button>
              </div>
            </>
          )}

          {tab === "measures" && (
            <div className="card">
              <h3>{t.workbench.tabMeasures}</h3>
              <div className="row" style={{ marginBottom: 10 }}>
                <select value={dim} onChange={(e) => setDim(e.target.value)}
                        style={{ padding: 8, borderRadius: 8, border: "1px solid var(--border)",
                                 background: "var(--surface-2)" }}>
                  {DIMS.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
                <button className="btn" onClick={runBattery} disabled={busy === "battery"}>
                  {busy === "battery" ? t.common.processing : t.workbench.run}
                </button>
              </div>
              {battery && (
                <>
                  <h3 style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
                    <span>{t.workbench.frequency}</span>
                    <ExportButtons
                      build={(fmt) => ({
                        url: batteryExportUrl(activeSetId, "frequency", fmt, { dim }),
                        filename: `lens-battery-frequency-${activeSetId}.${fmt}`,
                      })}
                    />
                  </h3>
                  <table className="data">
                    <thead><tr><th>category</th><th>count</th><th>%</th></tr></thead>
                    <tbody>
                      {(battery.frequency?.profile ?? []).map((r: any) => (
                        <tr key={r.category}><td>{r.category}</td><td>{r.count}</td><td>{r.percent}</td></tr>
                      ))}
                    </tbody>
                  </table>
                  <h3 style={{ marginTop: 14, display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
                    <span>{t.workbench.diversity}</span>
                    <ExportButtons
                      build={(fmt) => ({
                        url: batteryExportUrl(activeSetId, "diversity", fmt, { dim }),
                        filename: `lens-battery-diversity-${activeSetId}.${fmt}`,
                      })}
                    />
                  </h3>
                  <p className="evidence">
                    TTR {battery.diversity?.ttr} · Guiraud R {battery.diversity?.guiraud_r} ·
                    MATTR {battery.diversity?.mattr} · STTR {battery.diversity?.sttr}
                  </p>
                  <h3 style={{ marginTop: 14, display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
                    <span>{t.workbench.ngrams}</span>
                    <ExportButtons
                      build={(fmt) => ({
                        url: batteryExportUrl(activeSetId, "ngrams", fmt, { dim, min_count: 1 }),
                        filename: `lens-battery-ngrams-${activeSetId}.${fmt}`,
                      })}
                    />
                  </h3>
                  <table className="data">
                    <tbody>
                      {(battery.ngrams?.grams ?? []).map((g: any, i: number) => (
                        <tr key={i}><td>{g.gram.join(" → ")}</td><td>{g.count}</td></tr>
                      ))}
                    </tbody>
                  </table>
                  <h3 style={{ marginTop: 14, display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
                    <span>{t.workbench.dispersion}</span>
                    <ExportButtons
                      build={(fmt) => ({
                        url: batteryExportUrl(activeSetId, "dispersion", fmt, { dim }),
                        filename: `lens-battery-dispersion-${activeSetId}.${fmt}`,
                      })}
                    />
                  </h3>
                  <table className="data">
                    <thead><tr><th>category</th><th>Juilland's D</th><th>Gries' DP</th><th>bins</th></tr></thead>
                    <tbody>
                      {(battery.dispersion?.rows ?? []).map((r: any) => (
                        <tr key={r.category}>
                          <td>{r.category}</td><td>{r.juillands_d}</td><td>{r.gries_dp}</td>
                          <td className="evidence">{r.per_bin.join(", ")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </div>
          )}

          {tab === "analysis" && selected && (
            <>
              <div className="card">
                <h3>Kress & van Leeuwen — Visual Grammar</h3>
                <button className="btn" onClick={runVG} disabled={busy === "vg"}>
                  {busy === "vg" ? t.common.processing : t.workbench.run}
                </button>
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
              </div>

              <div className="card">
                <h3>{t.workbench.tabAnalysis} — discourse lenses (heuristic mode)</h3>
                <div className="row" style={{ marginBottom: 10 }}>
                  <select value={framework} onChange={(e) => setFramework(e.target.value)}
                          style={{ padding: 8, borderRadius: 8, border: "1px solid var(--border)",
                                   background: "var(--surface-2)" }}>
                    {frameworks.map((f) => <option key={f.id} value={f.id}>{f.full_name}</option>)}
                  </select>
                  <button className="btn" onClick={runLens} disabled={busy === "lens"}>
                    {busy === "lens" ? t.common.processing : t.workbench.run}
                  </button>
                </div>
                {claims?.claims?.map((c: any, i: number) => (
                  <p key={i} style={{ margin: "6px 0" }}>
                    {c.claim}
                    <br />
                    <span className="evidence">{c.evidence.join(" · ")}</span>{" "}
                    <span className="chip">conf {c.confidence}</span>
                    {c.ungrounded && <span className="chip ungrounded">{t.workbench.ungroundedFlag}</span>}
                    {claims.person_descriptive_redacted && (
                      <span className="chip ungrounded">redacted (consent gate)</span>
                    )}
                  </p>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
