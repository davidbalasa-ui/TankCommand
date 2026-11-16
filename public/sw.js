// Retires the service worker the old prototype installed at this address. It cached every page
// and file it fetched and answered offline requests with the old page. The rebuilt game does not
// use a service worker, so this one clears those caches, unregisters itself and reloads any open
// tab onto the live site.
self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(keys.map((key) => caches.delete(key)));
      await self.registration.unregister();
      const clients = await self.clients.matchAll({ type: 'window' });
      for (const client of clients) {
        client.navigate(client.url);
      }
    })(),
  );
});
