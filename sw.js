const CACHE = 'presidentielle-2027-v129';
const IMG = 'nous-votons-images';
const FILES = ['./', 'index.html', 'manifest.json', 'icon-180.png', 'icon-192.png', 'icon-512.png', 'icon-maskable-512.png', 'logo-header.svg', 'logo-appli.svg', 'favicon-32.png'];
self.addEventListener('install', (e) => { e.waitUntil(caches.open(CACHE).then((c) => c.addAll(FILES.map((f) => new Request(f, { cache: 'reload' }))))); self.skipWaiting(); });
self.addEventListener('activate', (e) => { e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE && k !== IMG).map((k) => caches.delete(k))))); self.clients.claim(); });
self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;
  const u = new URL(e.request.url);
  if (u.origin !== location.origin) return;
  // Photos et logos : affichés tout de suite depuis le téléphone, rafraîchis en arrière-plan
  if (/\/data\/(portraits|partis)\/.+\.(jpe?g|png|svg|webp)$/i.test(u.pathname)) {
    e.respondWith(caches.open(IMG).then((c) => c.match(e.request).then((hit) => {
      const net = fetch(e.request).then((r) => { if (r.ok) c.put(e.request, r.clone()); return r; }).catch(() => hit);
      if (hit) { e.waitUntil(net); return hit; }
      return net;
    })));
    return;
  }
  e.respondWith(fetch(e.request.url, { cache: 'no-cache' }).then((r) => { const cp = r.clone(); caches.open(CACHE).then((c) => c.put(e.request, cp)); return r; }).catch(() => caches.match(e.request, { ignoreSearch: true })));
});
// Alertes : affichage d'une notification reçue, et ouverture de l'appli au toucher
self.addEventListener('push', (e) => {
  let d = {}; try { d = e.data ? e.data.json() : {}; } catch (er) { d = { title: 'Nous votons', body: e.data ? e.data.text() : '' }; }
  e.waitUntil(self.registration.showNotification(d.title || 'Nous votons', { body: d.body || '', tag: d.tag || 'nv', icon: 'icon-192.png', badge: 'icon-192.png', data: { url: d.url || './' } }));
});
self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const url = new URL((e.notification.data && e.notification.data.url) || './', self.registration.scope).href;
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((cs) => {
    const c = cs.find((x) => x.url.startsWith(self.registration.scope));
    if (c) { c.focus(); return c.navigate ? c.navigate(url) : null; }
    return self.clients.openWindow(url);
  }));
});
