/* CorpusMind Lens PWA offline shell (browser only; never registered inside
 * the Tauri desktop shell, where a cached app shell previously caused blank
 * windows after upgrades).
 *
 * Caching policy (v0.2.0 rebuild):
 *   - Navigations (index.html): NETWORK-FIRST with cache fallback. The app
 *     shell can therefore never be served stale after an update.
 *   - Hashed build assets (/assets/*): CACHE-FIRST. Their names change with
 *     every build, so a cache hit is always correct.
 *   - Engine API (/api/*, cross-origin 127.0.0.1:8765): never touched.
 *     Research data must never be served stale from a cache.
 */
const CACHE = "lens-shell-v2";
const SHELL = ["/", "/index.html", "/icon-lens.svg", "/manifest.webmanifest"];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.pathname.startsWith("/api/")) return; // never cache research data
  if (url.origin !== location.origin) return;   // engine and other origins bypass

  // 1. Document navigations: network first, cache fallback, then offline shell.
  if (req.mode === "navigate") {
    e.respondWith(
      fetch(req)
        .then((r) => {
          if (r.ok) {
            const copy = r.clone();
            caches.open(CACHE).then((c) => c.put("/index.html", copy));
          }
          return r;
        })
        .catch(async () =>
          (await caches.match("/index.html")) ||
          (await caches.match("/")) ||
          new Response("Offline", { status: 503, headers: { "Content-Type": "text/plain" } })
        )
    );
    return;
  }

  // 2. Hashed build assets: cache first (names are content-hashed per build).
  if (url.pathname.startsWith("/assets/")) {
    e.respondWith(
      caches.match(req).then(
        (hit) =>
          hit ||
          fetch(req).then((r) => {
            if (r.ok) {
              const copy = r.clone();
              caches.open(CACHE).then((c) => c.put(req, copy));
            }
            return r;
          })
      )
    );
    return;
  }

  // 3. Everything else (icons, manifest): network first, cache fallback.
  e.respondWith(
    fetch(req)
      .then((r) => {
        if (r.ok) {
          const copy = r.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return r;
      })
      .catch(() => caches.match(req).then((hit) => hit || Response.error()))
  );
});
