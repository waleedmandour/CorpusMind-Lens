/**
 * Task-bar store (v0.3) — Smart Troubleshooting adapted from the parent
 * CorpusMind's zustand store to plain React (useSyncExternalStore; Lens
 * carries no state library). Responsibilities:
 *
 *  1. Capture every failed API call (the api.ts error listener) with a
 *     5-second dedupe window and a 20-issue memory.
 *  2. Poll /health every 15 s; two consecutive failures flag the engine
 *     offline; recovery auto-resolves NETWORK issues.
 *  3. Track background image-processing counts for the active set.
 *  4. Compute the suggested next step from app state (the workflow hint).
 *  5. Offline fix rules: an instant one-line suggestion per issue, no AI
 *     needed. Local-model interpretation is an optional extra layer
 *     (POST /troubleshoot/interpret) — never a cloud call.
 */
import { useEffect, useSyncExternalStore } from "react";
import { api, setApiErrorListener } from "../lib/api";

export type Severity = "info" | "warning" | "error";

export interface Issue {
  id: string;
  timestamp: string;
  message: string;
  code: string | number;
  endpoint: string | null;
  context: string | null;
  resolved: boolean;
  /** Instant offline one-liner, computed at capture time. */
  suggestion: string;
  /** Local-model interpretation: null = loading, undefined = not requested. */
  interpretation?: {
    available: boolean;
    severity?: Severity;
    plain_language: string;
    likely_cause?: string;
    suggested_fix?: string;
    should_report?: boolean;
    model?: string;
  } | null;
}

export interface ProcessingJob {
  setId: string | null;
  setName: string;
  processing: number;
  total: number;
}

interface TaskBarState {
  issues: Issue[];
  backendReachable: boolean;
  panelOpen: boolean;
  muted: boolean;
  job: ProcessingJob | null;
  nextStep: { id: string; label: string; view?: string } | null;
}

const DEDUP_WINDOW_MS = 5_000;
const MAX_ISSUES = 20;

let state: TaskBarState = {
  issues: [],
  backendReachable: true,
  panelOpen: false,
  muted: (typeof localStorage !== "undefined" && localStorage.getItem("lens.taskbar.muted") === "1") || false,
  job: null,
  // First-run hint before the Images page reports real state.
  nextStep: { id: "import", label: "nextImport", view: "images" },
};

const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

function set(patch: Partial<TaskBarState>) {
  state = { ...state, ...patch };
  emit();
}

function subscribe(fn: () => void): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

function getSnapshot(): TaskBarState {
  return state;
}

/** React hook — re-renders on every task-bar state change. */
export function useTaskBar(): TaskBarState {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

// ── Offline fix rules (parent's suggestFix, adapted to Lens) ────────────────
export function suggestFix(message: string, code: string | number, endpoint: string | null): string {
  const m = (message || "").toLowerCase();
  const ep = (endpoint || "").toLowerCase();

  if (m.includes("model call failed") || m.includes("[ollama]") || m.includes("[lmstudio]")) {
    if (m.includes("400") || m.includes("bad request")) {
      return "Open Settings, AI backend & models and pick a tool-capable text model (e.g. llama3.1, qwen2.5); the current one rejected the request.";
    }
    return "Make sure the model server (Ollama / LM Studio) is running, then retry.";
  }
  if (m.includes("does not support image input") || m.includes("no vision model")) {
    return "Install a vision model: Settings, AI backend & models, pull qwen3-vl:2b (multilingual OCR incl. Arabic), then retry.";
  }
  if (m.includes("semantic") && (m.includes("409") || m.includes("unavailable"))) {
    return "Semantic search needs an embedding model — Settings, AI backend & models, pull bge-m3.";
  }
  if (m.includes("magic-byte")) {
    return "The file is not a real image — re-export it as PNG or JPEG and upload again.";
  }
  if (m.includes("rename the file")) {
    return "The file extension does not match its content — rename it to the real format before uploading.";
  }
  if (m.includes("per-image limit") || (code === 413 && ep.includes("image"))) {
    return "The image exceeds the size limit — downscale or recompress it and upload again.";
  }
  if (m.includes("too many files")) {
    return "Split the upload into smaller batches.";
  }
  if (m.includes("batch run is already in progress")) {
    return "A batch run is already running for this set — watch the task bar or wait for it to finish.";
  }
  if (code === 404 || m.includes("404")) {
    if (ep.includes("stoplist")) return "That stoplist no longer exists — reopen the stoplist manager to refresh.";
    if (ep.includes("imageset") || ep.includes("corpus")) return "This image set no longer exists — re-select it from the Images page.";
    return "The requested item was not found — it may have been deleted; refresh the view.";
  }
  if (code === 422 || m.includes("422")) {
    if (ep.includes("stoplist")) return "Built-in stoplists are managed by the engine — use a custom name for your list.";
    return "The request was rejected — check your input values and try again.";
  }
  if (code === 429 || m.includes("429") || m.includes("rate limit")) {
    return "Rate limit reached — wait a few seconds before retrying.";
  }
  if (code === "NETWORK" || (typeof code === "string" && code.toUpperCase().includes("NETWORK"))) {
    return "Check that the Lens engine is running (the desktop app starts it automatically on port 8765 or nearby).";
  }
  if (code === 504 || (typeof code === "string" && code.includes("504")) || m.includes("gateway") || m.includes("timed out")) {
    return "The server timed out — wait a minute and retry.";
  }
  if (code === 500 || m.includes("500") || m.includes("internal server error")) {
    return "Internal engine error — retry the action; if it repeats, use Report to developer below.";
  }
  return "Retry the action; if it persists, use Report to developer below.";
}

// ── Error capture ────────────────────────────────────────────────────────────
const recentErrors = new Map<string, number>();

export function captureError(params: {
  message: string;
  code?: string | number;
  endpoint?: string | null;
  context?: string | null;
}): void {
  const code = params.code ?? "UNKNOWN";
  const key = `${code}:${params.endpoint ?? "unknown"}`;
  const now = Date.now();
  const last = recentErrors.get(key);
  if (last && now - last < DEDUP_WINDOW_MS) return;
  recentErrors.set(key, now);
  if (recentErrors.size > 50) {
    for (const [k, t] of recentErrors) {
      if (now - t > DEDUP_WINDOW_MS * 4) recentErrors.delete(k);
    }
  }
  const issue: Issue = {
    id: `${now}-${Math.random().toString(36).slice(2, 8)}`,
    timestamp: new Date().toISOString(),
    message: params.message,
    code,
    endpoint: params.endpoint ?? null,
    context: params.context ?? null,
    resolved: false,
    suggestion: suggestFix(params.message, code, params.endpoint ?? null),
  };
  set({ issues: [issue, ...state.issues].slice(0, MAX_ISSUES), panelOpen: state.muted ? state.panelOpen : true });
}

export function resolveIssue(id: string): void {
  set({ issues: state.issues.map((i) => (i.id === id ? { ...i, resolved: true } : i)) });
}
export function clearResolved(): void {
  set({ issues: state.issues.filter((i) => !i.resolved) });
}
export function clearAll(): void {
  set({ issues: [], panelOpen: false });
}
export function setPanelOpen(open: boolean): void {
  set({ panelOpen: open });
}
export function setMuted(muted: boolean): void {
  localStorage.setItem("lens.taskbar.muted", muted ? "1" : "0");
  set({ muted });
}

// ── Local-model interpretation (never cloud) ────────────────────────────────
export async function fetchInterpretation(issueId: string): Promise<void> {
  const issue = state.issues.find((i) => i.id === issueId);
  if (!issue) return;
  set({ issues: state.issues.map((i) => (i.id === issueId ? { ...i, interpretation: null } : i)) });
  try {
    const verdict = await api.troubleshootInterpret({
      error_message: issue.message,
      error_code: issue.code,
      endpoint: issue.endpoint,
      context: issue.context,
    });
    set({ issues: state.issues.map((i) => (i.id === issueId ? { ...i, interpretation: verdict } : i)) });
  } catch {
    set({
      issues: state.issues.map((i) => (i.id === issueId ? {
        ...i,
        interpretation: {
          available: false,
          severity: "info" as Severity,
          plain_language: "The interpretation request itself failed. The instant fix above still applies.",
          likely_cause: "",
          suggested_fix: "",
          should_report: false,
          model: "",
        },
      } : i)),
    });
  }
}

// ── Workflow hint + processing job tracking ──────────────────────────────────
export function updateWorkflow(setInfo: {
  activeSetId: string | null;
  activeSetName: string;
  processing: number;
  total: number;
  ready: number;
  hasAnnotations: boolean;
  hasResults: boolean;
} | null): void {
  if (!setInfo || !setInfo.activeSetId) {
    set({
      job: null,
      nextStep: { id: "import", label: "nextImport", view: "images" },
    });
    return;
  }
  const { processing, total, ready, activeSetId, activeSetName, hasAnnotations, hasResults } = setInfo;
  const job = processing > 0
    ? { setId: activeSetId, setName: activeSetName, processing, total }
    : null;
  let nextStep: TaskBarState["nextStep"];
  if (processing > 0) nextStep = { id: "wait", label: "nextWait" };
  else if (total > 0 && ready === 0) nextStep = { id: "wait", label: "nextWait" };
  else if (!hasAnnotations) nextStep = { id: "annotate", label: "nextAnnotate", view: "images" };
  else if (!hasResults) nextStep = { id: "text", label: "nextText", view: "text" };
  else nextStep = { id: "export", label: "nextExport", view: "export" };
  set({ job, nextStep });
}

// ── Health poller (started once from App) ────────────────────────────────────
let pollTimer: ReturnType<typeof setInterval> | null = null;
let failures = 0;

async function poll(): Promise<void> {
  try {
    await api.health();
    failures = 0;
    const wasDown = !state.backendReachable;
    if (wasDown) {
      set({
        backendReachable: true,
        issues: state.issues.map((i) => (i.code === "NETWORK" && !i.resolved ? { ...i, resolved: true } : i)),
      });
    }
  } catch {
    failures += 1;
    if (failures >= 2 && state.backendReachable) {
      set({ backendReachable: false });
      captureError({
        message: "Cannot reach the Lens engine. The analysis backend appears to be offline.",
        code: "NETWORK",
        endpoint: "/health",
        context: "Background health check",
      });
    }
  }
}

export function startTaskBar(): () => void {
  // Error capture from the API layer.
  setApiErrorListener((info) => captureError({
    message: info.message,
    code: info.status,
    endpoint: info.endpoint,
  }));
  // Health poll: immediate, then every 15 s.
  void poll();
  if (!pollTimer) pollTimer = setInterval(poll, 15_000);
  return () => {
    setApiErrorListener(null);
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  };
}
