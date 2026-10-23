'use strict';
// Adapted from markdown-it-mark (MIT). See markdown-it.LICENSE.
function highlightMarkdown(md) {
  function tokenize(state, silent) {
    if (silent || state.src[state.pos] !== '=') return false;
    const scanned = state.scanDelims(state.pos, true);
    let length = scanned.length;
    if (length < 2) return false;
    if (length % 2) {
      state.push('text', '', 0).content = '=';
      length--;
    }
    for (let i = 0; i < length; i += 2) {
      state.push('text', '', 0).content = '==';
      if (scanned.can_open || scanned.can_close) state.delimiters.push({
        marker: 0x3D, length: 0, jump: i / 2, token: state.tokens.length - 1,
        end: -1, open: scanned.can_open, close: scanned.can_close,
      });
    }
    state.pos += scanned.length;
    return true;
  }
  function postProcess(state, delimiters) {
    const lone = [];
    for (const start of delimiters) {
      if (start.marker !== 0x3D || start.end === -1) continue;
      const end = delimiters[start.end];
      for (const [index, nesting] of [[start.token, 1], [end.token, -1]]) {
        const token = state.tokens[index];
        token.type = nesting === 1 ? 'mark_open' : 'mark_close';
        token.tag = 'mark';
        token.nesting = nesting;
        token.markup = '==';
        token.content = '';
      }
      const previous = state.tokens[end.token - 1];
      if (previous.type === 'text' && previous.content === '=') lone.push(end.token - 1);
    }
    while (lone.length) {
      const index = lone.pop();
      let end = index + 1;
      while (end < state.tokens.length && state.tokens[end].type === 'mark_close') end++;
      end--;
      if (index !== end) [state.tokens[index], state.tokens[end]] = [state.tokens[end], state.tokens[index]];
    }
  }
  md.inline.ruler.before('emphasis', 'mark', tokenize);
  md.inline.ruler2.before('emphasis', 'mark', state => {
    postProcess(state, state.delimiters);
    for (const meta of state.tokens_meta || []) {
      if (meta && meta.delimiters) postProcess(state, meta.delimiters);
    }
  });
}
const messageMarkdown = markdownit('commonmark', { html: false, breaks: true }).enable(['table', 'strikethrough']).use(highlightMarkdown);
messageMarkdown.renderer.rules.link_open = (tokens, index, options, env, renderer) => {
  const token = tokens[index];
  const href = token.attrGet('href') || '';
  if (href && !href.startsWith('#')) {
    token.attrSet('target', '_blank');
    token.attrSet('rel', 'noopener noreferrer');
  }
  return renderer.renderToken(tokens, index, options, env);
};
const renderMessageImage = messageMarkdown.renderer.rules.image;
messageMarkdown.renderer.rules.image = (tokens, index, options, env, renderer) => {
  const pending = (tokens[index].children || []).slice();
  while (pending.length) {
    const token = pending.pop();
    if (token.type === 'text_special') token.type = 'text';
    for (const child of token.children || []) pending.push(child);
  }
  return renderMessageImage(tokens, index, options, env, renderer);
};
const ESCAPED_INLINE_CODE = /(?<![\\`])`((?!\\`|`)(?:(?<!\\)\\`|[^`\n])*?(?<!\\)\\`(?:(?<!\\)\\`|[^`\n])*|(?<!\\)\\`(?:(?:(?<!\\)\\`|[^`\n])*?(?<!\\)\\`)?)`(?![`])/g;
function unescapeMessageMarkdown(source) {
  const restored = source.replace(/^([ \t]*)\\(`{3,}|~{3,})/gm, '$1$2');
  let fence = null;
  return restored.split(/(\r?\n)/).map(part => {
    if (part === '\n' || part === '\r\n') return part;
    if (fence !== null) {
      if (part.trimStart().startsWith(fence)) fence = null;
      return part;
    }
    const opening = /^ {0,3}(`{3,}|~{3,})/.exec(part);
    if (opening) {
      fence = opening[1];
      return part;
    }
    return part.replace(ESCAPED_INLINE_CODE, (_, body) => {
      const content = body.replace(/(?<!\\)\\`/g, '`');
      const runs = content.match(/`+/g) || [];
      const longest = runs.reduce((max, run) => Math.max(max, run.length), 0);
      const ticks = '`'.repeat(longest + 1);
      if (content.startsWith('`') || content.endsWith('`') || (content.startsWith(' ') && content.endsWith(' '))) {
        return `${ticks} ${content} ${ticks}`;
      }
      return `${ticks}${content}${ticks}`;
    });
  }).join('');
}
function renderMessageMarkdown(source) {
  const attribute = value => messageMarkdown.utils.escapeHtml(value).replaceAll("'", '&#x27;');
  const images = [];
  const imagePrefix = 'previewimage' + crypto.randomUUID().replaceAll('-', '');
  const tagged = source.replace(/!\[([^\]\n]*)\]\((\S+?)\s+=(\p{Nd}+)x(\p{Nd}*)\)/gu, (match, alt, url, width, height) => {
    if (!messageMarkdown.validateLink(url)) return match;
    images.push(`<img src="${attribute(url)}" alt="${attribute(alt)}" width="${width}"${height ? ` height="${height}"` : ''} />`);
    return ` ${imagePrefix}${images.length - 1}x `;
  });
  let rendered = messageMarkdown.render(unescapeMessageMarkdown(tagged));
  rendered = rendered.replace(/<p>[\s\S]*?<\/p>/g, paragraph => paragraph.replace(/<br\s*\/?>/g, ''));
  rendered = rendered.replace(new RegExp(`${imagePrefix}(\\d+)x`, 'g'), (_, index) => images[Number(index)]);
  return rendered.replace(/<pre>([\s\S]*?)<\/pre>/g, (_, inner) => {
    const template = document.createElement('template');
    template.innerHTML = inner;
    const code = template.content.textContent;
    const payload = attribute(code).replaceAll('\n', '&#10;');
    const button = `<button type="button" class="copy-code" aria-label="Copy code" title="Copy code" data-code="${payload}">${icon('copy', 14).outerHTML}</button>`;
    return `<div class="code-block">${button}<pre>${inner}</pre></div>`;
  });
}
