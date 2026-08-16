// Cachar bara app-SKALET (HTML/JS/ikoner), inte portföljdatan - den
// hämtas alltid färsk via app.js (som i sin tur har sin egen
// localStorage-cache för direkt visning innan nätverket svarat).
const CACHE_NAMN = "portfolj-app-shell-v1";
const SKAL_FILER = ["./", "index.html", "app.js", "config.js", "manifest.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAMN).then((cache) => cache.addAll(SKAL_FILER))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((namn) =>
      Promise.all(namn.filter((n) => n !== CACHE_NAMN).map((n) => caches.delete(n)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  // Låt datahämtningen (gist) alltid gå till nätverket - cachas inte här.
  if (url.hostname.includes("gist")) return;

  event.respondWith(
    caches.match(event.request).then((cachead) => cachead || fetch(event.request))
  );
});
