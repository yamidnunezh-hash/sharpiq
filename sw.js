// SharpIQ Service Worker — actualización automática garantizada
// Cambia CACHE_VERSION en cada deploy importante para forzar recarga global
const CACHE_VERSION = 'sharpiq-v103';
const STATIC_ASSETS = [
  '/assets/icon-192.png',
  '/assets/icon-512.png',
];

// Archivos que SIEMPRE se piden frescos de la red
const NETWORK_FIRST = ['/', '/index.html', '/datos.js', '/sw.js'];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_VERSION).then(c => c.addAll(STATIC_ASSETS))
  );
  // Activa inmediatamente sin esperar a que cierren las pestañas viejas
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_VERSION).map(k => {
        console.log('[SW] Eliminando caché viejo:', k);
        return caches.delete(k);
      }))
    )
  );
  // Toma control de todos los clientes abiertos de inmediato
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  const path = url.pathname;

  // Ignorar peticiones que no son GET
  if (e.request.method !== 'GET') return;

  // Ignorar peticiones externas (APIs, CDNs)
  if (url.origin !== self.location.origin) return;

  // datos.js NUNCA se cachea — siempre fresco del servidor
  if (path.includes('datos.js')) {
    e.respondWith(
      fetch(e.request, {cache: 'no-store'})
        .catch(() => new Response('const PROXIMOS_EVENTOS=[];const PREDICCIONES_HISTORIAL=[];', {headers:{'Content-Type':'application/javascript'}}))
    );
    return;
  }

  const esNetworkFirst = NETWORK_FIRST.some(p => path === p || path.endsWith(p))
    || path.endsWith('.html')
    || path.endsWith('.js')
    || path.endsWith('.css');

  if (esNetworkFirst) {
    // Network first: siempre intenta la red, caché solo como fallback offline
    e.respondWith(
      fetch(e.request)
        .then(response => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_VERSION).then(c => c.put(e.request, clone));
          }
          return response;
        })
        .catch(() => caches.match(e.request))
    );
  } else {
    // Cache first: imágenes y recursos estáticos que no cambian
    e.respondWith(
      caches.match(e.request).then(cached => {
        if (cached) return cached;
        return fetch(e.request).then(response => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_VERSION).then(c => c.put(e.request, clone));
          }
          return response;
        });
      })
    );
  }
});

// ── PUSH NOTIFICATIONS ───────────────────────────────────────────
self.addEventListener('push', e => {
  let data = { title: '⚽ SharpIQ', body: 'Nueva predicción disponible', url: '/' };
  try { data = e.data.json(); } catch(err) {}
  e.waitUntil(
    self.registration.showNotification(data.title, {
      body:    data.body,
      icon:    '/assets/icon-192.png',
      badge:   '/assets/icon-192.png',
      vibrate: [200, 100, 200],
      data:    { url: data.url || '/' },
      actions: [{ action: 'ver', title: 'Ver predicción' }]
    })
  );
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || '/';
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(cs => {
      const c = cs.find(c => c.url.includes(self.location.origin));
      if (c) { c.focus(); c.navigate(url); }
      else clients.openWindow(url);
    })
  );
});
