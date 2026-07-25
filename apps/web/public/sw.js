// naktahu-v2: v1 pre-cached '/' and '/chat' HTML under a never-changing
// cache name and served it cache-first, so after every deploy returning
// visitors got stale HTML pointing at deleted _next chunks (ChunkLoadError,
// text/plain MIME refusals). HTML must never be served cache-first; the
// name bump makes existing clients drop the poisoned v1 cache.
const CACHE_NAME = 'naktahu-v2';
const STATIC_ASSETS = [
  '/manifest.json',
  '/icons/icon.svg',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  // API routes and cross-origin requests: always straight to network.
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/')) return;

  // Navigations (HTML): network-first so a new deploy is picked up
  // immediately; fall back to cache only when offline.
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() =>
        caches.match(event.request).then((cached) => cached ?? Response.error()),
      ),
    );
    return;
  }

  // Immutable hashed build assets and pre-cached statics: cache-first.
  event.respondWith(
    caches.match(event.request).then(
      (cached) => cached ?? fetch(event.request),
    ),
  );
});
