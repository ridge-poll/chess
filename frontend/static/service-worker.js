const CACHE_NAME = "chess-analytics-v21";
const APP_SHELL = [
  "/",
  "/static/styles.css?v=21",
  "/static/app.js?v=21",
  "/static/manifest.webmanifest?v=21",
  "/static/icon.svg?v=21",
  "/static/pieces/cburnett/wk.svg",
  "/static/pieces/cburnett/wq.svg",
  "/static/pieces/cburnett/wr.svg",
  "/static/pieces/cburnett/wb.svg",
  "/static/pieces/cburnett/wn.svg",
  "/static/pieces/cburnett/wp.svg",
  "/static/pieces/cburnett/bk.svg",
  "/static/pieces/cburnett/bq.svg",
  "/static/pieces/cburnett/br.svg",
  "/static/pieces/cburnett/bb.svg",
  "/static/pieces/cburnett/bn.svg",
  "/static/pieces/cburnett/bp.svg"
];

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api/")) {
    return;
  }
  event.respondWith(
    fetch(event.request).then((response) => {
      if (response.ok) {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
      }
      return response;
    }).catch(() => caches.match(event.request))
  );
});
