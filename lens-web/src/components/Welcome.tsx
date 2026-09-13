import { useState } from "react";
import { useShell } from "../shell";
import { api } from "../lib/api";

/**
 * Three-page welcome window (v0.2 UX rebuild), shown on first launch of the
 * new interface and replayable from Settings:
 *   1. What CorpusMind Lens is: local-first multimodal corpus analysis.
 *   2. The workspace: the full functional menu in workflow order (Images,
 *      Social Media, Text Analysis, Vision Analysis, Export) + the task bar.
 *   3. Optional local AI: Ollama / LM Studio, or none at all.
 * Page 3 offers a one-click Ollama install in the desktop shell; everything
 * degrades honestly when skipped.
 */
export function WelcomeFlow() {
  const { t, closeWelcome, toast } = useShell();
  const [step, setStep] = useState(0);
  const [installing, setInstalling] = useState(false);
  const [aiStatus, setAiStatus] = useState<string>("");

  const pages = [
    {
      title: t.welcome.p1Title,
      body: t.welcome.p1Body,
      points: [t.welcome.p1Point1, t.welcome.p1Point2, t.welcome.p1Point3],
      glyph: "◎",
    },
    {
      title: t.welcome.p2Title,
      body: t.welcome.p2Body,
      points: [t.welcome.p2Point1, t.welcome.p2Point2, t.welcome.p2Point3],
      glyph: "❏",
    },
    {
      title: t.welcome.p3Title,
      body: t.welcome.p3Body,
      points: [t.welcome.p3Point1, t.welcome.p3Point2, t.welcome.p3Point3],
      glyph: "✦",
    },
  ];
  const page = pages[step];

  const installOllama = async () => {
    setInstalling(true);
    setAiStatus("");
    try {
      const r = await api.providersStatus();
      if (r.ollama.reachable) {
        setAiStatus("Ollama is already running.");
      } else {
        toast(t.settings.installing);
        await api.aiServeOllama().catch(() => undefined);
        const after = await api.providersStatus();
        setAiStatus(
          after.ollama.reachable
            ? "Ollama is running."
            : "Ollama not found. Install it from ollama.com, or continue without AI."
        );
      }
    } catch {
      setAiStatus("Engine is still starting. You can set up AI later in Settings.");
    } finally {
      setInstalling(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t.welcome.p1Title}
      style={{
        position: "fixed", inset: 0, zIndex: 70,
        background: "var(--bg, #f6f7fb)",
        display: "grid", placeItems: "center", padding: 24,
      }}
    >
      <div
        className="lens-welcome"
        style={{
          width: "min(680px, 94vw)", background: "var(--surface)",
          border: "1px solid var(--border)", borderRadius: 16,
          padding: "40px 44px 28px", boxShadow: "0 24px 64px rgba(15,23,42,.18)",
        }}
      >
        <div
          aria-hidden
          style={{
            width: 56, height: 56, borderRadius: 14, display: "grid", placeItems: "center",
            background: "var(--lens-accent-soft, rgba(37,99,235,.12))", color: "var(--lens-accent, #2563eb)",
            fontSize: 26, marginBottom: 18,
          }}
        >
          {page.glyph}
        </div>
        <h2 style={{ margin: "0 0 10px", fontSize: 24 }}>{page.title}</h2>
        <p className="muted" style={{ margin: "0 0 18px", lineHeight: 1.65, maxWidth: 560 }}>
          {page.body}
        </p>
        <ul style={{ margin: "0 0 26px", padding: 0, listStyle: "none", display: "grid", gap: 10 }}>
          {page.points.map((p, i) => (
            <li key={i} className="row" style={{ gap: 10, fontSize: 14 }}>
              <span
                aria-hidden
                style={{
                  width: 22, height: 22, borderRadius: 999, flex: "0 0 auto",
                  display: "grid", placeItems: "center", fontSize: 12,
                  background: "var(--lens-accent-soft, rgba(37,99,235,.12))", color: "var(--lens-accent, #2563eb)",
                }}
              >
                ✓
              </span>
              {p}
            </li>
          ))}
        </ul>

        {step === 2 && (
          <div className="row" style={{ gap: 10, marginBottom: 18, flexWrap: "wrap" }}>
            <button className="btn secondary" disabled={installing} onClick={installOllama}>
              {installing ? t.settings.installing : t.settings.installOllama}
            </button>
            {aiStatus && <span className="muted" style={{ fontSize: 13 }}>{aiStatus}</span>}
          </div>
        )}

        <div
          className="row"
          style={{ justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}
        >
          <div className="row" aria-hidden style={{ gap: 8 }}>
            {pages.map((_, i) => (
              <span
                key={i}
                style={{
                  width: i === step ? 22 : 8, height: 8, borderRadius: 999,
                  background: i === step ? "var(--lens-accent, #2563eb)" : "var(--border)",
                  transition: "width .2s ease",
                }}
              />
            ))}
            <span className="muted" style={{ fontSize: 12, marginInlineStart: 6 }}>
              {t.welcome.step} {step + 1} {t.welcome.of} 3
            </span>
          </div>
          <div className="row" style={{ gap: 8 }}>
            <button className="btn secondary" onClick={closeWelcome}>
              {t.welcome.skip}
            </button>
            {step > 0 && (
              <button className="btn secondary" onClick={() => setStep((s) => s - 1)}>
                {t.welcome.back}
              </button>
            )}
            {step < 2 ? (
              <button className="btn" onClick={() => setStep((s) => s + 1)}>
                {t.welcome.next}
              </button>
            ) : (
              <button className="btn" onClick={closeWelcome}>
                {t.welcome.done}
              </button>
            )}
          </div>
        </div>
        <p className="muted" style={{ fontSize: 12, margin: "16px 0 0" }}>{t.welcome.note}</p>
      </div>
    </div>
  );
}
