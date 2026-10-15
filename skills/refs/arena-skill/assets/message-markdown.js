'use strict';
const messageMarkdown = markdownit('commonmark', { html: false, breaks: true }).enable(['table', 'strikethrough']);
messageMarkdown.renderer.rules.link_open = (tokens, index, options, env, renderer) => {
  const token = tokens[index];
  const href = token.attrGet('href') || '';
  if (href && !href.startsWith('#')) {
    token.attrSet('target', '_blank');
    token.attrSet('rel', 'noopener noreferrer');
  }
  return renderer.renderToken(tokens, index, options, env);
};
function renderMessageMarkdown(source) {
  const attribute = value => messageMarkdown.utils.escapeHtml(value).replaceAll("'", '&#x27;');
  const images = [];
  const imagePrefix = 'previewimage' + crypto.randomUUID().replaceAll('-', '');
  const tagged = source.replace(/!\[([^\]\n]*)\]\((\S+?)\s+=(\p{Nd}+)x(\p{Nd}*)\)/gu, (match, alt, url, width, height) => {
    if (!messageMarkdown.validateLink(url)) return match;
    images.push(`<img src="${attribute(url)}" alt="${attribute(alt)}" width="${width}"${height ? ` height="${height}"` : ''} />`);
    return ` ${imagePrefix}${images.length - 1}x `;
  });
  let rendered = messageMarkdown.render(tagged.replace(/^([ \t]*)\\(`{3,}|~{3,})/gm, '$1$2'));
  rendered = rendered.replace(/<p>[\s\S]*?<\/p>/g, paragraph => paragraph.replace(/<br\s*\/?>/g, ''));
  rendered = rendered.replace(new RegExp(`${imagePrefix}(\\d+)x`, 'g'), (_, index) => images[Number(index)]);
  return rendered.replace(/<pre>([\s\S]*?)<\/pre>/g, (_, inner) => {
    const code = inner.replace(/<[^>]+>/g, '').replace(/&(?:#\d+|#x[\da-f]+|[a-z][\da-z]+);/gi, entity => messageMarkdown.utils.unescapeAll(entity));
    const payload = attribute(code).replaceAll('\n', '&#10;');
    const button = `<button type="button" class="copy-code" aria-label="Copy code" title="Copy code" data-code="${payload}">${icon('copy', 14).outerHTML}</button>`;
    return `<div class="code-block">${button}<pre>${inner}</pre></div>`;
  });
}
