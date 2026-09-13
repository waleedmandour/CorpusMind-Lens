import { useState } from "react";
import { useShell } from "../shell";

/**
 * User Guide (v0.3) — the in-app accordion guide (a parent-app borrow),
 * replacing the PDF as the first line of help. Ten task-oriented chapters,
 * fully bilingual. The visual welcome tour remains replayable from Settings.
 */
export function GuideView() {
  const { t } = useShell();
  const [open, setOpen] = useState<number | null>(0);

  const sections = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => ({
    title: (t.guide as any)[`s${n}Title`],
    body: (t.guide as any)[`s${n}Body`],
  }));

  return (
    <div>
      <h2>{t.guide.title}</h2>
      <p className="muted" style={{ maxWidth: 720, marginTop: 0 }}>{t.guide.intro}</p>

      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        {sections.map((s, i) => (
          <div key={i} style={{ borderBottom: i < sections.length - 1 ? "1px solid var(--border)" : undefined }}>
            <button
              className="guide-head"
              aria-expanded={open === i}
              onClick={() => setOpen(open === i ? null : i)}
            >
              <span>{s.title}</span>
              <span aria-hidden>{open === i ? "▾" : "▸"}</span>
            </button>
            {open === i && (
              <p style={{
                margin: 0, padding: "0 16px 14px", fontSize: 13.5,
                lineHeight: 1.7, maxWidth: 760,
              }}>
                {s.body}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
