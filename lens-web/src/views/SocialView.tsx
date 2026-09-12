import { useCallback, useEffect, useMemo, useState } from "react";
import { useShell } from "../shell";
import { api, socialExportUrl } from "../lib/api";
import { EmptyState, ExportButtons, RowsTable } from "../components/ui";

/**
 * Social Media view (v0.2): import-first corpora (S1, fully offline) and
 * official free-tier API fetches (S2, BYO credentials), sharing the same
 * analysis battery and CSV/XML/TSV/JSON exports as the visual side.
 */

type Tab = "posts" | "text" | "social" | "sources";

const ANALYSES_TEXT = ["text-frequency", "text-diversity", "text-ngrams", "text-kwic"] as const;
const ANALYSES_SOCIAL = [
  "emoji", "hashtags", "hashtag-network", "engagement", "engagement-keyness", "time-series", "keyness",
] as const;

const CONNECTOR_FIELDS: Record<string, { key: string; labelKey: string; secret?: boolean }[]> = {
  mastodon: [
    { key: "instance", labelKey: "instance" },
    { key: "hashtag", labelKey: "hashtag" },
  ],
  reddit: [
    { key: "subreddit", labelKey: "subreddit" },
    { key: "client_id", labelKey: "clientId" },
    { key: "client_secret", labelKey: "clientSecret", secret: true },
    { key: "query", labelKey: "query" },
  ],
  youtube: [
    { key: "api_key", labelKey: "apiKey", secret: true },
    { key: "query", labelKey: "query" },
  ],
};

const inputStyle: React.CSSProperties = {
  padding: "8px 10px",
  borderRadius: 8,
  border: "1px solid var(--border)",
  background: "var(--surface-2)",
};

function Card({ title, subtitle, children }: { title?: React.ReactNode; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="card">
      {title && <h3 style={{ marginTop: 0 }}>{title}</h3>}
      {subtitle && <p className="muted" style={{ fontSize: 13, marginTop: -4 }}>{subtitle}</p>}
      {children}
    </div>
  );
}

export function SocialView() {
  const { t, toast, setActiveSetId, setView } = useShell();
  const [projects, setProjects] = useState<any[]>([]);
  const [projectId, setProjectId] = useState<string>("");
  const [tab, setTab] = useState<Tab>("posts");
  const [summary, setSummary] = useState<any>(null);
  const [posts, setPosts] = useState<any[]>([]);
  const [platform, setPlatform] = useState("all");
  const [result, setResult] = useState<any>(null);
  const [analysis, setAnalysis] = useState<string>("text-frequency");
  const [kwicQuery, setKwicQuery] = useState("");
  const [minCount, setMinCount] = useState(1);
  const [otherProject, setOtherProject] = useState("");
  const [busy, setBusy] = useState(false);

  // import state
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState("auto");
  const [attest, setAttest] = useState(false);
  const [pseudonymize, setPseudonymize] = useState(true);
  const [redactUrls, setRedactUrls] = useState(false);
  const [redactMentions, setRedactMentions] = useState(false);
  const [visionAnalyse, setVisionAnalyse] = useState(true);

  // fetch state
  const [connector, setConnector] = useState("mastodon");
  const [params, setParams] = useState<Record<string, string>>({});
  const [maxItems, setMaxItems] = useState(200);
  const [tos, setTos] = useState(false);
  const [fetching, setFetching] = useState(false);

  const refreshProjects = useCallback(async () => {
    const ps = await api.listProjects();
    setProjects(ps);
    setProjectId((cur) => cur || (ps[0]?.id ?? ""));
  }, []);

  useEffect(() => {
    refreshProjects().catch(() => undefined);
  }, [refreshProjects]);

  const refreshPosts = useCallback(async () => {
    if (!projectId) return;
    try {
      const [s, p] = await Promise.all([
        api.socialSummary(projectId),
        api.listPosts(projectId, platform, 300),
      ]);
      setSummary(s);
      setPosts(p.posts ?? []);
    } catch {
      /* engine still starting */
    }
  }, [projectId, platform]);

  useEffect(() => {
    refreshPosts();
  }, [refreshPosts]);

  const runAnalysis = useCallback(
    async (name: string) => {
      if (!projectId) return;
      setBusy(true);
      setResult(null);
      try {
        const params: Record<string, string | number> = {};
        if (name === "text-kwic") params.query = kwicQuery;
        if (name === "text-ngrams" || name === "engagement-keyness") params.min_count = minCount;
        if (name === "text-frequency") params.min_count = minCount;
        if (name === "keyness") params.other_project_id = otherProject;
        const data = await api.socialAnalyse(projectId, name, params);
        setResult(data);
      } catch (e: any) {
        toast(`${t.common.error}: ${e?.message ?? e}`, "error");
      } finally {
        setBusy(false);
      }
    },
    [projectId, kwicQuery, minCount, otherProject, toast, t.common.error]
  );

  useEffect(() => {
    if (tab === "text" || tab === "social") runAnalysis(analysis);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, analysis]);

  const platformCounts = useMemo(() => summary?.platform_counts ?? {}, [summary]);
  const totalPosts = summary?.total_posts ?? 0;

  const doImport = async () => {
    if (!projectId || !file) return;
    setBusy(true);
    try {
      const r = await api.socialImport(projectId, file, source, {
        attested: attest,
        pseudonymize,
        redact_urls: redactUrls,
        redact_mentions: redactMentions,
        vision_analyse: visionAnalyse,
      });
      toast(`${r.imported} ${t.social.imported}`);
      if (r.media_registered) toast(`${r.media_registered} ${t.social.mediaAttached}`);
      if (r.image_set_id) {
        setActiveSetId(r.image_set_id);
      }
      setFile(null);
      await refreshPosts();
      setTab("posts");
    } catch (e: any) {
      toast(`${t.common.error}: ${e?.message ?? e}`, "error");
    } finally {
      setBusy(false);
    }
  };

  const doFetch = async () => {
    if (!projectId) return;
    setFetching(true);
    try {
      const r = await api.socialFetch(projectId, {
        connector,
        acknowledge_tos: tos,
        max_items: maxItems,
        comments: true,
        params,
      });
      toast(`${r.imported} ${t.social.imported}`);
      (r.warnings ?? []).slice(0, 3).forEach((w: string) => toast(w, "error"));
      await refreshPosts();
      setTab("posts");
    } catch (e: any) {
      toast(`${t.common.error}: ${e?.message ?? e}`, "error");
    } finally {
      setFetching(false);
    }
  };

  const analysisRows = useMemo((): Record<string, any>[] => {
    if (!result) return [];
    if (analysis === "text-frequency" || analysis === "engagement-keyness") return result.profile ?? [];
    if (analysis === "text-ngrams") return result.profile ?? [];
    if (analysis === "emoji" || analysis === "hashtags") return result.profile ?? [];
    if (analysis === "hashtag-network") return result.edges ?? [];
    if (analysis === "time-series") return result.points ?? [];
    if (analysis === "text-kwic") return result.lines ?? [];
    if (analysis === "keyness") return result.rows ?? [];
    if (analysis === "engagement") return result.top_posts ?? [];
    if (analysis === "text-diversity")
      return Object.entries(result)
        .filter(([, v]) => typeof v === "number")
        .map(([k, v]) => ({ measure: k, value: v as number }));
    return [];
  }, [result, analysis]);

  const analysisColumns = useMemo((): { key: string; label: string; align?: "start" | "end" }[] => {
    const rows = analysisRows;
    if (!rows.length) return [];
    const sample = rows[0];
    return Object.keys(sample).map((k) => ({
      key: k,
      label: k,
      align: typeof sample[k] === "number" ? ("end" as const) : ("start" as const),
    }));
  }, [analysisRows]);

  const exportParams = useMemo(() => {
    const p: Record<string, string | number> = {};
    if (analysis === "text-kwic") p.query = kwicQuery;
    if (analysis.includes("min_count") || analysis === "text-ngrams" || analysis === "text-frequency" || analysis === "engagement-keyness")
      p.min_count = minCount;
    if (analysis === "keyness") p.other_project_id = otherProject;
    return p;
  }, [analysis, kwicQuery, minCount, otherProject]);

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
        <h2 style={{ margin: 0 }}>{t.social.title}</h2>
        {projectId && (
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <select
              aria-label={t.overview.projects}
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              style={inputStyle}
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            {totalPosts > 0 && (
              <>
                <select
                  aria-label={t.social.platformFilter}
                  value={platform}
                  onChange={(e) => setPlatform(e.target.value)}
                  style={inputStyle}
                >
                  <option value="all">{t.common.all}</option>
                  {Object.keys(platformCounts).map((p) => (
                    <option key={p} value={p}>
                      {p} ({platformCounts[p]})
                    </option>
                  ))}
                </select>
                <button
                  className="btn secondary"
                  onClick={async () => {
                    if (!confirm(t.social.clearPosts + "?")) return;
                    await api.deletePosts(projectId, platform);
                    toast(t.social.clearPosts);
                    await refreshPosts();
                  }}
                >
                  {t.social.clearPosts}
                </button>
              </>
            )}
          </div>
        )}
      </div>
      <p className="muted" style={{ maxWidth: 780 }}>{t.social.intro}</p>

      {!projectId ? (
        <EmptyState glyph="❏" title={t.overview.newProject} hint={t.social.noPosts} />
      ) : (
        <>
          <div className="row" style={{ gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
            {(
              [
                ["posts", t.social.posts],
                ["text", t.social.analyses + " · " + t.social.textFreq],
                ["social", t.social.analyses + " · " + t.social.emoji],
                ["sources", t.social.sources],
              ] as [Tab, string][]
            ).map(([id, label], i) => (
              <button
                key={id}
                className={tab === id ? "btn" : "btn secondary"}
                onClick={() => {
                  setTab(id);
                  // Each group leads with its own analysis; keep state in sync.
                  if (id === "text") setAnalysis("text-frequency");
                  if (id === "social") setAnalysis("emoji");
                }}
              >
                {i > 0 ? label : `${label}${totalPosts ? ` (${totalPosts})` : ""}`}
              </button>
            ))}
          </div>

          {tab === "posts" && (
            <>
              <Card title={t.social.importTitle} subtitle={t.social.sourcesHint}>
                <div className="row" style={{ gap: 10, flexWrap: "wrap", alignItems: "center" }}>
                  <input
                    type="file"
                    accept=".zip,.js,.json,.jsonl,.ndjson,.csv"
                    aria-label={t.social.chooseFile}
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  />
                  <select aria-label={t.social.source} value={source} onChange={(e) => setSource(e.target.value)} style={inputStyle}>
                    <option value="auto">{t.social.auto}</option>
                    <option value="x_archive">X / Twitter archive</option>
                    <option value="instagram">Instagram DYI</option>
                    <option value="facebook">Facebook DYI</option>
                    <option value="tiktok">TikTok export</option>
                    <option value="csv">CSV</option>
                    <option value="jsonl">JSONL</option>
                  </select>
                </div>
                <div style={{ marginTop: 12 }}>
                  <strong style={{ fontSize: 13 }}>{t.social.ethicsTitle}</strong>
                  <label className="row" style={{ gap: 8, marginTop: 8, fontSize: 13, alignItems: "flex-start" }}>
                    <input type="checkbox" checked={attest} onChange={(e) => setAttest(e.target.checked)} style={{ marginTop: 3 }} />
                    <span>{t.social.attest}</span>
                  </label>
                  <div className="row" style={{ gap: 16, flexWrap: "wrap", marginTop: 8, fontSize: 13 }}>
                    <label className="row" style={{ gap: 6 }}>
                      <input type="checkbox" checked={pseudonymize} onChange={(e) => setPseudonymize(e.target.checked)} />
                      {t.social.pseudonymize}
                    </label>
                    <label className="row" style={{ gap: 6 }}>
                      <input type="checkbox" checked={redactUrls} onChange={(e) => setRedactUrls(e.target.checked)} />
                      {t.social.redactUrls}
                    </label>
                    <label className="row" style={{ gap: 6 }}>
                      <input type="checkbox" checked={redactMentions} onChange={(e) => setRedactMentions(e.target.checked)} />
                      {t.social.redactMentions}
                    </label>
                    <label className="row" style={{ gap: 6 }}>
                      <input type="checkbox" checked={visionAnalyse} onChange={(e) => setVisionAnalyse(e.target.checked)} />
                      {t.social.visionAnalyse}
                    </label>
                  </div>
                </div>
                <div className="row" style={{ marginTop: 14 }}>
                  <button className="btn" disabled={!file || !attest || busy} onClick={doImport}>
                    {busy ? t.social.importing : t.social.importBtn}
                  </button>
                </div>
              </Card>

              <Card title={t.social.fetchTitle} subtitle={t.social.fetchDesc}>
                <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
                  <select value={connector} onChange={(e) => setConnector(e.target.value)} style={inputStyle}>
                    <option value="mastodon">{t.social.mastodon}</option>
                    <option value="reddit">{t.social.reddit}</option>
                    <option value="youtube">{t.social.youtube}</option>
                  </select>
                  {CONNECTOR_FIELDS[connector].map((f) => (
                    <input
                      key={f.key}
                      type={f.secret ? "password" : "text"}
                      placeholder={t.social[f.labelKey as keyof typeof t.social] as string}
                      aria-label={t.social[f.labelKey as keyof typeof t.social] as string}
                      value={params[f.key] ?? ""}
                      onChange={(e) => setParams((p) => ({ ...p, [f.key]: e.target.value }))}
                      style={{ ...inputStyle, minWidth: 180 }}
                    />
                  ))}
                  <label className="row" style={{ gap: 6, fontSize: 13 }}>
                    {t.social.maxItems}
                    <input
                      type="number"
                      min={10}
                      max={1000}
                      value={maxItems}
                      onChange={(e) => setMaxItems(Math.max(10, Math.min(1000, Number(e.target.value) || 200)))}
                      style={{ ...inputStyle, width: 90 }}
                    />
                  </label>
                </div>
                {connector === "reddit" && (
                  <div className="row" style={{ gap: 10, marginTop: 10, fontSize: 13 }}>
                    <label className="row" style={{ gap: 6 }}>
                      {t.social.mode}
                      <select value={params.mode ?? "new"} onChange={(e) => setParams((p) => ({ ...p, mode: e.target.value }))} style={inputStyle}>
                        <option value="new">{t.social.modeNew}</option>
                        <option value="top">{t.social.modeTop}</option>
                        <option value="hot">{t.social.modeHot}</option>
                        <option value="search">{t.social.modeSearch}</option>
                      </select>
                    </label>
                  </div>
                )}
                <label className="row" style={{ gap: 8, marginTop: 10, fontSize: 13, alignItems: "flex-start" }}>
                  <input type="checkbox" checked={tos} onChange={(e) => setTos(e.target.checked)} style={{ marginTop: 3 }} />
                  <span>{t.social.tos}</span>
                </label>
                <div className="row" style={{ marginTop: 12 }}>
                  <button className="btn" disabled={!tos || fetching} onClick={doFetch}>
                    {fetching ? t.social.fetching : t.social.fetch}
                  </button>
                </div>
                <p className="muted" style={{ fontSize: 12, marginBottom: 0 }}>{t.social.attestationStored}</p>
              </Card>

              {totalPosts === 0 ? (
                <EmptyState glyph="✉" title={t.social.posts} hint={t.social.noPosts} />
              ) : (
                <Card
                  title={
                    <span className="row" style={{ justifyContent: "space-between", width: "100%", flexWrap: "wrap", gap: 8 }}>
                      <span>{t.social.posts}</span>
                      <ExportButtons
                        build={(fmt) => ({
                          url: socialExportUrl(projectId, "posts", fmt, platform !== "all" ? { platform } : {}),
                          filename: `lens-posts-${projectId}.${fmt}`,
                        })}
                      />
                    </span>
                  }
                >
                  <div style={{ overflowX: "auto", maxHeight: 480, overflowY: "auto", border: "1px solid var(--border)", borderRadius: 10 }}>
                    <table className="lens-table" style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                      <thead>
                        <tr>
                          {[
                            ["created_at", "Date"],
                            ["platform", "Platform"],
                            ["author", "Author"],
                            ["text", "Text"],
                            ["meta", "Tags"],
                            ["likes", "Likes"],
                            ["comments", "Comments"],
                            ["shares", "Shares"],
                          ].map(([k, label]) => (
                            <th
                              key={k}
                              style={{
                                position: "sticky", top: 0, background: "var(--surface-2)",
                                textAlign: "start", padding: "8px 10px",
                                borderBottom: "1px solid var(--border)", fontWeight: 600,
                              }}
                            >
                              {label}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {posts.map((p) => (
                          <tr key={p.id} style={{ borderBottom: "1px solid var(--border)" }}>
                            <td style={{ padding: "7px 10px", whiteSpace: "nowrap" }}>{(p.created_at || "").slice(0, 16).replace("T", " ")}</td>
                            <td style={{ padding: "7px 10px" }}>
                              <span className="chip" style={{ fontSize: 11 }}>{p.platform}</span>
                            </td>
                            <td style={{ padding: "7px 10px", whiteSpace: "nowrap" }}>{p.author}</td>
                            <td style={{ padding: "7px 10px", maxWidth: 420 }}>
                              <span style={{ display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                                {p.text}
                              </span>
                            </td>
                            <td style={{ padding: "7px 10px", whiteSpace: "nowrap" }}>
                              {(p.meta?.hashtags ?? []).slice(0, 3).map((h: string) => (
                                <span key={h} className="chip" style={{ fontSize: 11, marginInlineEnd: 4 }}>#{h}</span>
                              ))}
                              {(p.meta?.emoji ?? []).slice(0, 4).join("")}
                              {p.meta?.media_count ? ` · ${p.meta.media_count} media` : ""}
                            </td>
                            <td style={{ padding: "7px 10px", textAlign: "end" }}>{p.likes}</td>
                            <td style={{ padding: "7px 10px", textAlign: "end" }}>{p.comments}</td>
                            <td style={{ padding: "7px 10px", textAlign: "end" }}>{p.shares}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              )}
            </>
          )}

          {(tab === "text" || tab === "social") && (
            <Card>
              <div className="row" style={{ gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
                {(tab === "text" ? ANALYSES_TEXT : ANALYSES_SOCIAL).map((a) => (
                  <button
                    key={a}
                    className={analysis === a ? "btn" : "btn secondary"}
                    style={{ padding: "4px 12px", fontSize: 13 }}
                    onClick={() => setAnalysis(a)}
                  >
                    {t.social[
                      ({
                        "text-frequency": "textFreq",
                        "text-diversity": "textDiv",
                        "text-ngrams": "textNgrams",
                        "text-kwic": "textKwic",
                        emoji: "emoji",
                        hashtags: "hashtags",
                        "hashtag-network": "network",
                        engagement: "engagement",
                        "engagement-keyness": "engKeyness",
                        "time-series": "timeline",
                        keyness: "keyness",
                      } as Record<string, keyof typeof t.social>)[a] as keyof typeof t.social]
                    }
                  </button>
                ))}
              </div>

              <div className="row" style={{ gap: 10, flexWrap: "wrap", marginBottom: 12 }}>
                {analysis === "text-kwic" && (
                  <input
                    placeholder={t.social.kwicQuery}
                    aria-label={t.social.kwicQuery}
                    value={kwicQuery}
                    onChange={(e) => setKwicQuery(e.target.value)}
                    style={inputStyle}
                  />
                )}
                {(analysis === "text-ngrams" || analysis === "text-frequency" || analysis === "engagement-keyness") && (
                  <label className="row" style={{ gap: 6, fontSize: 13 }}>
                    {t.social.minCount}
                    <input
                      type="number"
                      min={1}
                      value={minCount}
                      onChange={(e) => setMinCount(Math.max(1, Number(e.target.value) || 1))}
                      style={{ ...inputStyle, width: 70 }}
                    />
                  </label>
                )}
                {analysis === "keyness" && (
                  <select aria-label={t.social.referenceProject} value={otherProject} onChange={(e) => setOtherProject(e.target.value)} style={inputStyle}>
                    <option value="">{t.social.referenceProject}</option>
                    {projects.filter((p) => p.id !== projectId).map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                )}
                <button className="btn" disabled={busy || (analysis === "text-kwic" && !kwicQuery) || (analysis === "keyness" && !otherProject)} onClick={() => runAnalysis(analysis)}>
                  {t.workbench.run}
                </button>
                {result && (
                  <ExportButtons
                    build={(fmt) => ({
                      url: socialExportUrl(projectId, analysis, fmt, { ...exportParams }),
                      filename: `lens-${analysis}-${projectId}.${fmt}`,
                    })}
                  />
                )}
              </div>

              {busy ? (
                <p className="muted">{t.common.loading}</p>
              ) : result ? (
                analysis === "text-diversity" ? (
                  <RowsTable
                    columns={[
                      { key: "measure", label: "Measure" },
                      { key: "value", label: "Value", align: "end" },
                    ]}
                    rows={analysisRows}
                  />
                ) : analysis === "engagement" ? (
                  <>
                    <div className="row" style={{ gap: 18, flexWrap: "wrap", marginBottom: 12, fontSize: 13 }}>
                      {(["likes", "comments", "shares"] as const).map((k) => (
                        <span key={k}>
                          <strong>{k}</strong>: {result[k]?.mean ?? 0} (mean) · {result[k]?.median ?? 0} (median) · {result[k]?.total ?? 0} (total)
                        </span>
                      ))}
                    </div>
                    <RowsTable
                      columns={[
                        { key: "platform", label: "Platform" },
                        { key: "author", label: "Author" },
                        { key: "text", label: "Text" },
                        { key: "likes", label: "Likes", align: "end" },
                        { key: "comments", label: "Comments", align: "end" },
                        { key: "shares", label: "Shares", align: "end" },
                        { key: "engagement", label: "Total", align: "end" },
                      ]}
                      rows={analysisRows}
                    />
                  </>
                ) : (
                  <RowsTable columns={analysisColumns} rows={analysisRows} />
                )
              ) : (
                <p className="muted">{t.workbench.run} →</p>
              )}
            </Card>
          )}

          {tab === "sources" && (
            <Card title={t.social.sources}>
              {(summary?.sources ?? []).length === 0 ? (
                <p className="muted">{t.social.noPosts}</p>
              ) : (
                <RowsTable
                  columns={[
                    { key: "created_at", label: "Date" },
                    { key: "platform", label: "Platform" },
                    { key: "kind", label: "Kind" },
                    { key: "label", label: "Source" },
                    { key: "post_count", label: "Posts", align: "end" },
                    { key: "anonymized", label: "Anonymised" },
                    { key: "attested", label: "Attested" },
                  ]}
                  rows={(summary?.sources ?? []).map((s: any) => ({
                    ...s,
                    anonymized: s.anonymized ? "yes" : "no",
                    attested: s.attested ? "yes" : "no",
                  }))}
                />
              )}
            </Card>
          )}
        </>
      )}
    </div>
  );
}
