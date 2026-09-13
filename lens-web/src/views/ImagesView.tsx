import { useCallback, useEffect, useRef, useState } from "react";
import { useShell } from "../shell";
import { api, downloadEngineFile, engineUrl } from "../lib/api";
import { updateWorkflow } from "../state/taskbar";
import { EmptyState } from "../components/ui";

/**
 * Images (v0.3) — the corpus builder. Merges the old "Image Sets" page and
 * the confusing parts of "Vision Workbench" into one streamlined flow:
 *   pick a set → upload → watch background processing → inspect a photo →
 *   annotate its visual dimensions → export the archive.
 * Set-level statistics and the annotation editor live here; the analysis
 * batteries live on the dedicated analysis pages.
 */
export function ImagesView() {
  const { t, activeSetId, setActiveSetId, setView, toast, lang } = useShell();
  const ar = lang === "ar";
  const [projects, setProjects] = useState<any[]>([]);
  const [sets, setSets] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [images, setImages] = useState<any[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<any>(null);
  const [annotations, setAnnotations] = useState<any>(null);
  const [schema, setSchema] = useState<any>(null);
  const [busy, setBusy] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");

  const load = useCallback(async () => {
    const ps = await api.listProjects();
    setProjects(ps);
    const all: any[] = [];
    await Promise.all(
      ps.map(async (p) => {
        const ss = await api.listImageSets(p.id);
        ss.forEach((s: any) => all.push(s));
      })
    );
    setSets(all);
    return all;
  }, []);

  // Poll the selected set's images so background processing shows live.
  useEffect(() => {
    load().catch(() => undefined);
    api.annotationSchema().then(setSchema).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    setStats(null);
    setImages([]);
    setSelected(null);
    setAnalysis(null);
    setAnnotations(null);
    if (!activeSetId) {
      updateWorkflow(null);
      return;
    }
    api.getSetStats(activeSetId).then(setStats).catch(() => undefined);
    const loadImages = () => {
      api.listImages(activeSetId).then((imgs) => {
        setImages(imgs);
        const processing = imgs.filter((i: any) => i.status === "processing" || i.status === "pending").length;
        updateWorkflow({
          activeSetId,
          activeSetName: sets.find((s) => s.id === activeSetId)?.name ?? "",
          processing,
          total: imgs.length,
          ready: imgs.filter((i: any) => i.status === "ready").length,
          hasAnnotations: imgs.some((i: any) =>
            Object.values((i.meta || {}).annotations || {}).some((b: any) => b?.values?.length)),
          hasResults: imgs.every((i: any) => i.status === "ready") && imgs.length > 0,
        });
      }).catch(() => undefined);
    };
    loadImages();
    const iv = setInterval(loadImages, 3000);
    return () => clearInterval(iv);
  }, [activeSetId, sets]);

  useEffect(() => {
    if (!selected) return;
    setAnalysis(null);
    setAnnotations(null);
    api.getAnalysis(selected).then(setAnalysis).catch(() => undefined);
    api.getAnnotations(selected).then(setAnnotations).catch(() => undefined);
  }, [selected]);

  const doUpload = async (files: FileList | null) => {
    if (!files || !activeSetId) return;
    setUploading(true);
    setUploadMsg("");
    try {
      const res = await api.uploadImages(activeSetId, Array.from(files));
      setUploadMsg(
        `${res.accepted.length} ${t.images.uploadOk}` +
        (res.rejected.length ? `, ${res.rejected.length} ${t.images.uploadBad}` : "")
      );
      setTimeout(() => setUploadMsg(""), 8000);
    } catch (e: any) {
      setUploadMsg(e.message);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const toggleAnnotation = async (dimId: string, value: string) => {
    if (!selected) return;
    const current = annotations ?? { dimensions: {} };
    const block = current.dimensions?.[dimId] ?? { values: [], note: "" };
    const values = block.values.includes(value)
      ? block.values.filter((v: string) => v !== value)
      : [...block.values, value];
    const next = { dimensions: { [dimId]: { values, note: block.note ?? "" } }, tags: [] };
    setAnnotations({ ...current, dimensions: { ...current.dimensions, [dimId]: { values, note: block.note ?? "" } } });
    try {
      await api.setAnnotations(selected, next);
    } catch {
      toast(`${t.common.error}`, "error");
    }
  };

  const runVisionOcr = async () => {
    if (!selected) return;
    setBusy("vocr");
    try {
      await api.ocrVision(selected);
      const a = await api.getAnalysis(selected);
      setAnalysis(a);
      toast(t.images.visionOcrDone);
    } catch (e: any) {
      toast(`${t.common.error}: ${e?.message ?? e}`, "error");
    } finally {
      setBusy("");
    }
  };

  const dims = schema?.dimensions ?? [];
  const activeSet = sets.find((s) => s.id === activeSetId);
  const processingCount = images.filter((i) => i.status === "processing" || i.status === "pending").length;

  const exportXlsx = async () => {
    if (!activeSetId) return;
    try {
      const blob = await api.exportSet(activeSetId, "xlsx");
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `lens-set-${activeSetId}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      toast(`${t.common.error}: ${e?.message ?? e}`, "error");
    }
  };

  return (
    <div>
      <h2>{t.images.title}</h2>
      <p className="muted" style={{ maxWidth: 760, marginTop: 0 }}>{t.images.intro}</p>

      <div className="card">
        <h3>{t.images.sets}</h3>
        <div className="row" style={{ flexWrap: "wrap" }}>
          {sets.map((s) => (
            <button
              key={s.id}
              className={`btn secondary`}
              style={s.id === activeSetId
                ? { outline: "2px solid var(--lens-accent)", fontWeight: 600 }
                : undefined}
              onClick={() => setActiveSetId(s.id)}
            >
              {s.name}
              {s.id === activeSetId ? ` ✓ (${t.images.selected})` : ""}
            </button>
          ))}
          {sets.length === 0 && <span className="muted">{t.images.noImages}</span>}
        </div>
        {projects.length > 0 && (
          <p className="muted" style={{ fontSize: 12, marginBottom: 0 }}>
            {projects.map((p) => p.name).join(" · ")}
          </p>
        )}
      </div>

      {activeSetId && (
        <>
          <div className="card">
            <h3>{t.common.upload}</h3>
            <input
              ref={fileRef}
              type="file"
              multiple
              accept=".jpg,.jpeg,.png,.tif,.tiff,.webp,.bmp"
              onChange={(e) => doUpload(e.target.files)}
              disabled={uploading}
            />
            {uploading && <p className="muted">{t.common.processing}…</p>}
            {uploadMsg && <p className="muted">{uploadMsg}</p>}
            <p className="muted" style={{ fontSize: 12, marginBottom: 0 }}>{t.images.uploadHint}</p>
          </div>

          <div className="card">
            <h3>
              {t.images.gallery}
              {processingCount > 0 && (
                <span className="chip" style={{ marginInlineStart: 8 }}>
                  {processingCount} {t.images.processingN}
                </span>
              )}
            </h3>
            {images.length === 0 ? (
              <EmptyState glyph="❏" title={t.images.noImages} />
            ) : (
              <div className="row" style={{ gap: 8 }}>
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
            )}
          </div>

          {selected && (
            analysis ? (
              <>
                <div className="card">
                  <div className="row" style={{ justifyContent: "space-between" }}>
                    <h3 style={{ margin: 0 }}>{t.images.details} — {analysis.image?.filename ?? selected}</h3>
                    <div className="row" style={{ gap: 6 }}>
                      <button className="btn secondary" style={{ padding: "3px 10px", fontSize: 12 }}
                              onClick={runVisionOcr} disabled={busy === "vocr"}>
                        {busy === "vocr" ? t.common.processing : t.images.runVisionOcr}
                      </button>
                      <button className="btn secondary" style={{ padding: "3px 10px", fontSize: 12 }}
                              onClick={async () => {
                                try {
                                  await api.deleteImage(selected);
                                  setSelected(null);
                                  setAnalysis(null);
                                  toast(t.images.deleted);
                                } catch (e: any) {
                                  toast(`${t.common.error}: ${e?.message ?? e}`, "error");
                                }
                              }}>
                        {t.images.delete}
                      </button>
                    </div>
                  </div>
                  <dl className="kv" style={{ marginTop: 10 }}>
                    <dt>{t.images.ocr}</dt>
                    <dd>
                      {analysis.ocr?.text
                        ? <>{analysis.ocr?.engine} · conf {analysis.ocr?.confidence} · {analysis.ocr?.word_count} {t.text.words}<br /><span className="evidence">{analysis.ocr.text.slice(0, 400)}</span></>
                        : <span className="muted">{t.images.ocrEmpty}</span>}
                    </dd>
                    <dt>{t.images.colour}</dt>
                    <dd>
                      {(analysis.colour?.dominant_colours ?? []).map((c: any) => (
                        <span key={c.hex} title={c.hex}
                              style={{ display: "inline-block", width: 16, height: 16,
                                       background: c.hex, borderRadius: 4, marginInlineEnd: 4 }} />
                      ))}
                      {analysis.colour && <> · warm {analysis.colour.warm_cold_balance} · bright {analysis.colour.brightness}</>}
                    </dd>
                    <dt>{t.images.detections}</dt>
                    <dd>
                      {(analysis.detections ?? []).length
                        ? (analysis.detections ?? []).map((d: any, i: number) => (
                            <span className="chip" key={i}>{d.label} {d.confidence}</span>
                          ))
                        : <span className="muted">—</span>}
                    </dd>
                    <dt>{t.images.typography}</dt>
                    <dd className="evidence">{JSON.stringify(analysis.typography ?? {})}</dd>
                  </dl>
                </div>

                <div className="card">
                  <h3>{t.images.annotate}</h3>
                  {dims.map((d: any) => {
                    const active: string[] = annotations?.dimensions?.[d.id]?.values ?? [];
                    return (
                      <div key={d.id} style={{ marginBottom: 10 }}>
                        <strong>{ar ? d.label_ar : d.label_en}</strong>{" "}
                        {!ar && <span className="muted" style={{ fontSize: 12 }}>{d.label_ar}</span>}
                        <div className="row" style={{ marginTop: 4 }}>
                          {d.categories.map((c: any) => (
                            <button
                              key={c.id}
                              className={active.includes(c.id) ? "btn" : "btn secondary"}
                              style={{ fontSize: 12, padding: "4px 10px" }}
                              onClick={() => toggleAnnotation(d.id, c.id)}
                              title={ar ? c.description_ar : c.description_en}
                            >
                              {ar ? c.label_ar : c.label_en}
                            </button>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                  <button className="btn secondary"
                          onClick={async () => {
                            await api.bulkTag(activeSetId, ["reviewed"]);
                            toast(t.images.bulkTag);
                          }}>
                    {t.images.bulkTag}
                  </button>
                </div>
              </>
            ) : (
              <div className="card"><p className="muted">{t.images.analysisMissing}</p></div>
            )
          )}

          {stats && (
            <div className="card">
              <h3>{t.overview.stats} — {activeSet?.name}</h3>
              <dl className="kv">
                <dt>{t.common.images}</dt>
                <dd>{stats.image_count}</dd>
                <dt>OCR</dt>
                <dd>{(stats.coverage.ocr * 100).toFixed(1)}%</dd>
                <dt>{t.images.detections}</dt>
                <dd>{(stats.coverage.detections * 100).toFixed(1)}%</dd>
              </dl>
              <div className="row" style={{ marginTop: 10 }}>
                <button className="btn secondary" onClick={exportXlsx}>
                  {t.common.export} XLSX
                </button>
                <button className="btn secondary" onClick={() => downloadEngineFile(
                  `${engineUrl()}/api/v1/imagesets/${activeSetId}/ocrtools/export-corpus?format=json`,
                  `lens-corpus-${activeSetId}.json`
                )}>
                  {t.exportView.corpus} JSON
                </button>
                <button className="btn" onClick={() => setView("text")}>{t.nav.text} →</button>
                <button className="btn" onClick={() => setView("vision")}>{t.nav.vision} →</button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
