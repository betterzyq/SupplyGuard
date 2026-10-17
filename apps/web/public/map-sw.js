/* Cache public map application assets only. Never cache tokens, auth or API responses. */
const CACHE = "supplyguard-public-map-v2";
const PAGES = ["/supply-chain", "/tracking"];
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) =>
  event.waitUntil(self.clients.claim()),
);
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin)
    return;
  const asset =
    url.pathname.startsWith("/_next/static/") ||
    url.pathname.startsWith("/maps/");
  const navigation =
    event.request.mode === "navigate" && PAGES.includes(url.pathname);
  if (!asset && !navigation) return;
  event.respondWith(
    (async () => {
      const cache = await caches.open(CACHE);
      if (asset) {
        const stored = await cache.match(event.request);
        if (stored) return stored;
      }
      try {
        const response = await fetch(event.request);
        if (response.ok && response.type !== "opaque")
          await cache.put(
            navigation ? url.pathname : event.request,
            response.clone(),
          );
        return response;
      } catch (error) {
        const stored = await cache.match(
          navigation ? url.pathname : event.request,
        );
        if (stored) return stored;
        return new Response(
          "Offline resource unavailable; connect and prepare the demo first.",
          {
            status: 503,
            headers: { "Content-Type": "text/plain; charset=utf-8" },
          },
        );
      }
    })(),
  );
});
