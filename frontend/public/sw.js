// Cache only the generic offline page. Never cache APIs, tokens, or patient data.
const cacheName = 'spandan-offline-v1';
self.addEventListener('install', event => event.waitUntil(caches.open(cacheName).then(cache => cache.add('/offline.html')).then(() => self.skipWaiting())));
self.addEventListener('activate', event => event.waitUntil(caches.keys().then(names => Promise.all(names.filter(name => name.startsWith('spandan-') && name !== cacheName).map(name => caches.delete(name)))).then(() => self.clients.claim())));
self.addEventListener('fetch', event => {
  if (event.request.mode === 'navigate' && new URL(event.request.url).origin === self.location.origin) {
    event.respondWith(fetch(event.request).catch(() => caches.match('/offline.html')));
  }
});
