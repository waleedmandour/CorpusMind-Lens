import { useShell } from "../shell";
import { LENS_VERSION } from "../lib/api";

/**
 * About (v0.3) — a parent-app borrow: version, ethics/privacy position,
 * credits for the open assets Lens builds on, and how to cite it.
 */
const REPO = "https://github.com/waleedmandour/CorpusMind-Lens";

export function AboutView() {
  const { t, setView } = useShell();

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 4 }}>
        <img
          src="/icon-192.png"
          alt="CorpusMind Lens application icon"
          width={64}
          height={64}
          style={{ borderRadius: 14 }}
        />
        <div>
          <h2 style={{ margin: 0 }}>{t.about.title}</h2>
          <p className="muted" style={{ margin: 0 }}>{t.about.tagline}</p>
        </div>
      </div>

      <div className="card">
        <h3>{t.about.what}</h3>
        <p style={{ fontSize: 13.5, lineHeight: 1.7, maxWidth: 760 }}>{t.about.whatBody}</p>
      </div>

      <div className="card">
        <h3>{t.about.privacy}</h3>
        <p style={{ fontSize: 13.5, lineHeight: 1.7, maxWidth: 760 }}>{t.about.privacyBody}</p>
      </div>

      <div className="card">
        <h3>{t.about.credits}</h3>
        <p style={{ fontSize: 13.5, lineHeight: 1.7, maxWidth: 760 }}>{t.about.creditsBody}</p>
        <p className="muted" style={{ fontSize: 13 }}>
          {t.about.license}: AGPL-3.0-only
        </p>
      </div>

      <div className="card">
        <h3>{t.about.cite}</h3>
        <p style={{ fontSize: 13.5, lineHeight: 1.7, maxWidth: 760 }}>{t.about.citeBody}</p>
        <pre className="evidence" style={{
          background: "var(--surface-2)", border: "1px solid var(--border)",
          borderRadius: 8, padding: 10, whiteSpace: "pre-wrap", fontSize: 12,
        }}>{`Mandour, W., & Ibrahim, W. (2026). CorpusMind Lens (Version ${LENS_VERSION}) [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.14777178`}</pre>
      </div>

      <div className="card">
        <h3>{t.nav.settings}</h3>
        <div className="row" style={{ flexWrap: "wrap" }}>
          <a className="btn secondary" style={{ textDecoration: "none" }} href={REPO} target="_blank" rel="noreferrer">
            {t.about.repo}
          </a>
          <a className="btn secondary" style={{ textDecoration: "none" }} href={`${REPO}/releases`} target="_blank" rel="noreferrer">
            {t.about.releases}
          </a>
          <button className="btn secondary" onClick={() => setView("guide")}>{t.about.guide}</button>
        </div>
      </div>
    </div>
  );
}
