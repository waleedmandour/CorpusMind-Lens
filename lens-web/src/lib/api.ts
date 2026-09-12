// Thin API wrapper around the engine. Endpoint shapes mirror
// shared/lens-api.d.ts (generated — see shared/README.md).
declare const __ENGINE_BASE_URL__: string;
declare const __LENS_VERSION__: string;

const BASE = typeof __ENGINE_BASE_URL__ !== "undefined" ? __ENGINE_BASE_URL__ : "http://127.0.0.1:8765";
export const ENGINE_URL = BASE;
export const LENS_VERSION = typeof __LENS_VERSION__ !== "undefined" ? __LENS_VERSION__ : "0.1.0";

export class LensApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}/api/v1${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const body = await r.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      /* keep statusText */
    }
    throw new LensApiError(r.status, detail);
  }
  return r.json() as Promise<T>;
}

export const api = {
  health: () => req<{ status: string; version: string; product: string }>("/health"),
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
  aiBackendStatus: () => (window as any).__TAURI__?.core.invoke("ai_backend_status"),
  aiBackendStart: () => (window as any).__TAURI__?.core.invoke("ai_backend_start"),
  aiBackendRestart: () => (window as any).__TAURI__?.core.invoke("ai_backend_restart"),
  installOllama: () => (window as any).__TAURI__?.core.invoke("ai_install_ollama"),
  machineSpecs: () => (window as any).__TAURI__?.core.invoke("machine_specs_command"),
  /** Subscribe to silent-install progress events; returns an unlisten fn. */
  onInstallProgress: (cb: (e: any) => void): Promise<() => void> | undefined =>
    (window as any).__TAURI__?.event?.listen("ai-install://progress", (ev: any) => cb(ev.payload)),
};
