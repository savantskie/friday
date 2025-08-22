self.addEventListener('install', (event) => {
  self.skipWaiting();
});
self.addEventListener('activate', (event) => {
  clients.claim();
});

// Show notifications sent via Web Push later
self.addEventListener('push', (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch {}
  const title = data.title || 'Friday';
  const body  = data.body  || 'Ping';
  const url   = data.url   || '/';
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      data: { url }
    })
  );
});

// Focus or open a tab when the user clicks a notification
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil((async () => {
    const allClients = await clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const c of allClients) {
      if ('focus' in c) return c.focus();
    }
    return clients.openWindow(url);
  })());
});
