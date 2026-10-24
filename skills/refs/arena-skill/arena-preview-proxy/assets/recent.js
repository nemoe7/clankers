'use strict';

// The chooser keeps the last preview roots opened from it in this browser's storage, so the server keeps no memory.
// Every proxy page can write this storage. Keep valid preview roots only. Render the list as text, not HTML.
const KEY = 'arena-preview-recent';
const NAME_KEY = 'arena-preview-recent-names';
const RESET_KEY = 'arena-preview-recent-reset';
const LIMIT = 10;
const MAX_LABEL = 48;
const BOUNDARY_HOURS = [2, 8, 14, 20];
const ROOT = /^https:\/\/sbx-[a-z0-9-]+\.arena\.site$/i;

function isUnavailableLabel(value) {
  return /\b(?:preview\s+)?unavailable\b/i.test(String(value ?? '').trim());
}

function previewRoot(raw) {
  let url;
  try {
    url = new URL(String(raw));
  } catch {
    return null;
  }
  return ROOT.test(url.origin) && url.href === `${url.origin}/` ? url.origin : null;
}

function remember(list, root) {
  return [root, ...list.filter(item => item !== root)].slice(0, LIMIT);
}

function forget(list, root) {
  return list.filter(item => item !== root);
}

function clean(value) {
  const roots = Array.isArray(value) ? value.map(previewRoot).filter(Boolean) : [];
  return [...new Set(roots)].slice(0, LIMIT);
}

// A share lands on the chooser with its root in `shared`, so the save happens here before the
// preview opens. A plain link carries `url` and adds no entry. `previewRoot` refuses the rest.
function fromShare(search) {
  let params;
  try {
    params = new URLSearchParams(String(search || ''));
  } catch {
    return null;
  }
  const raw = params.get('shared') || '';
  const direct = previewRoot(raw);
  if (direct) return direct;
  const match = String(raw).match(/^https:\/\/sbx-[a-z0-9-]+\.arena\.site(?=[/?#]|$)/i);
  return match ? previewRoot(`${match[0]}/`) : null;
}

function inputRoot(raw) {
  const direct = previewRoot(raw);
  if (direct) return direct;
  const match = String(raw ?? '').trim().match(/^https:\/\/sbx-[a-z0-9-]+\.arena\.site(?=[/?#]|$)/i);
  return match ? previewRoot(`${match[0]}/`) : null;
}

function postRecentRoot(root, extra = {}) {
  if (!root || typeof fetch !== 'function') return;
  try {
    fetch('/pwa/recent', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: `${root}/`, manual: true, ...extra }),
      keepalive: true
    }).catch(() => {});
  } catch {
    // Ignore network errors on background registration.
  }
}

function viewerHref(root) {
  return `/?url=${encodeURIComponent(`${root}/`)}`;
}

// A label trims its edges, drops control characters and caps its length, so one entry cannot
// flood the list or hide its own remove button.
function named(value) {
  const text = String(value).replace(/[\u0000-\u001f\u007f]/g, '').trim().slice(0, MAX_LABEL);
  return isUnavailableLabel(text) ? '' : text;
}

function applyName(names, root, raw) {
  if (!previewRoot(root)) return names;
  const next = { ...names };
  const label = named(raw);
  if (label) next[root] = label;
  else delete next[root];
  return next;
}

// Stored labels for roots the list still holds, nothing else: a root that leaves the list
// drops its label with it, and junk types never reach the page.
function cleanNames(list, value) {
  const names = {};
  if (!value || typeof value !== 'object' || Array.isArray(value)) return names;
  for (const root of list) {
    const label = named(value[root] ?? '');
    if (label) names[root] = label;
  }
  return names;
}

function displayName(names, root) {
  const label = names && typeof names[root] === 'string' ? names[root] : '';
  return label || new URL(root).host;
}

function mergeRemote(list, names, entries, removed) {
  let nextList = Array.isArray(list) ? clean(list) : [];
  if (names && typeof names === 'object' && !Array.isArray(names)) {
    nextList = nextList.filter(root => !isUnavailableLabel(names[root]));
  }
  let nextNames = cleanNames(nextList, names);
  if (Array.isArray(removed)) {
    for (const item of removed) {
      const root = previewRoot(item) || previewRoot(`${String(item ?? '').replace(/\/+$/, '')}/`);
      if (root) nextList = forget(nextList, root);
    }
    nextNames = cleanNames(nextList, nextNames);
  }
  if (!Array.isArray(entries)) return { list: nextList, names: nextNames };
  const manualEntries = [];
  const scriptEntries = [];
  for (const item of entries) {
    const raw = item && typeof item.url === 'string' ? item.url : '';
    const root = previewRoot(raw) || previewRoot(`${raw.replace(/\/+$/, '')}/`);
    if (!root) continue;
    if (item && isUnavailableLabel(item.name)) {
      nextList = forget(nextList, root);
      continue;
    }
    if (item && item.manual === true) {
      manualEntries.push({ root, name: item.name });
    } else {
      scriptEntries.push({ root, name: item ? item.name : '' });
    }
  }
  for (let idx = manualEntries.length - 1; idx >= 0; idx -= 1) {
    const { root, name } = manualEntries[idx];
    const cleanLabel = typeof name === 'string' ? named(name) : '';
    if (cleanLabel) {
      nextList = nextList.filter(item => item === root || nextNames[item] !== cleanLabel);
    }
    nextList = remember(nextList, root);
    if (cleanLabel && !nextNames[root]) {
      nextNames = applyName(nextNames, root, cleanLabel);
    }
  }
  for (const { root, name } of scriptEntries) {
    const cleanLabel = typeof name === 'string' ? named(name) : '';
    if (cleanLabel) {
      nextList = nextList.filter(item => item === root || nextNames[item] !== cleanLabel);
    }
    if (!nextList.includes(root) && nextList.length < LIMIT) {
      nextList.push(root);
    }
    if (nextList.includes(root) && cleanLabel && !nextNames[root]) {
      nextNames = applyName(nextNames, root, cleanLabel);
    }
  }
  return { list: nextList.slice(0, LIMIT), names: cleanNames(nextList, nextNames) };
}

// The list resets at 02:00, 08:00, 14:00 or 20:00 PHT, and PHT holds UTC+8 all year, so the
// boundary math runs on fixed offsets. Before 02:00 the previous one lands at 20:00 the day before.
function previousBoundary(when) {
  const SHIFT = 8 * 3600000;
  const DAY = 86400000;
  const HOUR = 3600000;
  const shifted = when.getTime() + SHIFT;
  const dayStart = Math.floor(shifted / DAY) * DAY;
  const hourOfDay = Math.floor((shifted - dayStart) / HOUR);
  let boundary = null;
  for (const hour of BOUNDARY_HOURS) {
    if (hour <= hourOfDay) boundary = dayStart + hour * HOUR;
  }
  if (boundary === null) boundary = dayStart - 4 * HOUR;
  return new Date(boundary - SHIFT);
}

// A stamp behind the boundary clears the list, even when the app missed one or several
// boundaries while closed. No stamp is a first open, and it keeps whatever the list holds.
function needsReset(stamped, boundary) {
  return stamped !== null && typeof stamped === 'number' && stamped < boundary;
}

function load() {
  try {
    return clean(JSON.parse(localStorage.getItem(KEY) || '[]'));
  } catch {
    return [];
  }
}

function save(list) {
  try {
    localStorage.setItem(KEY, JSON.stringify(list));
    writeNames(cleanNames(list, readNames()));
  } catch {
    // Storage is off or full: the preview still opens, and the list keeps its old entries.
  }
}

function show(box, list, names) {
  box.replaceChildren(...list.map(root => {
    const host = new URL(root).host;
    const link = document.createElement('a');
    link.href = viewerHref(root);
    link.textContent = displayName(names, root);
    const rename = document.createElement('button');
    rename.type = 'button';
    rename.value = root;
    rename.dataset.rename = 'true';
    rename.textContent = '✎';
    rename.title = `Rename ${host}`;
    rename.setAttribute('aria-label', `Rename ${host}`);
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.value = root;
    remove.textContent = '×';
    remove.title = `Remove ${host}`;
    remove.setAttribute('aria-label', `Remove ${host}`);
    const item = document.createElement('li');
    item.append(link, rename, remove);
    return item;
  }));
  box.hidden = list.length === 0;
}

function resetRecent() {
  const boundary = previousBoundary(new Date()).getTime();
  const stamped = readReset();
  if (needsReset(stamped, boundary)) {
    save([]);
    writeNames({});
  }
  if (stamped === null || stamped < boundary) writeReset(boundary);
}

function start() {
  resetRecent();
  const shared = fromShare(location.search);
  if (shared) {
    // Save before the jump: the preview page runs no part of this list.
    save(remember(load(), shared));
    postRecentRoot(shared);
    location.replace(viewerHref(shared));
    return;
  }
  const box = document.getElementById('recent');
  const form = document.querySelector('form');
  if (!box || !form) return;
  const freshNames = () => cleanNames(load(), readNames());
  let names = freshNames();
  const render = () => show(box, load(), names);
  const syncRemote = () => {
    if (typeof fetch !== 'function') return;
    fetch('/pwa/recent', { cache: 'no-store' })
      .then(res => (res && res.ok ? res.json() : null))
      .then(body => {
        if (!body || typeof body !== 'object') return;
        const merged = mergeRemote(load(), readNames(), body.entries, body.removed);
        save(merged.list);
        writeNames(merged.names);
        names = freshNames();
        render();
      })
      .catch(() => {});
  };
  const refreshAtBoundary = () => {
    resetRecent();
    names = freshNames();
    render();
    syncRemote();
    const when = new Date();
    const next = previousBoundary(when).getTime() + 6 * 3600000;
    setTimeout(refreshAtBoundary, next - when.getTime());
  };
  refreshAtBoundary();
  form.addEventListener('submit', () => {
    const root = inputRoot(form.elements.url.value);
    if (root) {
      form.elements.url.value = `${root}/`;
      save(remember(load(), root));
      postRecentRoot(root);
    }
  });
  box.addEventListener('click', event => {
    const button = event.target.closest('button');
    if (button && button.dataset.rename) {
      const root = button.value;
      const item = button.closest('li');
      const link = item && item.querySelector('a');
      if (!link || !previewRoot(root)) return;
      const input = document.createElement('input');
      input.type = 'text';
      input.maxLength = MAX_LABEL;
      input.value = names[root] || '';
      input.placeholder = new URL(root).host;
      input.setAttribute('aria-label', `Rename ${new URL(root).host}`);
      let cancelled = false;
      const commit = () => {
        if (cancelled) return;
        names = applyName(names, root, input.value);
        writeNames(names);
        postRecentRoot(root, { name: names[root] || '' });
        render();
      };
      input.addEventListener('keydown', press => {
        if (press.key === 'Enter') {
          press.preventDefault();
          commit();
        } else if (press.key === 'Escape') {
          cancelled = true;
          render();
        }
      });
      input.addEventListener('blur', commit);
      item.replaceChild(input, link);
      input.focus();
      return;
    }
    if (button) {
      const list = forget(load(), button.value);
      save(list);
      postRecentRoot(button.value, { remove: true });
      names = freshNames();
      render();
      return;
    }
    const link = event.target.closest('a');
    const root = link && previewRoot(new URL(link.href).searchParams.get('url'));
    if (root) {
      save(remember(load(), root));
      postRecentRoot(root);
    }
  });
}

// Labels live in their own key, so the root list keeps the shape every stored copy already has.
function readNames() {
  try {
    return JSON.parse(localStorage.getItem(NAME_KEY) || '{}');
  } catch {
    return {};
  }
}

function writeNames(names) {
  try {
    localStorage.setItem(NAME_KEY, JSON.stringify(names));
  } catch {
    // Storage is off or full: the list keeps its labels, and the preview still opens.
  }
}

function readReset() {
  try {
    const raw = localStorage.getItem(RESET_KEY);
    const value = Number(raw);
    return raw === null || !Number.isFinite(value) ? null : value;
  } catch {
    return null;
  }
}

function writeReset(boundary) {
  try {
    localStorage.setItem(RESET_KEY, String(boundary));
  } catch {
    // Storage is off or full: the next open runs the boundary check again.
  }
}

// The checks load the pure helpers in Node. The chooser page runs the list.
if (typeof module === 'object' && module.exports) {
  module.exports = {
    previewRoot, remember, forget, clean, fromShare, viewerHref,
    named, applyName, cleanNames, displayName, mergeRemote,
    previousBoundary, needsReset, LIMIT
  };
} else {
  start();
}
