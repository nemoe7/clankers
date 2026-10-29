/**
 * Safe offline Markdown renderer for messages, acks, and report blocks.
 */

const BRACES_SVG = `<svg class="lucide lucide-braces" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M8 3H7a2 2 0 0 0-2 2v5a2 2 0 0 1-2 2 2 2 0 0 1 2 2v5c0 1.1.9 2 2 2h1"></path><path d="M16 21h1a2 2 0 0 0 2-2v-5c0-1.1.9-2 2-2a2 2 0 0 1-2-2V5a2 2 0 0 0-2-2h-1"></path></svg>`;
const COPY_SVG = `<svg class="lucide lucide-copy" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"></rect><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"></path></svg>`;

const CODE_LANG_NAMES = {
  bash: "Bash",
  c: "C",
  cjs: "JavaScript",
  cpp: "C++",
  cs: "C#",
  css: "CSS",
  diff: "Diff",
  go: "Go",
  html: "HTML",
  java: "Java",
  javascript: "JavaScript",
  js: "JavaScript",
  json: "JSON",
  jsx: "JSX",
  kt: "Kotlin",
  markdown: "Markdown",
  md: "Markdown",
  mermaid: "Mermaid",
  mjs: "JavaScript",
  php: "PHP",
  plaintext: "Text",
  py: "Python",
  python: "Python",
  rb: "Ruby",
  rs: "Rust",
  rust: "Rust",
  sh: "Shell",
  shell: "Shell",
  sql: "SQL",
  svg: "SVG",
  swift: "Swift",
  text: "Text",
  toml: "TOML",
  ts: "TypeScript",
  tsx: "TSX",
  txt: "Text",
  typescript: "TypeScript",
  xml: "XML",
  yaml: "YAML",
  yml: "YAML",
  zsh: "Zsh",
};

export function escapeHtml(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function slugifyHeading(text) {
  return (
    "sec-" +
    String(text || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
  );
}

function formatCodeLang(raw) {
  const key = String(raw || "").trim().toLowerCase();
  if (!key) return "Code";
  return CODE_LANG_NAMES[key] || key.charAt(0).toUpperCase() + key.slice(1);
}

function highlightDiffLines(lines) {
  return lines
    .map((line) => {
      const escaped = escapeHtml(line);
      if (
        line.startsWith("diff ") ||
        line.startsWith("index ") ||
        line.startsWith("--- ") ||
        line.startsWith("+++ ")
      ) {
        return `<span class="token comment">${escaped}</span>`;
      }
      if (line.startsWith("@@")) {
        return `<span class="token coord">${escaped}</span>`;
      }
      if (line.startsWith("+")) {
        return `<span class="token inserted">${escaped}</span>`;
      }
      if (line.startsWith("-")) {
        return `<span class="token deleted">${escaped}</span>`;
      }
      return escaped;
    })
    .join("\n");
}

function renderCodeFence(lang, codeLines) {
  const rawCode = codeLines.join("\n");
  const escapedCode = escapeHtml(rawCode);
  const dataCode = escapedCode.replace(/\n/g, "&#10;");
  const langKey = String(lang || "").trim().toLowerCase();
  const langLabel = escapeHtml(formatCodeLang(langKey));
  const langClass = langKey ? ` class="language-${escapeHtml(langKey)}"` : "";
  const innerHtml =
    langKey === "diff" || langKey === "patch"
      ? highlightDiffLines(codeLines)
      : escapedCode;
  return `
    <div class="code-block">
      <button type="button" class="copy-code" aria-label="Copy code" title="Copy code" data-code="${dataCode}">${COPY_SVG}</button>
      <div class="code-block-header">
        <span class="code-block-lang">${BRACES_SVG}<span>${langLabel}</span></span>
      </div>
      <pre><code${langClass}>${innerHtml}</code></pre>
    </div>
  `;
}

export function renderInlineMarkdown(text) {
  let out = escapeHtml(text);
  out = out.replace(/`([^`\n]+)`/g, "<code>$1</code>");
  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  out = out.replace(/~~([^~]+)~~/g, "<del>$1</del>");
  out = out.replace(/==([^=]+)==/g, "<mark>$1</mark>");
  return out;
}

export function renderMarkdownBlock(markdown, { headings = null } = {}) {
  const lines = String(markdown ?? "").split(/\r?\n/);
  const html = [];
  let inCode = false;
  let codeLang = "";
  let codeLines = [];
  let inList = false;
  let tableRows = [];

  const closeList = () => {
    if (inList) {
      html.push("</ul>");
      inList = false;
    }
  };

  const closeTable = () => {
    if (!tableRows.length) return;
    const headerCells = tableRows[0];
    const bodyRows = tableRows.slice(
      tableRows.length > 1 &&
        tableRows[1].every((c) => /^:?-{2,}:?$/.test(c.trim()))
        ? 2
        : 1
    );
    const thead = `<thead><tr>${headerCells
      .map((c) => `<th>${renderInlineMarkdown(c.trim())}</th>`)
      .join("")}</tr></thead>`;
    const tbody = bodyRows.length
      ? `<tbody>${bodyRows
          .map(
            (r) =>
              `<tr>${r
                .map((c) => `<td>${renderInlineMarkdown(c.trim())}</td>`)
                .join("")}</tr>`
          )
          .join("")}</tbody>`
      : "";
    html.push(`<table>${thead}${tbody}</table>`);
    tableRows = [];
  };

  for (const line of lines) {
    const fenceMatch = line.trim().match(/^```([\w+-]*)\s*$/);
    if (fenceMatch || (inCode && line.trim().startsWith("```"))) {
      closeList();
      closeTable();
      if (inCode) {
        html.push(renderCodeFence(codeLang, codeLines));
        codeLines = [];
        codeLang = "";
        inCode = false;
      } else {
        inCode = true;
        codeLang = fenceMatch ? fenceMatch[1] : "";
      }
      continue;
    }
    if (inCode) {
      codeLines.push(line);
      continue;
    }
    const trimmed = line.trim();
    if (!trimmed) {
      closeList();
      closeTable();
      continue;
    }
    if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
      closeList();
      const cells = trimmed.slice(1, -1).split("|");
      tableRows.push(cells);
      continue;
    }
    closeTable();
    const heading = trimmed.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      closeList();
      const level = heading[1].length;
      const rawTitle = heading[2].trim();
      const id = slugifyHeading(rawTitle);
      if (Array.isArray(headings)) {
        headings.push({ id, level, text: rawTitle });
      }
      html.push(
        `<h${level} id="${escapeHtml(id)}">${renderInlineMarkdown(rawTitle)}</h${level}>`
      );
      continue;
    }
    const quote = trimmed.match(/^>\s?(.*)$/);
    if (quote) {
      closeList();
      html.push(
        `<blockquote><p>${renderInlineMarkdown(quote[1])}</p></blockquote>`
      );
      continue;
    }
    const bullet = trimmed.match(/^[-*]\s+(.+)$/);
    if (bullet) {
      if (!inList) {
        html.push("<ul>");
        inList = true;
      }
      html.push(`<li>${renderInlineMarkdown(bullet[1])}</li>`);
      continue;
    }
    closeList();
    html.push(`<p>${renderInlineMarkdown(trimmed)}</p>`);
  }
  closeList();
  closeTable();
  if (inCode) {
    html.push(renderCodeFence(codeLang, codeLines));
  }
  return html.join("\n");
}
