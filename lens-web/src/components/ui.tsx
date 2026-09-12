import React, { useState } from "react";
import { useShell } from "../shell";
import { downloadEngineFile } from "../lib/api";

/** CSV / XML / TSV / JSON export buttons for any analysis outcome.
 * The engine renders the file; this component only downloads it via an
 * object URL (works in the browser PWA and the Tauri webview alike). */
export function ExportButtons({
  build,
}: {
  build: (format: string) => { url: string; filename: string } | null;
}) {
  const { t, toast } = useShell();
  const [busy, setBusy] = useState(false);
  const formats = ["csv", "xml", "tsv", "json"];
  return (
    <span className="row" style={{ gap: 6, flexWrap: "wrap" }}>
      <span className="muted" style={{ fontSize: 12 }}>{t.common.export}:</span>
      {formats.map((f) => (
        <button
          key={f}
          className="btn secondary"
          style={{ padding: "3px 10px", fontSize: 12 }}
          disabled={busy}
          onClick={async () => {
            const target = build(f);
            if (!target) return;
            setBusy(true);
            try {
              await downloadEngineFile(target.url, target.filename);
              toast(`${target.filename}`);
            } catch (e: any) {
              toast(`${t.common.error}: ${e?.message ?? e}`, "error");
            } finally {
              setBusy(false);
            }
          }}
        >
          {f.toUpperCase()}
        </button>
      ))}
    </span>
  );
}

export function EmptyState({
  glyph, title, hint, action,
}: {
  glyph: string;
  title: string;
  hint?: string;
  action?: React.ReactNode;
}) {
  return (
    <div
      className="lens-empty"
      style={{
        textAlign: "center", padding: "44px 20px", border: "1px dashed var(--border)",
        borderRadius: 14, background: "var(--surface-2)", margin: "10px 0",
      }}
    >
      <div aria-hidden style={{ fontSize: 34, marginBottom: 8 }}>{glyph}</div>
      <div style={{ fontWeight: 600, marginBottom: 6 }}>{title}</div>
      {hint && (
        <div className="muted" style={{ fontSize: 13, maxWidth: 520, margin: "0 auto 14px", lineHeight: 1.6 }}>
          {hint}
        </div>
      )}
      {action}
    </div>
  );
}

/** Light data table for result profiles (frequency lists, emoji, edges...). */
export function RowsTable({
  columns, rows, max = 100,
}: {
  columns: { key: string; label: string; align?: "start" | "end" }[];
  rows: Record<string, any>[];
  max?: number;
}) {
  return (
    <div style={{ overflowX: "auto", maxHeight: 420, overflowY: "auto", border: "1px solid var(--border)", borderRadius: 10 }}>
      <table className="lens-table" style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                style={{
                  position: "sticky", top: 0, background: "var(--surface-2)",
                  textAlign: c.align === "end" ? "end" : "start",
                  padding: "8px 10px", borderBottom: "1px solid var(--border)", fontWeight: 600,
                }}
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, max).map((r, i) => (
            <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
              {columns.map((c) => (
                <td
                  key={c.key}
                  style={{
                    padding: "7px 10px",
                    textAlign: c.align === "end" ? "end" : "start",
                    whiteSpace: c.key === "text" ? "normal" : "nowrap",
                    maxWidth: c.key === "text" ? 420 : undefined,
                  }}
                >
                  {String(r[c.key] ?? "")}
                </td>
              ))}
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={columns.length} style={{ padding: 14, textAlign: "center" }} className="muted">
                {"-"}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
