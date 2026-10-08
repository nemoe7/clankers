'use strict';

const fs = require('node:fs');
const http = require('node:http');
const https = require('node:https');
const path = require('node:path');
const crypto = require('node:crypto');
const zlib = require('node:zlib');

const PORT = Number(process.env.PORT || 8080);
const COOKIE_NAME = 'arena_preview_target';
const COOKIE_MAX_AGE = 12 * 60 * 60;
const COOKIE_SECRET = process.env.PROXY_COOKIE_SECRET || '';
const HOP_BY_HOP_HEADERS = [
  'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
  'te', 'trailer', 'transfer-encoding', 'upgrade', 'proxy-connection'
];
// Browser navigation metadata triggers Arena's mobile preview gate, so the proxy
// drops it before the upstream request.
const FETCH_METADATA_HEADERS = [
  'sec-fetch-dest', 'sec-fetch-mode', 'sec-fetch-site', 'sec-fetch-user', 'referer'
];
const ALLOWED_METHODS = new Set(['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']);
const PREVIEW_HOST = /^sbx-[a-z0-9-]+\.arena\.site$/i;
const ASSET_TYPES = {
  'register.js': 'text/javascript; charset=utf-8',
  'service-worker.js': 'text/javascript; charset=utf-8',
  'icon.svg': 'image/svg+xml',
  'icon-192.png': 'image/png',
  'icon-512.png': 'image/png'
};
const ASSETS = path.join(__dirname, 'assets');
// The head rewrite buffers one small page; a larger body streams untouched.
const HEAD_CAP = 1_000_000;

function isAllowedPreview(url) {
  return url.protocol === 'https:' &&
    !url.username && !url.password && !url.port &&
    PREVIEW_HOST.test(url.hostname) &&
    url.pathname === '/' && !url.search && !url.hash;
}

function parseSelectedUrl(raw) {
  let url;
  try {
    url = new URL(raw);
  } catch {
    throw new Error('The url parameter must be a valid, URL-encoded HTTPS preview URL.');
  }
  if (!isAllowedPreview(url)) {
    throw new Error('Only HTTPS preview roots on sbx-*.arena.site are accepted.');
  }
  return url;
}

function signOrigin(origin) {
  const payload = Buffer.from(origin, 'utf8').toString('base64url');
  const signature = crypto.createHmac('sha256', COOKIE_SECRET).update(payload).digest('base64url');
  return `${payload}.${signature}`;
}

function verifyOriginToken(token) {
  if (!token || typeof token !== 'string') return null;
  const dot = token.lastIndexOf('.');
  if (dot <= 0 || dot === token.length - 1) return null;
  const payload = token.slice(0, dot);
  const given = Buffer.from(token.slice(dot + 1));
  const expected = Buffer.from(
    crypto.createHmac('sha256', COOKIE_SECRET).update(payload).digest('base64url')
  );
  if (given.length !== expected.length || !crypto.timingSafeEqual(given, expected)) return null;
  try {
    const url = new URL(`${Buffer.from(payload, 'base64url').toString('utf8')}/`);
    return isAllowedPreview(url) ? url.origin : null;
  } catch {
    return null;
  }
}

function readCookie(header, name) {
  if (!header) return null;
  for (const part of header.split(';')) {
    const item = part.trim();
    const eq = item.indexOf('=');
    if (eq > 0 && item.slice(0, eq) === name) return item.slice(eq + 1);
  }
  return null;
}

function withoutProxyCookie(header) {
  if (!header) return '';
  return header.split(';')
    .map(item => item.trim())
    .filter(Boolean)
    .filter(item => {
      const eq = item.indexOf('=');
      return item.slice(0, eq < 0 ? item.length : eq) !== COOKIE_NAME;
    })
    .join('; ');
}

function makeTarget(origin, pathname, search) {
  const target = new URL(`${origin}/`);
  target.pathname = pathname || '/';
  target.search = search || '';
  return target;
}

function sendText(res, status, text) {
  res.writeHead(status, {
    'content-type': 'text/plain; charset=utf-8',
    'cache-control': 'no-store',
    'x-content-type-options': 'nosniff'
  });
  res.end(text);
}

function sendHtml(res, status, body) {
  res.writeHead(status, {
    'content-type': 'text/html; charset=utf-8',
    'cache-control': 'no-store',
    'x-content-type-options': 'nosniff'
  });
  res.end(body);
}

function rewriteArenaCookie(cookie) {
  // The browser is on the tailnet host, so make Arena's cookie host-only there;
  // the proxy forwards it upstream on later requests.
  return cookie.replace(/;\s*domain=\.?arena\.site(?=;|$)/i, '');
}

function pwaHead() {
  // The manifest link rides the served head, so installability never waits on script.
  return '<link rel="manifest" href="/pwa/manifest.webmanifest">' +
    '<script src="/pwa/register.js" defer></script>';
}

function injectPwa(html) {
  // The tags go before </head>, and a page without one still takes them: after its <body> or
  // <html> opener, or after its doctype. A served page always carries the manifest link.
  const close = /<\/head\s*>/i.exec(html);
  if (close) return html.slice(0, close.index) + pwaHead() + html.slice(close.index);
  const open = /<body[^>]*>/i.exec(html) || /<html[^>]*>/i.exec(html);
  if (open) {
    const at = open.index + open[0].length;
    return html.slice(0, at) + pwaHead() + html.slice(at);
  }
  const type = /^\s*<!doctype[^>]*>/i.exec(html);
  const at = type ? type[0].length : 0;
  return html.slice(0, at) + pwaHead() + html.slice(at);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[character]);
}

function viewerPage(message) {
  // The viewer root is the main page of the installed app: it carries the manifest link and a
  // URL box, so the page installs and opens a preview without a hand-made query string. The
  // root once answered a bare text line, so the page had no head and no manifest landed
  // (owner notes 59ec9e1 and fd9315b).
  const reason = message ? `<p class="reason">${escapeHtml(message)}</p>` : '';
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Arena preview</title>
${pwaHead()}
<style>
body { margin: 0; padding: 2rem 1rem; font: 16px/1.5 system-ui, sans-serif;
  background: #1f2430; color: #e8ecf4; }
main { max-width: 34rem; margin: 0 auto; }
h1 { font-size: 1.4rem; margin: 0 0 1rem; }
.reason { padding: .6rem .8rem; border-radius: .4rem; background: #3a2b34; color: #ffd9e0; }
form { display: flex; gap: .5rem; margin: 1rem 0; }
input { flex: 1; padding: .6rem .7rem; border-radius: .4rem; border: 1px solid #48506a;
  background: #141922; color: inherit; font: inherit; min-width: 0; }
button { padding: .6rem 1rem; border-radius: .4rem; border: 0; background: #4f7cff;
  color: #fff; font: inherit; }
.hint { color: #a8b0c4; font-size: .9rem; }
</style>
</head>
<body>
<main>
<h1>Arena preview</h1>
${reason}
<form method="get" action="/">
<label for="url" hidden>Preview URL</label>
<input id="url" name="url" type="url" inputmode="url" required autocomplete="off"
  placeholder="https://sbx-xxxx.arena.site/">
<button type="submit">Open</button>
</form>
<p class="hint">Only HTTPS preview roots on <code>sbx-*.arena.site</code>. Install this page
as an app from the browser menu to reopen the preview in one tap.</p>
</main>
</body>
</html>
`;
}

function decodeBody(buffer, encoding) {
  // The proxy forwards the browser's Accept-Encoding, so an upstream page often arrives
  // compressed. The rewrite reads plain HTML, so decode it here; a body that will not decode
  // returns null and passes through untouched.
  const name = String(encoding || '').trim().toLowerCase();
  if (!name || name === 'identity') return buffer;
  try {
    if (name === 'gzip' || name === 'x-gzip') return zlib.gunzipSync(buffer);
    if (name === 'deflate') return zlib.inflateSync(buffer);
    if (name === 'br') return zlib.brotliDecompressSync(buffer);
  } catch {
    return null;
  }
  return null;
}

function manifestJson(origin) {
  return JSON.stringify({
    name: 'Arena preview',
    short_name: 'Preview',
    // The start URL carries the preview origin, so it changes with the signed cookie. A fixed id
    // keeps one installed app across those changes.
    id: '/',
    start_url: origin ? `/?url=${encodeURIComponent(`${origin}/`)}` : '/',
    scope: '/',
    display: 'standalone',
    background_color: '#1f2430',
    theme_color: '#1f2430',
    // A launch reuses the open window, so the preview stays in-page.
    launch_handler: { client_mode: 'navigate-existing' },
    // The installed app takes a shared link; Android has no per-link "open with"
    // entry for a web app, so the share sheet is the system path in.
    share_target: {
      action: '/pwa/share',
      method: 'GET',
      params: { title: 'title', text: 'text', url: 'url' }
    },
    // Chrome offers the install from an icon that resolves at 192px and 512px, so the two
    // raster icons ship beside the scalable one (owner note 31023b2).
    icons: [
      { src: '/pwa/icon-192.png', sizes: '192x192', type: 'image/png' },
      { src: '/pwa/icon-512.png', sizes: '512x512', type: 'image/png' },
      { src: '/pwa/icon.svg', sizes: 'any', type: 'image/svg+xml' }
    ]
  });
}

function sharePreview(incoming, res) {
  const shared = incoming.searchParams.get('url') ||
    (incoming.searchParams.get('text') || '').match(/https:\/\/sbx-[a-z0-9-]+\.arena\.site\/?/i)?.[0] ||
    '';
  let selected;
  try {
    selected = parseSelectedUrl(shared);
  } catch {
    return sendText(res, 400, 'Share an Arena preview link: https://sbx-*.arena.site/');
  }
  res.writeHead(302, {
    location: `/?url=${encodeURIComponent(`${selected.origin}/`)}`,
    'cache-control': 'no-store'
  });
  return res.end();
}

function servePwa(incoming, req, res) {
  if (incoming.pathname === '/pwa/share') return sharePreview(incoming, res);
  if (incoming.pathname === '/pwa/manifest.webmanifest') {
    const origin = verifyOriginToken(readCookie(req.headers.cookie, COOKIE_NAME));
    res.writeHead(200, {
      'content-type': 'application/manifest+json; charset=utf-8',
      'cache-control': 'no-store',
      'x-content-type-options': 'nosniff'
    });
    return res.end(manifestJson(origin));
  }
  const name = incoming.pathname.slice('/pwa/'.length);
  if (!Object.hasOwn(ASSET_TYPES, name) || name.includes('/')) {
    return sendText(res, 404, 'Unknown installed-app file.');
  }
  let body;
  try {
    body = fs.readFileSync(path.join(ASSETS, name));
  } catch {
    return sendText(res, 500, 'The installed-app file is missing.');
  }
  const headers = {
    'content-type': ASSET_TYPES[name],
    'cache-control': 'no-store',
    'x-content-type-options': 'nosniff'
  };
  // The worker controls the whole proxy origin, not only the /pwa/ prefix.
  if (name === 'service-worker.js') headers['service-worker-allowed'] = '/';
  res.writeHead(200, headers);
  return res.end(body);
}

function rewriteHtml(upstreamRes, res, status, headers) {
  const chunks = [];
  let size = 0;
  let capped = false;
  const flush = () => {
    capped = true;
    res.writeHead(status, headers);
    for (const item of chunks) res.write(item);
  };
  upstreamRes.on('data', chunk => {
    if (capped) return;
    size += chunk.length;
    if (size > HEAD_CAP) {
      // Too large to rewrite: flush the head buffer and stream the rest.
      flush();
      res.write(chunk);
      upstreamRes.pipe(res);
      return;
    }
    chunks.push(chunk);
  });
  upstreamRes.on('end', () => {
    if (capped) return;
    const raw = Buffer.concat(chunks);
    const decoded = decodeBody(raw, headers['content-encoding']);
    if (decoded === null || decoded.length > HEAD_CAP * 4) {
      // Undecodable or oversized: the bytes pass through untouched, with no injection.
      res.writeHead(status, headers);
      return res.end(raw);
    }
    const body = Buffer.from(injectPwa(decoded.toString('utf8')), 'utf8');
    delete headers['content-encoding'];
    headers['content-length'] = String(body.length);
    res.writeHead(status, headers);
    res.end(body);
  });
  upstreamRes.on('error', err => {
    if (!res.headersSent) sendText(res, 502, `Upstream request failed: ${err.message}`);
    else res.destroy(err);
  });
}

const server = http.createServer((req, res) => {
  if (!ALLOWED_METHODS.has(req.method)) {
    return sendText(res, 405, 'Method not allowed.');
  }

  let incoming;
  try {
    incoming = new URL(req.url, 'http://proxy.invalid');
  } catch {
    return sendText(res, 400, 'Invalid request URL.');
  }

  if (incoming.pathname === '/healthz') return sendText(res, 200, 'ok');
  if (incoming.pathname.startsWith('/pwa/')) return servePwa(incoming, req, res);

  let target;
  let targetCookie = null;
  try {
    if (incoming.searchParams.has('url')) {
      if (incoming.pathname !== '/') {
        return sendText(res, 400, 'Pass url only on the viewer root: /?url=<encoded-preview-url>');
      }
      const selected = parseSelectedUrl(incoming.searchParams.get('url'));
      target = selected;
      targetCookie = `${COOKIE_NAME}=${signOrigin(selected.origin)}; Path=/; Max-Age=${COOKIE_MAX_AGE}; HttpOnly; Secure; SameSite=Lax`;
    } else {
      const origin = verifyOriginToken(readCookie(req.headers.cookie, COOKIE_NAME));
      if (!origin) {
        // No target yet: the main page itself answers, so it installs and carries the
        // manifest link (owner note fd9315b).
        return sendHtml(res, 200, viewerPage(
          'Choose a preview: paste its URL, or open this page from a share or a link that'
          + ' carries one.'
        ));
      }
      target = makeTarget(origin, incoming.pathname, incoming.search);
    }
  } catch (err) {
    if (incoming.pathname === '/') {
      return sendHtml(res, 400, viewerPage(err.message || 'Invalid preview URL.'));
    }
    return sendText(res, 400, err.message || 'Invalid preview URL.');
  }

  const headers = { ...req.headers };
  for (const name of HOP_BY_HOP_HEADERS) delete headers[name];
  for (const name of FETCH_METADATA_HEADERS) delete headers[name];
  const forwardedCookies = withoutProxyCookie(headers.cookie);
  if (forwardedCookies) headers.cookie = forwardedCookies;
  else delete headers.cookie;
  headers.host = target.host;

  // The target origin comes from parseSelectedUrl or the signed cookie, and isAllowedPreview
  // pins both to HTTPS roots on sbx-*.arena.site with no credentials, port or path. CodeQL
  // cannot model that pattern allowlist, so .github/codeql/codeql-config.yml excludes
  // js/request-forgery for this forwarding request.
  const upstream = https.request(target, { method: req.method, headers, timeout: 120000 },
    upstreamRes => {
      const responseHeaders = { ...upstreamRes.headers };
      for (const name of HOP_BY_HOP_HEADERS) delete responseHeaders[name];
      if (responseHeaders['set-cookie']) {
        const cookies = responseHeaders['set-cookie'].map(rewriteArenaCookie);
        responseHeaders['set-cookie'] = targetCookie ? [targetCookie, ...cookies] : cookies;
      } else if (targetCookie) {
        responseHeaders['set-cookie'] = [targetCookie];
      }
      const location = responseHeaders.location;
      if (location) {
        try {
          const redirected = new URL(location, target);
          if (redirected.origin === target.origin) {
            responseHeaders.location = `${redirected.pathname}${redirected.search}${redirected.hash}`;
          }
        } catch {
          // Leave malformed or relative Location values unchanged.
        }
      }
      responseHeaders['cache-control'] = 'no-store';
      const status = upstreamRes.statusCode || 502;
      const isHtml = /\btext\/html\b/i.test(String(responseHeaders['content-type'] || ''));
      if (isHtml && req.method !== 'HEAD') {
        delete responseHeaders['content-length'];
        return rewriteHtml(upstreamRes, res, status, responseHeaders);
      }
      res.writeHead(status, responseHeaders);
      upstreamRes.pipe(res);
    });

  upstream.setTimeout(120000, () => upstream.destroy(new Error('Upstream timeout')));
  upstream.on('error', err => {
    if (!res.headersSent) sendText(res, 502, `Upstream request failed: ${err.message}`);
    else res.destroy(err);
  });
  req.on('aborted', () => upstream.destroy());
  req.pipe(upstream);
});

server.headersTimeout = 65_000;
server.requestTimeout = 10 * 60 * 1000;

// The pure helpers are exported for the checks; the image runs this file directly, so the
// listening server stays out of a require.
module.exports = { injectPwa, decodeBody, viewerPage };

if (require.main === module) {
  // A served proxy refuses a short signing secret; a require for the checks needs none.
  if (COOKIE_SECRET.length < 32) {
    console.error('PROXY_COOKIE_SECRET must be at least 32 characters.');
    process.exit(1);
  }
  server.listen(PORT, '127.0.0.1', () => {
    console.log(`Arena preview proxy listening on 127.0.0.1:${PORT}`);
    console.log('Allowed target pattern: https://sbx-*.arena.site/');
  });
}
