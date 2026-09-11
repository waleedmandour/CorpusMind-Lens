import { useEffect, useState } from "react";
import { useShell } from "../shell";
import { api } from "../lib/api";

interface Msg {
  role: "user" | "assistant";
  text: string;
  toolCalls?: { tool: string; grounded: boolean; summary: string }[];
}

export function AssistantView() {
  const { t, activeSetId } = useShell();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [tools, setTools] = useState<string[]>([]);

  useEffect(() => {
    api.assistantTools().then((ts) => setTools(ts.map((x: any) => x.name))).catch(() => undefined);
  }, []);

  const ask = async () => {
    if (!q.trim() || busy) return;
    const question = q.trim();
    setQ("");
    setMsgs((m) => [...m, { role: "user", text: question }]);
    setBusy(true);
    try {
      const res = await api.assistantAsk({ question, set_id: activeSetId });
      setMsgs((m) => [
        ...m,
        { role: "assistant", text: res.answer, toolCalls: res.tool_calls },
      ]);
    } catch (e: any) {
      setMsgs((m) => [...m, { role: "assistant", text: `⚠ ${e.message}` }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <h2>{t.nav.assistant}</h2>
      <div className="notice">{t.assistant.disclaimer}</div>

      <div className="card" style={{ minHeight: 320 }}>
        {msgs.length === 0 && (
          <p className="muted">
            {t.assistant.placeholder}
            <br />
            <span className="evidence">
              tools: {tools.slice(0, 6).join(", ")}… ({tools.length})
            </span>
          </p>
        )}
        {msgs.map((m, i) => (
          <div key={i} style={{ margin: "10px 0", textAlign: m.role === "user" ? "end" : "start" }}>
            <div
              style={{
                display: "inline-block",
                maxWidth: "80%",
                background: m.role === "user" ? "var(--lens-accent)" : "var(--surface-2)",
                color: m.role === "user" ? "#fff" : "var(--text)",
                padding: "10px 14px",
                borderRadius: 12,
                whiteSpace: "pre-wrap",
                textAlign: "start",
              }}
            >
              {m.text.split(/(\[ungrounded\][^.]*)/g).map((part, j) =>
                part.startsWith("[ungrounded]") ? (
                  <span key={j} style={{ color: "var(--danger)" }}>{part}</span>
                ) : (
                  <span key={j}>{part}</span>
                )
              )}
            </div>
            {m.toolCalls && m.toolCalls.length > 0 && (
              <div style={{ marginTop: 4 }}>
                <span className="muted" style={{ fontSize: 12 }}>{t.assistant.toolsUsed}: </span>
                {m.toolCalls.map((tc, j) => (
                  <span key={j} className={`chip ${tc.grounded ? "grounded" : "ungrounded"}`}>
                    {tc.tool} {tc.grounded ? "✓" : "✗"}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="row">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask()}
          placeholder={t.assistant.placeholder}
          aria-label={t.nav.assistant}
          style={{
            flex: 1, padding: "10px 12px", borderRadius: 8,
            border: "1px solid var(--border)", background: "var(--surface-2)",
          }}
        />
        <button className="btn" onClick={ask} disabled={busy}>
          {busy ? t.common.processing : t.assistant.ask}
        </button>
      </div>
    </div>
  );
}
