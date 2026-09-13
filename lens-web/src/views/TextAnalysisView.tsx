import { useCallback, useEffect, useMemo, useState } from "react";
import { useShell } from "../shell";
import { api, downloadEngineFile } from "../lib/api";
import { RowsTable } from "../components/ui";

/**
 * Text Analysis (v0.3) — the AntConc-audit surface over the OCR corpus:
 * word list, concordance, collocations (+ network + word sketch), n-grams,
 * dispersion, and reference-corpus keyness. Every result exports in the
 * publication formats; the stoplist manager is inline.
 */
type Tab = "wordlist" | "conc" | "coll" | "ngrams" | "disp" | "key";

const fmt = (v: any): string =>
  v === null || v === undefined ? "—" : String(v);

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

function StoplistPicker({ project, value, onChange }: {
  project: string | null; value: string; onChange: (v: string) => void;
}) {
  const { t, toast } = useShell();
  const [lists, setLists] = useState<any[]>([]);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [items, setItems] = useState("");

  const reload = useCallback(() => {
    if (!project) return;
    api.listStoplists(project).then((r) => {
      setLists([...(r.custom ?? [])]);
    }).catch(() => undefined);
  }, [project]);
  useEffect(reload, [reload]);

  const create = async () => {
    if (!project || !name.trim()) return;
    try {
      await api.createStoplist(project, name.trim(),
        items.split(/[\s,]+/).map((w) => w.trim().toLowerCase()).filter(Boolean));
      setName(""); setItems("");
      reload();
      toast(t.common.save);
    } catch (e: any) {
      toast(`${t.common.error}: ${e?.message ?? e}`, "error");
    }
  };

  return (
    <span className="row" style={{ gap: 8 }}>
      <select value={value} onChange={(e) => onChange(e.target.value)}
              style={{ padding: 8, borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface-2)" }}
              aria-label={t.text.stoplist}>
        <option value="builtin">{t.text.stoplistBuiltin}</option>
        <option value="builtin-none">{t.text.stoplistNone}</option>
        <option value="builtin-en">EN</option>
        <option value="builtin-ar">AR</option>
        {lists.map((l) => <option key={l.name} value={l.name}>{l.name}</option>)}
      </select>
      {project && (
        <button className="btn secondary" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => setOpen(!open)}>
          {t.text.stoplistManage}
        </button>
      )}
      {open && project && (
        <span className="card" style={{ display: "block", margin: 0, padding: 12, minWidth: 320 }}>
          <div className="row">
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder={t.text.stoplistName}
                   style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--surface-2)" }} />
            <input value={items} onChange={(e) => setItems(e.target.value)} placeholder={t.text.stoplistItems}
                   style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--surface-2)", minWidth: 180 }} />
            <button className="btn" style={{ padding: "6px 10px" }} onClick={create}>{t.text.stoplistCreate}</button>
          </div>
          {lists.length > 0 && (
            <div className="row" style={{ marginTop: 8 }}>
              {lists.map((l) => (
                <span key={l.name} className="chip">
                  {l.name} ({l.items.length})
                  <button className="lens-link" style={{ marginInlineStart: 6 }}
                          onClick={async () => {
                            try {
                              await api.deleteStoplist(project, l.name);
                              reload();
                              if (value === l.name) onChange("builtin");
                            } catch (e: any) {
                              toast(`${t.common.error}: ${e?.message ?? e}`, "error");
                            }
                          }}>
                    {t.text.stoplistDelete}
                  </button>
                </span>
              ))}
            </div>
          )}
          <p className="muted" style={{ fontSize: 12, marginBottom: 0 }}>{t.text.stoplistHint}</p>
        </span>
      )}
    </span>
  );
}

/** Radial collocation network (GraphColl-style, zero dependencies). */
function Network({ node, edges, t }: { node: string; edges: any[]; t: any }) {
  const size = 320;
  const cx = size / 2, cy = size / 2, r = size / 2 - 46;
  const maxW = Math.max(...edges.map((e) => e.weight || 0), 0.001);
  return (
    <div>
      <h4 style={{ margin: "12px 0 4px" }}>{t.text.network}</h4>
      <p className="muted" style={{ fontSize: 12 }}>{t.text.networkHint}</p>
      <svg width="100%" viewBox={`0 0 ${size} ${size}`} style={{ maxWidth: 420, background: "var(--surface-2)", borderRadius: 10 }} role="img" aria-label={t.text.network}>
        {edges.map((e, i) => {
          const angle = (i / Math.max(edges.length, 1)) * 2 * Math.PI - Math.PI / 2;
          const x = cx + r * Math.cos(angle);
          const y = cy + r * Math.sin(angle);
          const strength = (e.weight || 0) / maxW;
          return (
            <line key={i} x1={cx} y1={cy} x2={x} y2={y}
                  stroke="var(--lens-accent)" strokeOpacity={0.2 + strength * 0.6}
                  strokeWidth={1 + strength * 3} />
          );
        })}
        {edges.map((e, i) => {
          const angle = (i / Math.max(edges.length, 1)) * 2 * Math.PI - Math.PI / 2;
          const x = cx + r * Math.cos(angle);
          const y = cy + r * Math.sin(angle);
          return (
            <g key={i}>
              <circle cx={x} cy={y} r={4} fill="var(--lens-accent)" />
              <text x={x} y={y - 8} textAnchor="middle" fontSize="11" fill="var(--text)">{e.target}</text>
            </g>
          );
        })}
        <circle cx={cx} cy={cy} r={26} fill="var(--lens-gold)" />
        <text x={cx} y={cy + 4} textAnchor="middle" fontSize="12" fontWeight="700" fill="#1a1305">{node}</text>
      </svg>
    </div>
  );
}

export function TextAnalysisView() {
  const { t, setActiveSetId, activeSetId: sid, toast } = useShell();
  const [tab, setTab] = useState<Tab>("wordlist");
  const [sets, setSets] = useState<any[]>([]);
  const [project, setProject] = useState<string | null>(null);
  const [hasText, setHasText] = useState<boolean | null>(null);

  const [stoplist, setStoplist] = useState("builtin");

  // wordlist
  const [wordlist, setWordlist] = useState<any>(null);
  // concordance
  const [query, setQuery] = useState("");
  const [regex, setRegex] = useState(false);
  const [sort, setSort] = useState("none");
  const [conc, setConc] = useState<any>(null);
  const [concBusy, setConcBusy] = useState(false);
  // collocations
  const [node, setNode] = useState("");
  const [span, setSpan] = useState(5);
  const [metric, setMetric] = useState("mi");
  const [coll, setColl] = useState<any>(null);
  const [sketchWord, setSketchWord] = useState<string | null>(null);
  const [sketch, setSketch] = useState<any>(null);
  // ngrams
  const [n, setN] = useState(2);
  const [minCount, setMinCount] = useState(2);
  const [grams, setGrams] = useState<any>(null);
  // dispersion
  const [disp, setDisp] = useState<any>(null);
  // keyness
  const [refs, setRefs] = useState<any[]>([]);
  const [reference, setReference] = useState("");
  const [keyness, setKeyness] = useState<any>(null);

  const runWordlist = useCallback(() => {
    if (!sid) return;
    api.textWordlist(sid, { stoplist }).then(setWordlist).catch(() => undefined);
  }, [sid, stoplist]);

  useEffect(() => {
    setWordlist(null); setConc(null); setColl(null); setGrams(null);
    setDisp(null); setKeyness(null); setHasText(null); setSketch(null); setSketchWord(null);
    setProject(null);
    if (!sid) return;
    (async () => {
      const allSets: any[] = [];
      const ps = await api.listProjects().catch(() => []);
      await Promise.all(ps.map(async (p) => (await api.listImageSets(p.id)).forEach((s: any) => allSets.push(s))));
      setSets(allSets);
      const s = allSets.find((x) => x.id === sid);
      setProject(s?.project_id ?? null);
    })();
    runWordlist();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sid]);

  useEffect(() => { if (sid) runWordlist(); }, [stoplist, sid, runWordlist]);

  // Probe OCR availability once per set for the empty-state hint.
  useEffect(() => {
    if (!sid) return;
    api.listImages(sid).then((imgs) => {
      setHasText(imgs.some((i: any) => ((i.meta || {}).ocr || {}).text));
    }).catch(() => setHasText(false));
  }, [sid]);

  useEffect(() => {
    if (!sid) return;
    api.textReferences(sid).then((r) => {
      setRefs(r.references ?? []);
      if (r.references?.length) setReference(r.references[0].id);
    }).catch(() => undefined);
  }, [sid]);

  const runConc = async () => {
    if (!sid || !query.trim()) return;
    setConcBusy(true);
    try {
      setConc(await api.textConcordance(sid, { query, regex, sort, context_words: 6 }));
    } catch (e: any) {
      toast(`${t.common.error}: ${e?.message ?? e}`, "error");
    } finally {
      setConcBusy(false);
    }
  };

  const runColl = async () => {
    if (!sid || !node.trim()) return;
    try {
      setColl(await api.textCollocations(sid, { node: node.trim(), span, metric, min_freq: 1 }));
    } catch (e: any) {
      toast(`${t.common.error}: ${e?.message ?? e}`, "error");
    }
  };

  const openSketch = async (word: string) => {
    setSketchWord(word);
    setSketch(null);
    try {
      setSketch(await api.textSketch(sid!, word));
    } catch (e: any) {
      toast(`${t.common.error}: ${e?.message ?? e}`, "error");
    }
  };

  const runNgrams = () => {
    if (!sid) return;
    api.textNgrams(sid, { n, min_count: minCount }).then(setGrams).catch(() => undefined);
  };

  const runDisp = () => {
    if (!sid) return;
    api.textDispersion(sid, stoplist).then(setDisp).catch(() => undefined);
  };

  const runKeyness = () => {
    if (!sid || !reference) return;
    api.textKeynessReference(sid, reference, stoplist).then(setKeyness).catch((e: any) =>
      toast(`${t.common.error}: ${e?.message ?? e}`, "error"));
  };

  const exportText = (what: string, params: Record<string, string | number | boolean>, name: string, format: string) => {
    downloadEngineFile(api.textExportUrl(sid!, what, format, params), `${name}.${format}`)
      .catch((e: any) => toast(`${t.common.error}: ${e?.message ?? e}`, "error"));
  };

  const tabs: [Tab, string][] = [
    ["wordlist", t.text.tabWordlist], ["conc", t.text.tabConc], ["coll", t.text.tabColl],
    ["ngrams", t.text.tabNgrams], ["disp", t.text.tabDisp], ["key", t.text.tabKey],
  ];

  const activeSet = useMemo(() => sets.find((s) => s.id === sid), [sets, sid]);

  if (!sid) {
    return (
      <div>
        <h2>{t.text.title}</h2>
        <p className="muted">{t.vision.needSet}</p>
        <SetPicker />
      </div>
    );
  }

  return (
    <div>
      <h2>{t.text.title}</h2>
      <p className="muted" style={{ maxWidth: 760, marginTop: 0 }}>{t.text.intro}</p>

      <div className="card">
        <div className="row" style={{ flexWrap: "wrap" }}>
          <SetPicker />
          <StoplistPicker project={project} value={stoplist} onChange={setStoplist} />
          {activeSet && <span className="chip">{activeSet.name}</span>}
          <button className="btn secondary" onClick={runWordlist} style={{ padding: "6px 12px" }}>
            {t.common.run}
          </button>
        </div>
        {hasText === false && <p className="notice" style={{ marginTop: 10 }}>{t.text.emptyOcr}</p>}
      </div>

      <div className="tabs" role="tablist">
        {tabs.map(([id, label]) => (
          <button key={id} role="tab" aria-selected={tab === id}
                  className={tab === id ? "active" : ""} onClick={() => setTab(id)}>
            {label}
          </button>
        ))}
      </div>

      {tab === "wordlist" && (
        <div className="card">
          <h3>{t.text.tabWordlist}</h3>
          {wordlist && (
            <>
              <p className="muted" style={{ fontSize: 13 }}>
                {wordlist.tokens} {t.text.words} · {wordlist.types} types · TTR {wordlist.ttr}
              </p>
              <RowsTable
                columns={[
                  { key: "word", label: t.text.node },
                  { key: "count", label: t.text.freq, align: "end" },
                  { key: "freq_pm", label: "pm", align: "end" },
                ]}
                rows={wordlist.items}
                max={150}
              />
            </>
          )}
        </div>
      )}

      {tab === "conc" && (
        <div className="card">
          <h3>{t.text.tabConc}</h3>
          <div className="row" style={{ flexWrap: "wrap" }}>
            <input value={query} onChange={(e) => setQuery(e.target.value)}
                   placeholder={t.text.query}
                   onKeyDown={(e) => { if (e.key === "Enter") runConc(); }}
                   style={{ padding: 8, borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface-2)", minWidth: 220 }} />
            <label className="row" style={{ gap: 4, fontSize: 13 }}>
              <input type="checkbox" checked={regex} onChange={(e) => setRegex(e.target.checked)} /> {t.text.regex}
            </label>
            <select value={sort} onChange={(e) => setSort(e.target.value)}
                    style={{ padding: 8, borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface-2)" }}>
              <option value="none">{t.text.sortNone}</option>
              <option value="L1">{t.text.sortL1}</option>
              <option value="R1">{t.text.sortR1}</option>
            </select>
            <button className="btn" onClick={runConc} disabled={concBusy || !query.trim()}>
              {concBusy ? t.common.processing : t.common.run}
            </button>
            {conc && conc.hits.length > 0 && (
              <button className="btn secondary" onClick={() => exportText(
                "concordance/export",
                { query, regex, context_words: 6 },
                `lens-concordance-${sid}`, "csv")}>
                {t.common.export} CSV
              </button>
            )}
          </div>
          {conc && (
            <>
              <p className="muted" style={{ fontSize: 13 }}>
                {conc.total} {t.text.totalHits}{conc.truncated ? " (5000+)" : ""}
              </p>
              <div style={{ maxHeight: 420, overflowY: "auto", border: "1px solid var(--border)", borderRadius: 10, padding: 8, fontFamily: "var(--mono)", fontSize: 12.5 }}>
                {conc.hits.map((h: any, i: number) => (
                  <div key={i} style={{ padding: "3px 0", borderBottom: "1px solid var(--border)" }}>
                    <span className="evidence" style={{ marginInlineEnd: 8 }}>{h.image}</span>
                    <span style={{ opacity: 0.75 }}>{h.left.join(" ")} </span>
                    <strong style={{ background: "var(--lens-accent-soft)", padding: "0 3px", borderRadius: 3 }}>{h.node}</strong>
                    <span style={{ opacity: 0.75 }}> {h.right.join(" ")}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {tab === "coll" && (
        <div className="card">
          <h3>{t.text.tabColl}</h3>
          <div className="row" style={{ flexWrap: "wrap" }}>
            <input value={node} onChange={(e) => setNode(e.target.value)}
                   placeholder={t.text.node}
                   style={{ padding: 8, borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface-2)", minWidth: 180 }} />
            <label className="row" style={{ gap: 4, fontSize: 13 }}>
              {t.text.span}
              <input type="number" min={1} max={10} value={span} onChange={(e) => setSpan(+e.target.value)}
                     style={{ width: 60, padding: 6, borderRadius: 6, border: "1px solid var(--border)", background: "var(--surface-2)" }} />
            </label>
            <select value={metric} onChange={(e) => setMetric(e.target.value)}
                    style={{ padding: 8, borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface-2)" }}>
              <option value="mi">{t.text.metricMi}</option>
              <option value="t">{t.text.metricT}</option>
              <option value="ll">{t.text.metricLl}</option>
              <option value="logdice">{t.text.metricLogdice}</option>
              <option value="deltap">{t.text.metricDp}</option>
              <option value="freq">{t.text.metricFreq}</option>
            </select>
            <button className="btn" onClick={runColl} disabled={!node.trim()}>{t.common.run}</button>
          </div>
          {coll && (
            <>
              <p className="muted" style={{ fontSize: 13 }}>
                {coll.node_freq} × {t.text.node} · N = {coll.N}
              </p>
              {coll.edges.length > 0 && <Network node={coll.node} edges={coll.edges} t={t} />}
              <div style={{ marginTop: 10 }}>
                <RowsTable
                  columns={[
                    { key: "word", label: t.text.tabColl },
                    { key: "O", label: "O", align: "end" },
                    { key: "mi", label: "MI", align: "end" },
                    { key: "t_score", label: "t", align: "end" },
                    { key: "log_likelihood", label: "LL", align: "end" },
                    { key: "log_dice", label: "LogDice", align: "end" },
                    { key: "delta_p", label: "ΔP", align: "end" },
                  ]}
                  rows={coll.rows}
                  max={50}
                />
              </div>
              <p className="muted" style={{ fontSize: 12 }}>{t.text.effectNote}</p>
            </>
          )}
          {sketchWord && (
            <div className="card" style={{ margin: "14px 0 0" }}>
              <h3>{t.text.sketchFor} “{sketchWord}”</h3>
              {!sketch ? <p className="muted">{t.common.loading}</p> : (
                <>
                  <p className="muted" style={{ fontSize: 13 }}>
                    {t.text.freq} {sketch.freq} · {sketch.images_with_token} {t.common.images}
                  </p>
                  {sketch.collocates?.length > 0 && (
                    <>
                      <strong>{t.text.tabColl}</strong>
                      <div className="row" style={{ margin: "6px 0" }}>
                        {sketch.collocates.map((c: any) => (
                          <span key={c.word} className="chip">{c.word} · MI {c.mi}</span>
                        ))}
                      </div>
                    </>
                  )}
                  <h4 style={{ margin: "10px 0 4px" }}>{t.text.visualCopatterns}</h4>
                  <dl className="kv">
                    <dt>{t.text.colours}</dt>
                    <dd>
                      {(sketch.visual_copatterns.dominant_colours ?? []).map((c: any) => (
                        <span key={c.hex} title={c.hex}
                              style={{ display: "inline-block", width: 16, height: 16, background: c.hex,
                                       borderRadius: 4, marginInlineEnd: 4 }} />
                      ))}
                      {sketch.visual_copatterns.dominant_colours?.length === 0 && <span className="muted">—</span>}
                    </dd>
                    <dt>{t.text.meanBrightness} / {t.text.meanWarmth}</dt>
                    <dd>{fmt(sketch.visual_copatterns.mean_brightness)} / {fmt(sketch.visual_copatterns.mean_warm_cold_balance)}</dd>
                    <dt>{t.text.annotationValues}</dt>
                    <dd>
                      {(sketch.visual_copatterns.annotation_values ?? []).map((a: any) => (
                        <span key={a.value} className="chip">{a.value} ({a.count})</span>
                      )) || "—"}
                    </dd>
                    <dt>{t.text.detectedObjects}</dt>
                    <dd>
                      {(sketch.visual_copatterns.detected_objects ?? []).map((o: any) => (
                        <span key={o.label} className="chip">{o.label} ({o.count})</span>
                      )) || "—"}
                    </dd>
                    <dt>{t.text.concSample}</dt>
                    <dd>
                      {(sketch.concordance_sample ?? []).slice(0, 4).map((h: any, i: number) => (
                        <div key={i} className="evidence" style={{ marginBottom: 2 }}>
                          {h.left} <strong>{h.node}</strong> {h.right}
                        </div>
                      ))}
                    </dd>
                  </dl>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {tab === "ngrams" && (
        <div className="card">
          <h3>{t.text.tabNgrams}</h3>
          <div className="row" style={{ flexWrap: "wrap" }}>
            <label className="row" style={{ gap: 4, fontSize: 13 }}>
              N
              <input type="number" min={2} max={6} value={n} onChange={(e) => setN(+e.target.value)}
                     style={{ width: 60, padding: 6, borderRadius: 6, border: "1px solid var(--border)", background: "var(--surface-2)" }} />
            </label>
            <label className="row" style={{ gap: 4, fontSize: 13 }}>
              {t.text.minCount}
              <input type="number" min={1} value={minCount} onChange={(e) => setMinCount(+e.target.value)}
                     style={{ width: 70, padding: 6, borderRadius: 6, border: "1px solid var(--border)", background: "var(--surface-2)" }} />
            </label>
            <button className="btn" onClick={runNgrams}>{t.common.run}</button>
            {grams && grams.rows?.length > 0 && (
              <button className="btn secondary" onClick={() => exportText("ngrams/export", { n, min_count: minCount }, `lens-ngrams-${sid}`, "csv")}>
                {t.common.export} CSV
              </button>
            )}
          </div>
          {grams && (
            <>
              <div style={{ marginTop: 10 }}>
                <RowsTable
                  columns={[
                    { key: "gram", label: `${t.text.tabNgrams} (N=${grams.n})` },
                    { key: "count", label: t.text.freq, align: "end" },
                    { key: "juillands_d", label: "D", align: "end" },
                    { key: "gries_dp", label: "DP", align: "end" },
                    { key: "range", label: t.text.range, align: "end" },
                  ]}
                  rows={(grams.rows ?? []).map((r: any) => ({ ...r, gram: r.gram.join(" ") }))}
                  max={80}
                />
              </div>
              <p className="muted" style={{ fontSize: 12 }}>{t.text.dispersionNote}</p>
            </>
          )}
        </div>
      )}

      {tab === "disp" && (
        <div className="card">
          <h3>{t.text.tabDisp}</h3>
          <button className="btn" onClick={runDisp}>{t.common.run}</button>
          {disp && (
            <>
              <div style={{ marginTop: 10 }}>
                <RowsTable
                  columns={[
                    { key: "word", label: t.text.node },
                    { key: "count", label: t.text.freq, align: "end" },
                    { key: "juillands_d", label: "D", align: "end" },
                    { key: "gries_dp", label: "DP", align: "end" },
                    { key: "range", label: t.text.range, align: "end" },
                    { key: "images", label: t.common.images, align: "end" },
                  ]}
                  rows={disp.rows}
                  max={100}
                />
              </div>
              <p className="muted" style={{ fontSize: 12 }}>{t.text.dispersionNote}</p>
            </>
          )}
        </div>
      )}

      {tab === "key" && (
        <div className="card">
          <h3>{t.workbench.keyness}</h3>
          <div className="row" style={{ flexWrap: "wrap" }}>
            <select value={reference} onChange={(e) => setReference(e.target.value)}
                    style={{ padding: 8, borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface-2)", minWidth: 240 }}>
              {refs.map((r) => <option key={r.id} value={r.id}>{r.description} ({r.words})</option>)}
            </select>
            <button className="btn" onClick={runKeyness} disabled={!reference}>{t.common.run}</button>
            {keyness && keyness.rows?.length > 0 && (
              <button className="btn secondary" onClick={() => exportText("keyness-reference/export", { reference }, `lens-keyness-${reference}-${sid}`, "csv")}>
                {t.common.export} CSV
              </button>
            )}
          </div>
          {keyness && (
            <>
              <p className="muted" style={{ fontSize: 13 }}>
                N1 = {keyness.N1} · N2 = {keyness.N2}
              </p>
              <RowsTable
                columns={[
                  { key: "term", label: t.text.node },
                  { key: "f1", label: "f1", align: "end" },
                  { key: "log_likelihood", label: "LL", align: "end" },
                  { key: "log_ratio", label: "LogRatio", align: "end" },
                  { key: "pct_diff", label: "%DIFF", align: "end" },
                  { key: "fisher_exact", label: "Fisher", align: "end" },
                ]}
                rows={keyness.rows.slice(0, 60)}
                max={60}
              />
              <p className="muted" style={{ fontSize: 12 }}>{t.text.effectNote}</p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
