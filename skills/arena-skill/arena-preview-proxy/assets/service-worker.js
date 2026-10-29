'use strict';

// A minimal worker with no caching, so the preview never serves stale bytes.
// For same-origin sub-requests whose Referer is a child asset (e.g. /app.js or /style.css)
// rather than the viewer root (/?url=...), attach the controlling window client's URL as
// referrer so the stateless proxy can still read the target preview root.
function hasViewerTargetReferer(referrer, origin) {
  try {
    const ref = new URL(referrer || '');
    return ref.origin === origin && ref.pathname === '/' && ref.searchParams.has('url');
  } catch {
    return false;
  }
}

function shouldAttachClientReferer(req, clientId, origin) {
  if (!req || req.mode === 'navigate' || !clientId) return false;
  let url;
  try {
    url = new URL(req.url);
  } catch {
    return false;
  }
  if (url.origin !== origin || url.pathname.startsWith('/pwa/')) return false;
  return !hasViewerTargetReferer(req.referrer, origin);
}

if (typeof self !== 'undefined' && typeof self.addEventListener === 'function') {
  self.addEventListener('install', () => self.skipWaiting());
  self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
  self.addEventListener('fetch', event => {
    const req = event.request;
    if (!shouldAttachClientReferer(req, event.clientId, self.location.origin)) return;
    event.respondWith((async () => {
      const client = await self.clients.get(event.clientId);
      if (client && hasViewerTargetReferer(client.url, self.location.origin)) {
        try {
          return await fetch(new Request(req, { referrer: client.url }));
        } catch {
          // Fall back to the original request if Request construction fails.
        }
      }
      return fetch(req);
    })());
  });
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { hasViewerTargetReferer, shouldAttachClientReferer };
}
