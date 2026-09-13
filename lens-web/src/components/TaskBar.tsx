/**
 * TaskBar (v0.3) — the parent app's bottom bar, adapted to Lens.
 *
 * Always visible. Left: engine state + background processing progress.
 * Centre: a red badge when issues exist. Right: the suggested next step and
 * the app version. Clicking the badge (or the engine chip when offline)
 * expands a panel with issue cards: plain-language message, code/endpoint,
 * an instant offline fix, an optional LOCAL-model interpretation, resolve
 * and report-to-developer actions. Nothing ever leaves the machine.
 */
import { useState } from "react";
import { isDesktopShell, LENS_VERSION } from "../lib/api";
import { useShell } from "../shell";
import {
  fetchInterpretation, resolveIssue, clearResolved, clearAll, setPanelOpen,
  setMuted, useTaskBar, type Issue,
} from "../state/taskbar";

const DEVELOPER_EMAIL = "w.abumandour@squ.edu.om";

function severityIcon(sev: string): string {
  return sev === "error" || sev === "warning" ? "\u26A0" : "\u2139";
}

function buildMailto(issue: Issue, langNote: string): string {
  const subject = `[CorpusMind Lens Bug Report] ${issue.message.slice(0, 80)}`;
  const lines: string[] = [
    "Dear Dr. Mandour,",
    "",
    "I encountered the following issue while using CorpusMind Lens and would like to report it.",
    "",
    "=== ISSUE DETAILS ===",
    `Timestamp: ${issue.timestamp}`,
    `Code: ${issue.code}`,
    `Endpoint: ${issue.endpoint ?? "N/A"}`,
    `Context: ${issue.context ?? "N/A"}`,
    `Message: ${issue.message}`,
    "",
  ];
  if (issue.suggestion) lines.push(`=== INSTANT SUGGESTION === ${issue.suggestion}`, "");
  const interp = issue.interpretation;
  if (interp?.available) {
    lines.push(
      "=== LOCAL MODEL INTERPRETATION ===",
      `Severity: ${interp.severity}`,
      `Plain language: ${interp.plain_language}`,
      `Likely cause: ${interp.likely_cause ?? ""}`,
      `Suggested fix: ${interp.suggested_fix ?? ""}`,
      `Model: ${interp.model ?? ""}`,
      "",
    );
  }
  lines.push(
    "=== ENVIRONMENT ===",
    `Lens version: ${LENS_VERSION}`,
    `Browser: ${navigator.userAgent}`,
    "",
    "Steps to reproduce:",
    "1. ",
    "2. ",
    "3. ",
    "",
    langNote,
    "",
    "Best regards,",
  );
  return `mailto:${DEVELOPER_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(lines.join("\n"))}`;
}

function IssueCard({ issue, t }: { issue: Issue; t: any }) {
  const [showFull, setShowFull] = useState(false);
  const sev = issue.interpretation?.severity ?? "error";
  const interp = issue.interpretation;

  return (
    <div className={`tb-issue ${sev === "error" ? "tb-sev-error" : sev === "warning" ? "tb-sev-warn" : "tb-sev-info"} ${issue.resolved ? "tb-resolved" : ""}`}>
      <div className="row" style={{ alignItems: "flex-start", gap: 8 }}>
        <span aria-hidden>{severityIcon(sev)}</span>
        <div style={{ flex: 1, minWidth: 220 }}>
          <div className="tb-msg">
            {issue.message.length > 140 && !showFull
              ? `${issue.message.slice(0, 140)}… `
              : issue.message}
            {issue.message.length > 140 && (
              <button className="lens-link" style={{ marginInlineStart: 6 }} onClick={() => setShowFull(!showFull)}>
                {showFull ? t.taskbar.showLess : t.taskbar.showFull}
              </button>
            )}
          </div>
          <div className="tb-tags">
            <span className="tb-tag">{t.common.error}: {issue.code}</span>
            {issue.endpoint && <span className="tb-tag">{issue.endpoint}</span>}
            <span className="tb-tag">{new Date(issue.timestamp).toLocaleTimeString()}</span>
            {issue.resolved && <span className="tb-tag tb-tag-ok">{t.taskbar.resolve}</span>}
          </div>
        </div>
        {!issue.resolved && (
          <button className="btn secondary" style={{ padding: "2px 10px" }}
                  title={t.taskbar.resolve} onClick={() => resolveIssue(issue.id)}>
            ✓
          </button>
        )}
      </div>

      {issue.suggestion && (
        <div className="tb-suggestion" role="note">
          <strong>{t.taskbar.fixLabel}:</strong> {issue.suggestion}
        </div>
      )}

      {interp === null && (
        <div className="tb-interp muted">{t.taskbar.explaining}</div>
      )}
      {interp && interp.available && (
        <div className={`tb-interp ${interp.severity === "error" ? "tb-sev-error" : interp.severity === "warning" ? "tb-sev-warn" : "tb-sev-info"}`}>
          <div><strong>{t.taskbar.whatHappened}:</strong> {interp.plain_language}</div>
          {interp.likely_cause && <div><strong>{t.taskbar.likelyCause}:</strong> {interp.likely_cause}</div>}
          {interp.suggested_fix && <div><strong>{t.taskbar.suggestedFix}:</strong> {interp.suggested_fix}</div>}
          {interp.model && <div className="evidence">{t.taskbar.interpretedBy} {interp.model} (local)</div>}
        </div>
      )}
      {interp && !interp.available && (
        <div className="tb-interp muted">{t.taskbar.interpUnavailable}</div>
      )}

      <div className="row" style={{ gap: 8, marginTop: 6 }}>
        {!interp && (
          <button className="btn secondary" style={{ padding: "3px 10px", fontSize: 12 }}
                  onClick={() => fetchInterpretation(issue.id)}>
            {t.taskbar.explain}
          </button>
        )}
        <a className="btn secondary" style={{ padding: "3px 10px", fontSize: 12, textDecoration: "none" }}
           href={buildMailto(issue, "")} title={DEVELOPER_EMAIL}>
          ✉ {t.taskbar.report}
        </a>
      </div>
    </div>
  );
}

export function TaskBar() {
  const { t, setView } = useShell();
  const tb = useTaskBar();
  const unresolved = tb.issues.filter((i) => !i.resolved);
  const showBadge = !tb.muted && (unresolved.length > 0 || !tb.backendReachable);
  const nextLabel = tb.nextStep
    ? (t.taskbar as Record<string, string>)[tb.nextStep.label] ?? ""
    : "";

  return (
    <div className="tb-root">
      {tb.panelOpen && (
        <div className="tb-panel" role="dialog" aria-label={t.taskbar.panelTitle}>
          <div className="tb-panel-head">
            <strong>{t.taskbar.panelTitle}</strong>
            <div className="row" style={{ gap: 8 }}>
              <button className="lens-link" onClick={() => setMuted(!tb.muted)}>
                {tb.muted ? t.taskbar.unmute : t.taskbar.mute}
              </button>
              {tb.issues.some((i) => i.resolved) && (
                <button className="lens-link" onClick={clearResolved}>{t.taskbar.clearResolved}</button>
              )}
              {tb.issues.length > 0 && (
                <button className="lens-link" onClick={clearAll}>{t.taskbar.clearAll}</button>
              )}
              <button className="lens-link" aria-label={t.common.cancel} onClick={() => setPanelOpen(false)}>✕</button>
            </div>
          </div>
          {tb.muted && <div className="tb-muted-banner">{t.taskbar.mutedBanner}</div>}
          <div className="tb-panel-body">
            {tb.issues.length === 0 ? (
              <div className="muted" style={{ padding: "10px 4px" }}>
                {t.taskbar.noIssues}
                {!tb.backendReachable && <div style={{ marginTop: 6, fontSize: 12 }}>{t.taskbar.networkHint}</div>}
              </div>
            ) : (
              tb.issues.map((i) => <IssueCard key={i.id} issue={i} t={t} />)
            )}
          </div>
        </div>
      )}

      <div className="tb-bar">
        <div className="tb-left">
          <button
            className={`tb-chip ${tb.backendReachable ? "tb-ok" : "tb-down"}`}
            onClick={() => !tb.backendReachable && setPanelOpen(true)}
            title={tb.backendReachable ? t.taskbar.engineOk : t.taskbar.networkHint}
          >
            <span className="tb-dot" aria-hidden />
            {tb.backendReachable ? t.taskbar.engineOk : t.taskbar.engineOffline}
          </button>
          {tb.job && (
            <span className="tb-chip tb-job" role="status">
              <span className="tb-spinner" aria-hidden />
              {t.taskbar.processing} {tb.job.processing}/{tb.job.total} {t.taskbar.processingImages}
            </span>
          )}
        </div>

        <div className="tb-right">
          {nextLabel && (
            <button
              className="tb-next"
              onClick={() => tb.nextStep?.view && setView(tb.nextStep.view as any)}
              title={nextLabel}
            >
              <strong>{t.taskbar.nextTitle}:</strong> {nextLabel}
            </button>
          )}
          {showBadge && (
            <button
              className={`tb-badge ${unresolved.length > 0 ? "tb-bad" : "tb-bad tb-down"}`}
              onClick={() => setPanelOpen(!tb.panelOpen)}
              aria-expanded={tb.panelOpen}
            >
              {unresolved.length > 0
                ? `${unresolved.length} ${unresolved.length === 1 ? t.taskbar.issue : t.taskbar.issues}`
                : t.taskbar.engineOffline}
              <span aria-hidden>{tb.panelOpen ? "▲" : "▼"}</span>
            </button>
          )}
          <span className="tb-version">v{LENS_VERSION}</span>
        </div>
      </div>
    </div>
  );
}
