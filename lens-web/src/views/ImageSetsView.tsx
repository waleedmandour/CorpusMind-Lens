import { useEffect, useRef, useState } from "react";
import { useShell } from "../shell";
import { api } from "../lib/api";

export function ImageSetsView() {
  const { t, activeSetId, setActiveSetId, setView } = useShell();
  const [projects, setProjects] = useState<any[]>([]);
  const [sets, setSets] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");

  const load = async () => {
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
  };

  useEffect(() => {
    load().catch(() => undefined);
  }, []);
  useEffect(() => {
    if (activeSetId) api.getSetStats(activeSetId).then(setStats).catch(() => undefined);
  }, [activeSetId]);

  const doUpload = async (files: FileList | null) => {
    if (!files || !activeSetId) return;
    setUploading(true);
    setUploadMsg("");
    try {
      const res = await api.uploadImages(activeSetId, Array.from(files));
      setUploadMsg(
        `${res.accepted.length} accepted, ${res.rejected.length} rejected` +
        (res.rejected.length ? ` — first: ${res.rejected[0].error}` : "")
      );
      setTimeout(() => setUploadMsg(""), 8000);
    } catch (e: any) {
      setUploadMsg(e.message);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <div>
      <h2>{t.nav.imageSets}</h2>
      <div className="card">
        <h3>{t.overview.projects}</h3>
        {projects.map((p) => (
          <span className="chip" key={p.id}>{p.name}</span>
        ))}
      </div>

      <div className="card">
        <h3>{t.nav.imageSets}</h3>
        <table className="data">
          <thead>
            <tr>
              <th>{t.nav.imageSets}</th>
              <th>{t.overview.provenance}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sets.map((s) => (
              <tr key={s.id} style={s.id === activeSetId ? { background: "var(--lens-accent-soft)" } : undefined}>
                <td>{s.name}</td>
                <td className="muted">{s.provenance_notes || s.description || "—"}</td>
                <td>
                  <button className="btn secondary" onClick={() => setActiveSetId(s.id)}>
                    {s.id === activeSetId ? "✓" : "→"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
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
            <p className="muted" style={{ fontSize: 12 }}>
              JPG · PNG · TIFF · WebP · BMP — magic-byte checked; analysis runs in the background.
            </p>
          </div>

          {stats && (
            <div className="card">
              <h3>{t.overview.stats}</h3>
              <dl className="kv">
                <dt>{t.common.images}</dt>
                <dd>{stats.image_count}</dd>
                <dt>Format mix</dt>
                <dd>{Object.entries(stats.format_mix).map(([k, v]) => `${k}: ${v}`).join(", ") || "—"}</dd>
                <dt>Orientation</dt>
                <dd>{Object.entries(stats.orientation_mix).map(([k, v]) => `${k}: ${v}`).join(", ") || "—"}</dd>
                <dt>OCR coverage</dt>
                <dd>{(stats.coverage.ocr * 100).toFixed(1)}%</dd>
                <dt>Detections</dt>
                <dd>{(stats.coverage.detections * 100).toFixed(1)}%</dd>
              </dl>
              <div className="row" style={{ marginTop: 10 }}>
                <button className="btn" onClick={() => setView("workbench")}>
                  {t.nav.workbench} →
                </button>
                <button
                  className="btn secondary"
                  onClick={async () => {
                    const blob = await api.exportSet(activeSetId, "xlsx");
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `lens-set-${activeSetId}.xlsx`;
                    a.click();
                    URL.revokeObjectURL(url);
                  }}
                >
                  Export xlsx
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
