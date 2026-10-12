'use strict';

// The proxy injects this file so Android Chrome can offer an installed-app frame.
// The worker must control the viewer root. Remove the narrow registration before the root registration.
if ('serviceWorker' in navigator) {
  const WORKER = '/pwa/service-worker.js';
  const ROOT = new URL('/', location.href).href;
  navigator.serviceWorker.getRegistration(WORKER).then(existing => {
    if (existing && existing.scope !== ROOT) return existing.unregister();
  }).catch(() => {}).then(() =>
    navigator.serviceWorker.register(WORKER, { scope: '/' })).catch(() => {});
}
