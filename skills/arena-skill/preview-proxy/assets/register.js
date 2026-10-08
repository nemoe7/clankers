'use strict';

// The proxy injects this file into the preview page, so Android Chrome can offer
// the installed-app frame. An installable frame is optional: the preview works
// without it.
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/pwa/service-worker.js').catch(() => {});
}

// A click on an Arena preview link re-enters the proxy in this window, instead of
// leaving the installed app for a raw sandbox host.
const PREVIEW_HOST = /^sbx-[a-z0-9-]+\.arena\.site$/i;
document.addEventListener('click', event => {
  if (event.defaultPrevented || event.button !== 0 ||
      event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
    return;
  }
  const anchor = event.target && event.target.closest ? event.target.closest('a[href]') : null;
  if (!anchor || anchor.hasAttribute('download')) return;
  let url;
  try {
    url = new URL(anchor.href);
  } catch {
    return;
  }
  if (url.protocol !== 'https:' || !PREVIEW_HOST.test(url.hostname)) return;
  event.preventDefault();
  location.assign(`/?url=${encodeURIComponent(`${url.origin}/`)}`);
});
