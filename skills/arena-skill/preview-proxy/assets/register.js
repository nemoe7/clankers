'use strict';

// The proxy injects this file into the preview page, so Android Chrome can offer
// the installed-app frame. An installable frame is optional: the preview works
// without it. The app takes no click on an outside link; the share target is the
// only path in.
// The worker must control the viewer root, because that root is the manifest's
// start URL: a worker under /pwa/ leaves the start URL outside its scope, and
// Chrome then refuses the install. A registration left on
// the narrow scope is dropped first, so the wider one can take its place.
if ('serviceWorker' in navigator) {
  const WORKER = '/pwa/service-worker.js';
  const ROOT = new URL('/', location.href).href;
  navigator.serviceWorker.getRegistration(WORKER).then(existing => {
    if (existing && existing.scope !== ROOT) return existing.unregister();
  }).catch(() => {}).then(() =>
    navigator.serviceWorker.register(WORKER, { scope: '/' })).catch(() => {});
}
