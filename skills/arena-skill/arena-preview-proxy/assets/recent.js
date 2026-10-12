'use strict';

// The chooser keeps the last preview roots opened from it in this browser's storage, so the server keeps no memory.
// Every proxy page can write this storage. Keep valid preview roots only. Render the list as text, not HTML.
const KEY = 'arena-preview-recent';
const LIMIT = 10;
const ROOT = /^https:\/\/sbx-[a-z0-9-]+\.arena\.site$/i;

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
  } catch {
    // Storage is off or full: the preview still opens, and the list keeps its old entries.
  }
}

function show(box, list) {
  box.replaceChildren(...list.map(root => {
    const host = new URL(root).host;
    const link = document.createElement('a');
    link.href = `/?url=${encodeURIComponent(`${root}/`)}`;
    link.textContent = host;
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.value = root;
    remove.textContent = '×';
    remove.title = `Remove ${host}`;
    remove.setAttribute('aria-label', `Remove ${host}`);
    const item = document.createElement('li');
    item.append(link, remove);
    return item;
  }));
  box.hidden = list.length === 0;
}

function start() {
  const box = document.getElementById('recent');
  const form = document.querySelector('form');
  if (!box || !form) return;
  show(box, load());
  form.addEventListener('submit', () => {
    const root = previewRoot(form.elements.url.value);
    if (root) save(remember(load(), root));
  });
  box.addEventListener('click', event => {
    const remove = event.target.closest('button');
    if (remove) {
      const list = forget(load(), remove.value);
      save(list);
      show(box, list);
      return;
    }
    const link = event.target.closest('a');
    const root = link && previewRoot(new URL(link.href).searchParams.get('url'));
    if (root) save(remember(load(), root));
  });
}

// The checks load the pure helpers in Node. The chooser page runs the list.
if (typeof module === 'object' && module.exports) {
  module.exports = { previewRoot, remember, forget, clean, LIMIT };
} else {
  start();
}
