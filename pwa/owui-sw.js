self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', () => clients.claim());

self.addEventListener('push', (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch {}
  const title = data.title || 'Friday';
  const body  = data.body  || 'New message';
  const url   = data.url   || '/';
  event.waitUntil(self.registration.showNotification(title, { body, data: { url } }));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil((async () => {
    const wins = await clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const w of wins) { if ('focus' in w) return w.focus(); }
    return clients.openWindow(url);
  })());
});
