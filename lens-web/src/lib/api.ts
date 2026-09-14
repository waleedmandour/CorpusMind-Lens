// Thin API wrapper around the engine. Endpoint shapes mirror
// shared/lens-api.d.ts (generated — see shared/README.md).
declare const __ENGINE_BASE_URL__: string;
declare const __LENS_VERSION__: string;

let BASE =
  typeof __ENGINE_BASE_URL__ !== "undefined" ? __ENGINE_BASE_URL__ : "http://127.0.0.1:8765";
export function engineUrl(): string {
  return BASE;
}
export const LENS_VERSION = typeof __LENS_VERSION__ !== "undefined" ? __LENS_VERSION__ : "0.1.0";

/** The desktop shell may have started the engine on a fallback port
 * (8765 busy: a Companion engine or a stale process). Call once at boot. */
export function setEngineBase(url: string): void {
  BASE = url.replace(/\/$/, "");
}

export class LensApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

// ── Task-bar error capture (v0.3 Smart Troubleshooting) ───────────────────
// One choke point: every failed API call reports (message, status, endpoint)
// to the task-bar issue store, which dedupes and displays it. Registered
// from state/taskbar.ts to avoid a circular import.
type ApiErrorListener = (info: { message: string; status: number | "NETWORK"; endpoint: string }) => void;
let apiErrorListener: ApiErrorListener | null = null;
export function setApiErrorListener(fn: ApiErrorListener | null): void {
  apiErrorListener = fn;
}
function reportApiError(status: number | "NETWORK", path: string, message: string): void {
  try {
    apiErrorListener?.({ message, status, endpoint: path.replace(/^\/api\/v1/, "") });
  } catch {
    /* the task bar must never break a request path */
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let r: Response;
  try {
    r = await fetch(`${BASE}/api/v1${path}`, {
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      ...init,
    });
  } catch (e: any) {
    reportApiError("NETWORK", path, e?.message ?? "network error");
    throw e;
  }
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const body = await r.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      /* keep statusText */
    }
    reportApiError(r.status, path, String(detail));
    throw new LensApiError(r.status, detail);
  }
  return r.json() as Promise<T>;
}

export type StackStatus = { available: boolean; packages: Record<string, boolean>; enables: string; enable_hint: string };
export type HealthInfo = {
  status: string;
  version: string;
  product: string;
  capabilities?: Record<string, StackStatus>;
};

export const api = {
  health: () => req<HealthInfo>("/health"),
  providersStatus: () =>
    req<{ ollama: { reachable: boolean; models: string[] }; lmstudio: { reachable: boolean } }>(
      "/providers/status"
    ),

  listProjects: () => req<any[]>("/projects"),
  createProject: (name: string, description = "") =>
    req<any>("/projects", { method: "POST", body: JSON.stringify({ name, description }) }),
  deleteProject: (id: string) => req<any>(`/projects/${id}`, { method: "DELETE" }),

  listImageSets: (projectId: string) => req<any[]>(`/projects/${projectId}/imagesets`),
  createImageSet: (payload: any) => req<any>("/imagesets", { method: "POST", body: JSON.stringify(payload) }),
  getImageSet: (id: string) => req<any>(`/imagesets/${id}`),
  getSetStats: (id: string) => req<any>(`/imagesets/${id}/stats`),
  deleteImageSet: (id: string) => req<any>(`/imagesets/${id}`, { method: "DELETE" }),

  listImages: (setId: string) => req<any[]>(`/imagesets/${setId}/images`),
  getImage: (id: string) => req<any>(`/images/${id}`),
  deleteImage: (id: string) => req<any>(`/images/${id}`, { method: "DELETE" }),
  imageThumbnail: (id: string) => `${BASE}/api/v1/images/${id}/thumbnail`,
  uploadImages: async (setId: string, files: File[], ocrLanguage?: string) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    if (ocrLanguage) form.append("ocr_language", ocrLanguage);
    const r = await fetch(`${BASE}/api/v1/imagesets/${setId}/images`, { method: "POST", body: form });
    if (!r.ok) throw new LensApiError(r.status, await r.text());
    return r.json();
  },
  reanalyze: (id: string) => req<any>(`/images/${id}/reanalyze`, { method: "POST" }),

  getAnalysis: (id: string) => req<any>(`/images/${id}/analysis`),
  getAnnotations: (id: string) => req<any>(`/images/${id}/annotations`),
  setAnnotations: (id: string, payload: any) =>
    req<any>(`/images/${id}/annotations`, { method: "PUT", body: JSON.stringify(payload) }),
  annotationSchema: () => req<any>("/annotations/schema"),
  bulkTag: (setId: string, tags: string[], imageIds?: string[]) =>
    req<any>(`/imagesets/${setId}/annotations/bulk-tags`, {
      method: "POST",
      body: JSON.stringify({ tags, image_ids: imageIds ?? null }),
    }),

  detectionStatus: () => req<any>("/detection/status"),
  detectImage: (id: string, categories?: string[]) =>
    req<any>(`/images/${id}/detect`, { method: "POST", body: JSON.stringify(categories ?? null) }),
  typography: (id: string) => req<any>(`/images/${id}/typography`, { method: "POST" }),

  align: (id: string) => req<any>(`/images/${id}/align`, { method: "POST" }),
  visualGrammar: (id: string) => req<any>(`/images/${id}/visual-grammar`, { method: "POST" }),
  crossModal: (id: string) => req<any>(`/images/${id}/cross-modal`, { method: "POST" }),

  discourseFrameworks: () => req<any[]>("/discourse/frameworks"),
  discourseAnalyse: (imageId: string, frameworkId: string, mode: "heuristic" | "llm" = "heuristic") =>
    req<any>(`/images/${imageId}/discourse/${frameworkId}?mode=${mode}`, { method: "POST" }),

  battery: (setId: string, kind: string, dim: string, extra = "") =>
    req<any>(`/imagesets/${setId}/battery/${kind}/${dim}${extra}`),
  fullBattery: (setId: string, dim: string) =>
    req<any>(`/imagesets/${setId}/battery/full?dim=${dim}`),
  compare: (a: string, b: string) => req<any>(`/compare/${a}/${b}`),

  ocrWordlist: (setId: string) => req<any>(`/imagesets/${setId}/ocrtools/wordlist`),
  ocrKwic: (setId: string, query: string) =>
    req<any>(`/imagesets/${setId}/ocrtools/kwic?query=${encodeURIComponent(query)}`),

  // ── v0.3 Text Analysis (AntConc audit) ─────────────────────────────────
  textWordlist: (setId: string, params: Record<string, string | number> = {}) =>
    req<any>(`/imagesets/${setId}/text/wordlist?${new URLSearchParams(
      Object.entries(params).map(([k, v]) => [k, String(v)]))}`),
  textConcordance: (setId: string, params: Record<string, string | number | boolean>) =>
    req<any>(`/imagesets/${setId}/text/concordance?${new URLSearchParams(
      Object.entries(params).map(([k, v]) => [k, String(v)]))}`),
  textCollocations: (setId: string, params: Record<string, string | number | boolean>) =>
    req<any>(`/imagesets/${setId}/text/collocations?${new URLSearchParams(
      Object.entries(params).map(([k, v]) => [k, String(v)]))}`),
  textNgrams: (setId: string, params: Record<string, string | number>) =>
    req<any>(`/imagesets/${setId}/text/ngrams?${new URLSearchParams(
      Object.entries(params).map(([k, v]) => [k, String(v)]))}`),
  textDispersion: (setId: string, stoplist: string) =>
    req<any>(`/imagesets/${setId}/text/dispersion?stoplist=${encodeURIComponent(stoplist)}`),
  textSketch: (setId: string, word: string) =>
    req<any>(`/imagesets/${setId}/text/sketch?word=${encodeURIComponent(word)}`),
  textReferences: (setId: string) => req<any>(`/imagesets/${setId}/text/references`),
  textKeynessReference: (setId: string, reference: string, stoplist: string) =>
    req<any>(`/imagesets/${setId}/text/keyness-reference?reference=${encodeURIComponent(reference)}&stoplist=${encodeURIComponent(stoplist)}`),
  textExportUrl: (setId: string, what: string, format: string, params: Record<string, string | number | boolean>) => {
    const qs = new URLSearchParams({ format, ...Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)])) });
    return `${BASE}/api/v1/imagesets/${setId}/text/${what}?${qs.toString()}`;
  },
  listStoplists: (projectId: string) => req<any>(`/projects/${projectId}/stoplists`),
  createStoplist: (projectId: string, name: string, items: string[]) =>
    req<any>(`/projects/${projectId}/stoplists`, { method: "POST", body: JSON.stringify({ name, items }) }),
  deleteStoplist: (projectId: string, name: string) =>
    req<any>(`/projects/${projectId}/stoplists/${encodeURIComponent(name)}`, { method: "DELETE" }),

  // ── v0.3 default models + Smart Troubleshooting ─────────────────────────
  modelDefaults: () => req<any>("/settings/models"),
  putModelDefaults: (payload: { vision_ocr_model?: string; embed_model?: string; chat_model?: string; clear?: string[] }) =>
    req<any>("/settings/models", { method: "PUT", body: JSON.stringify(payload) }),
  troubleshootStatus: () => req<any>("/troubleshoot/status"),
  troubleshootInterpret: (payload: { error_message: string; error_code?: string | number | null; endpoint?: string | null; context?: string | null }) =>
    req<any>("/troubleshoot/interpret", { method: "POST", body: JSON.stringify(payload) }),

  exportSet: async (setId: string, format: string) => {
    const r = await fetch(`${BASE}/api/v1/imagesets/${setId}/export?format=${format}`);
    if (!r.ok) throw new LensApiError(r.status, "export failed");
    return r.blob();
  },
  methodsSection: (setId: string) => req<any>(`/imagesets/${setId}/methods-section`),

  assistantTools: () => req<any[]>("/assistant/tools"),
  assistantAsk: (payload: any) => req<any>("/assistant/ask", { method: "POST", body: JSON.stringify(payload) }),

  settings: () => req<any>("/settings"),
  ethics: () => req<any>("/settings/ethics"),
  companionStatus: () => req<any>("/companion/status"),

  // ── v0.2 local AI backend & models ──────────────────────────────────────
  aiLocalStatus: () => req<any>("/ai/local/status"),
  aiCatalog: (query = "", task = "any") =>
    req<any>(`/ai/catalog?query=${encodeURIComponent(query)}&task=${task}`),
  aiServeOllama: () => req<any>("/ai/local/serve", { method: "POST", body: "{}" }),
  aiDeleteModel: (name: string) =>
    req<any>("/ai/local/models", { method: "DELETE", body: JSON.stringify({ name }) }),
  semanticSearch: (setId: string, query: string, topK = 20) =>
    req<any>(`/imagesets/${setId}/semantic-search`, {
      method: "POST",
      body: JSON.stringify({ query, top_k: topK }),
    }),
  ocrVision: (imageId: string, model?: string) =>
    req<any>(`/images/${imageId}/ocr/vision${model ? `?model=${encodeURIComponent(model)}` : ""}`,
      { method: "POST" }),

  // ── Social tab (v0.2): imports, connectors, analyses ────────────────────
  socialImport: async (projectId: string, file: File, source: string, options: Record<string, unknown>) => {
    const form = new FormData();
    form.append("file", file);
    form.append("source", source);
    form.append("options", JSON.stringify(options));
    const r = await fetch(`${BASE}/api/v1/projects/${projectId}/social/import`, { method: "POST", body: form });
    if (!r.ok) {
      let detail = r.statusText;
      try { detail = (await r.json()).detail ?? detail; } catch { /* keep */ }
      throw new LensApiError(r.status, typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return r.json();
  },
  socialFetch: (projectId: string, body: Record<string, unknown>) =>
    req<any>(`/projects/${projectId}/social/fetch`, { method: "POST", body: JSON.stringify(body) }),
  listPosts: (projectId: string, platform = "all", limit = 200, offset = 0) =>
    req<any>(`/projects/${projectId}/posts?platform=${encodeURIComponent(platform)}&limit=${limit}&offset=${offset}`),
  deletePosts: (projectId: string, platform = "all") =>
    req<any>(`/projects/${projectId}/posts?platform=${encodeURIComponent(platform)}`, { method: "DELETE" }),
  socialSummary: (projectId: string) => req<any>(`/projects/${projectId}/social/summary`),
  socialAnalyse: (projectId: string, analysis: string, params: Record<string, string | number> = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).map(([k, v]) => [k, String(v)])
    ).toString();
    return req<any>(`/projects/${projectId}/social/${analysis}${qs ? `?${qs}` : ""}`);
  },

  /** Pull a model with live NDJSON progress (status/completed/total). */
  aiPull: async (model: string, onLine: (e: any) => void): Promise<void> => {
    const r = await fetch(`${BASE}/api/v1/ai/local/pull`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    });
    if (!r.ok || !r.body) {
      let detail = r.statusText;
      try { detail = (await r.json()).detail ?? detail; } catch { /* keep */ }
      onLine({ done: true, error: detail });
      return;
    }
    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() ?? "";
      for (const line of lines) {
        if (!line.trim()) continue;
        try { onLine(JSON.parse(line)); } catch { /* skip partial */ }
      }
    }
  },
};

// ── Tauri shell commands (absent when running as a browser PWA) ───────────
// withGlobalTauri is on, so the shell exposes window.__TAURI__.
export function isDesktopShell(): boolean {
  return typeof (window as any).__TAURI__ !== "undefined";
}

export const shell = {
  engineStatus: () => (window as any).__TAURI__?.core.invoke("engine_status"),
  startEngine: () => (window as any).__TAURI__?.core.invoke("start_engine"),
  restartEngine: () => (window as any).__TAURI__?.core.invoke("restart_engine"),
  engineLogs: () => (window as any).__TAURI__?.core.invoke("engine_logs"),
  /** v0.3.2: native Save As dialog (defaults to the OS Downloads folder).
   * Resolves null when the user cancels. */
  chooseExportPath: (defaultFileName: string): Promise<string | null> =>
    (window as any).__TAURI__?.core.invoke("choose_export_path", { defaultFileName }),
  /** v0.3.2: write fetched export bytes (base64) to the chosen path. */
  writeExportFile: (path: string, dataB64: string): Promise<{ saved: boolean; path: string }> =>
    (window as any).__TAURI__?.core.invoke("write_export_file", { path, dataB64 }),
  aiBackendStatus: () => (window as any).__TAURI__?.core.invoke("ai_backend_status"),
  aiBackendStart: () => (window as any).__TAURI__?.core.invoke("ai_backend_start"),
  aiBackendRestart: () => (window as any).__TAURI__?.core.invoke("ai_backend_restart"),
  installOllama: () => (window as any).__TAURI__?.core.invoke("ai_install_ollama"),
  machineSpecs: () => (window as any).__TAURI__?.core.invoke("machine_specs_command"),
  /** Subscribe to silent-install progress events; returns an unlisten fn. */
  onInstallProgress: (cb: (e: any) => void): Promise<() => void> | undefined =>
    (window as any).__TAURI__?.event?.listen("ai-install://progress", (ev: any) => cb(ev.payload)),
};

/** Adopt the port the desktop shell actually started the engine on. */
export async function discoverEnginePort(): Promise<void> {
  if (!isDesktopShell()) return;
  try {
    const st = await shell.engineStatus();
    if (st?.port && st.port !== 8765) setEngineBase(`http://127.0.0.1:${st.port}`);
  } catch {
    /* browser PWA or shell busy: keep the default base */
  }
}

/** Fetch an engine file as base64 (desktop export path writes). */
function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const s = String(reader.result ?? "");
      resolve(s.includes(",") ? s.slice(s.indexOf(",") + 1) : s);
    };
    reader.onerror = () => reject(reader.error ?? new Error("could not read export data"));
    reader.readAsDataURL(blob);
  });
}

export type DownloadOutcome = { savedPath?: string; cancelled?: boolean };

/** Download an engine-generated file (CSV/XML/...) in browser and desktop.
 * Browser: object URL + anchor (lands in the browser's Downloads folder).
 * Desktop (v0.3.2): a native Save As dialog defaults to the OS Downloads
 * folder, the user may pick any location, and the bytes are written there.
 * Returns where the file went so callers can surface the exact path. */
export async function downloadEngineFile(url: string, filename: string): Promise<DownloadOutcome> {
  const r = await fetch(url);
  if (!r.ok) throw new LensApiError(r.status, "export failed");
  const blob = await r.blob();
  if (isDesktopShell()) {
    const chosen = await shell.chooseExportPath(filename);
    if (!chosen) return { cancelled: true };
    const dataB64 = await blobToBase64(blob);
    await shell.writeExportFile(chosen, dataB64);
    return { savedPath: chosen };
  }
  const obj = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = obj;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(obj), 4000);
  return {};
}

export function socialExportUrl(
  projectId: string,
  what: string,
  format: string,
  params: Record<string, string | number> = {}
): string {
  const qs = new URLSearchParams({ format, ...Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)])) });
  return `${BASE}/api/v1/projects/${projectId}/social-export/${what}?${qs.toString()}`;
}

export function batteryExportUrl(
  setId: string,
  kind: string,
  format: string,
  params: Record<string, string | number> = {}
): string {
  const qs = new URLSearchParams({ format, ...Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)])) });
  return `${BASE}/api/v1/imagesets/${setId}/battery-export/${kind}?${qs.toString()}`;
}
