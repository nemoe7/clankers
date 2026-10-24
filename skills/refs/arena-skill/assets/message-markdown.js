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
function formatUnescapedInlineCode(body) {
  let content = '';
  for (let i = 0; i < body.length; i += 1) {
    if (body[i] === '\\' && i + 1 < body.length && body[i + 1] === '`' && (i === 0 || body[i - 1] !== '\\')) {
      content += '`';
      i += 1;
    } else {
      content += body[i];
    }
  }
  let longest = 0;
  let run = 0;
  for (let i = 0; i < content.length; i += 1) {
    if (content[i] === '`') {
      run += 1;
      if (run > longest) longest = run;
    } else {
      run = 0;
    }
  }
  const ticks = '`'.repeat(longest + 1);
  if (content.startsWith('`') || content.endsWith('`') || (content.startsWith(' ') && content.endsWith(' '))) {
    return `${ticks} ${content} ${ticks}`;
  }
  return `${ticks}${content}${ticks}`;
}
function unescapeInlineCodeLine(part) {
  let out = '';
  const n = part.length;
  let i = 0;
  while (i < n) {
    if (part[i] !== '`') {
      out += part[i];
      i += 1;
      continue;
    }
    if (i > 0 && part[i - 1] === '\\') {
      out += part[i];
      i += 1;
      continue;
    }
    if (i + 1 < n && part[i + 1] === '`') {
      while (i < n && part[i] === '`') {
        out += part[i];
        i += 1;
      }
      continue;
    }
    if (i + 1 < n && part[i + 1] === '\\' && i + 2 < n && part[i + 2] === '`') {
      if (i + 3 < n && part[i + 3] === '`' && (i + 4 === n || part[i + 4] !== '`')) {
        out += formatUnescapedInlineCode(part.slice(i + 1, i + 3));
        i += 4;
        continue;
      }
      if (i + 3 < n && part[i + 3] === '`') {
        out += part.slice(i, i + 3);
        i += 3;
        while (i < n && part[i] === '`') {
          out += part[i];
          i += 1;
        }
        continue;
      }
      let j = i + 3;
      while (j < n) {
        if (part[j] === '\\' && j + 1 < n && part[j + 1] === '`' && part[j - 1] !== '\\') {
          j += 2;
        } else if (part[j] === '`') {
          break;
        } else {
          j += 1;
        }
      }
      if (j < n && (j + 1 === n || part[j + 1] !== '`') && j - 2 >= i + 3 && part.slice(j - 2, j) === '\\`' && part[j - 3] !== '\\') {
        out += formatUnescapedInlineCode(part.slice(i + 1, j));
        i = j + 1;
      } else {
        out += part.slice(i, j);
        i = j;
      }
      continue;
    }
    let j = i + 1;
    let hasEscaped = false;
    while (j < n) {
      if (part[j] === '\\' && j + 1 < n && part[j + 1] === '`' && (j === i + 1 || part[j - 1] !== '\\')) {
        hasEscaped = true;
        j += 2;
      } else if (part[j] === '`') {
        break;
      } else {
        j += 1;
      }
    }
    if (j < n && (j + 1 === n || part[j + 1] !== '`')) {
      out += hasEscaped ? formatUnescapedInlineCode(part.slice(i + 1, j)) : part.slice(i, j + 1);
      i = j + 1;
    } else {
      out += part.slice(i, j);
      i = j;
    }
  }
  return out;
}
function stripMarkdownHtmlComments(source) {
  let out = '';
  let i = 0;
  const n = source.length;
  let fence = null;
  let atLineStart = true;
  while (i < n) {
    if (atLineStart) {
      const m = /^ {0,3}(`{3,}|~{3,})/.exec(source.slice(i));
      if (m) {
        if (fence === null) fence = m[1];
        else if (m[1][0] === fence[0] && m[1].length >= fence.length) fence = null;
      }
      atLineStart = false;
    }
    if (fence === null && source[i] === '`') {
      let ticks = 0;
      while (i + ticks < n && source[i + ticks] === '`') ticks++;
      const delim = '`'.repeat(ticks);
      const close = source.indexOf(delim, i + ticks);
      if (close !== -1) {
        const span = source.slice(i, close + ticks);
        out += span;
        atLineStart = span.endsWith('\n');
        i = close + ticks;
        continue;
      }
    }
    if (fence === null && source.startsWith('<!--', i)) {
      const end = source.indexOf('-->', i + 4);
      if (end !== -1) {
        let next = end + 3;
        if (out === '' || out.endsWith('\n')) {
          if (source.startsWith('\r\n', next)) next += 2;
          else if (source[next] === '\n') next += 1;
          atLineStart = true;
        }
        i = next;
        continue;
      }
    }
    const ch = source[i];
    out += ch;
    if (ch === '\n') atLineStart = true;
    i++;
  }
  return out;
}
function unescapeMessageMarkdown(source) {
  const restored = stripMarkdownHtmlComments(source).replace(/^([ \t]*)\\(`{3,}|~{3,})/gm, '$1$2');
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
    return unescapeInlineCodeLine(part);
  }).join('');
}
const CODE_LANG_NAMES = {
  bash: 'Bash', c: 'C', cjs: 'JavaScript', cpp: 'C++', cs: 'C#', css: 'CSS',
  diff: 'Diff', go: 'Go', html: 'HTML', java: 'Java', javascript: 'JavaScript',
  js: 'JavaScript', json: 'JSON', jsx: 'JSX', kt: 'Kotlin', markdown: 'Markdown',
  md: 'Markdown', mermaid: 'Mermaid', mjs: 'JavaScript', php: 'PHP',
  plaintext: 'Text', py: 'Python', python: 'Python', rb: 'Ruby', rs: 'Rust',
  rust: 'Rust', sh: 'Shell', shell: 'Shell', sql: 'SQL', svg: 'SVG',
  swift: 'Swift', text: 'Text', toml: 'TOML', ts: 'TypeScript', tsx: 'TSX',
  txt: 'Text', typescript: 'TypeScript', xml: 'XML', yaml: 'YAML', yml: 'YAML',
  zsh: 'Zsh',
};
function formatCodeLanguage(inner) {
  const match = /^<code\s+class="language-([^\s"]+)"/i.exec(inner.trim());
  if (!match) return 'Code';
  const raw = match[1].toLowerCase();
  return CODE_LANG_NAMES[raw] || (raw.charAt(0).toUpperCase() + raw.slice(1));
}
function ensureCodeBlockHeaders(html) {
  if (typeof html !== 'string' || !html.includes('class="code-block"') || html.includes('class="code-block-header"')) return html;
  const attribute = value => messageMarkdown.utils.escapeHtml(value).replaceAll("'", '&#x27;');
  return html.replace(/<div class="code-block">((?:\s*<button\b[\s\S]*?<\/button>)*)\s*<pre>([\s\S]*?)<\/pre>\s*<\/div>/g, (_, buttons, inner) => {
    const header = `<div class="code-block-header"><span class="code-block-lang">${icon('braces', 14).outerHTML}<span>${attribute(formatCodeLanguage(inner))}</span></span></div>`;
    return `<div class="code-block">${buttons}${header}<pre>${inner}</pre></div>`;
  });
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
    const mdButton = /^<code\s+class="language-(?:markdown|md)"\s*>/i.test(inner.trim())
      ? `<button type="button" class="preview-code-md" aria-label="Preview Markdown" title="Preview Markdown" aria-pressed="false" data-code="${payload}">${icon('markdown', 14).outerHTML}</button>`
      : '';
    const button = `<button type="button" class="copy-code" aria-label="Copy code" title="Copy code" data-code="${payload}">${icon('copy', 14).outerHTML}</button>`;
    const header = `<div class="code-block-header"><span class="code-block-lang">${icon('braces', 14).outerHTML}<span>${attribute(formatCodeLanguage(inner))}</span></span></div>`;
    return `<div class="code-block">${mdButton}${button}${header}<pre>${inner}</pre></div>`;
  });
}
