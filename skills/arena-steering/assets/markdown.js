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
  const mermaidBtn =
    langKey === "mermaid"
      ? `<button type="button" class="preview-code-mermaid" aria-label="Show Mermaid code" title="Show Mermaid code" aria-pressed="false" data-code="${dataCode}">${BRACES_SVG}</button>`
      : "";
  const mermaidStateAttr =
    langKey === "mermaid" ? ` data-mermaid-state="pending"` : "";
  return `
    <div class="code-block"${mermaidStateAttr}>
      ${mermaidBtn}
      <button type="button" class="copy-code" aria-label="Copy code" title="Copy code" data-code="${dataCode}">${COPY_SVG}</button>
      <div class="code-block-header">
        <span class="code-block-lang">${BRACES_SVG}<span>${langLabel}</span></span>
      </div>
      <pre><code${langClass}>${innerHtml}</code></pre>
    </div>
  `;
}

export function sanitizeMermaidSvg(svgText) {
  if (typeof svgText !== "string") return null;
  const trimmed = svgText.trim();
  if (!/^<svg\b[\s\S]*<\/svg>$/i.test(trimmed)) return null;
  if (
    /<(script|foreignobject|iframe|object|embed|audio|video|canvas|applet|meta|link)\b/i.test(
      trimmed
    )
  ) {
    return null;
  }
  if (
    /\bon[a-z]+\s*=|javascript:|vbscript:|data:text\/html|@import|\burl\s*\(\s*["']?\s*(?!#)/i.test(
      trimmed
    )
  ) {
    return null;
  }
  if (/\b(?:xlink:)?href\s*=\s*["']?\s*(?!#)/i.test(trimmed)) {
    return null;
  }
  if (!/\bclass\s*=\s*["'][^"']*mermaid-svg/i.test(trimmed)) {
    return trimmed.replace(/^<svg\b/i, '<svg class="mermaid-svg" role="img"');
  }
  return trimmed;
}

let mermaidSeq = 0;
let mermaidInitialized = false;
const mermaidSvgCache = new Map();

export function initializeMermaid() {
  const lib = globalThis.mermaid;
  if (!lib?.initialize) return null;
  if (!mermaidInitialized) {
    lib.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      htmlLabels: false,
      maxTextSize: 50000,
      maxEdges: 500,
      suppressErrorRendering: true,
      theme: "base",
      themeVariables: {
        darkMode: true,
        background: "#22252b",
        fontFamily:
          '"Basel Grotesk", -apple-system, BlinkMacSystemFont, sans-serif',
        fontSize: "13px",
        primaryColor: "#2b2f37",
        primaryTextColor: "#f3f4f6",
        primaryBorderColor: "#68b5f8",
        secondaryColor: "#242830",
        secondaryTextColor: "#f3f4f6",
        secondaryBorderColor: "#4a505c",
        tertiaryColor: "#1b1e23",
        tertiaryTextColor: "#9da3ae",
        tertiaryBorderColor: "#373b44",
        lineColor: "#9da3ae",
        textColor: "#f3f4f6",
        mainBkg: "#2b2f37",
        secondBkg: "#242830",
        nodeBorder: "#68b5f8",
        clusterBkg: "#1b1e23",
        clusterBorder: "#373b44",
        defaultLinkColor: "#9da3ae",
        titleColor: "#f9fafb",
        edgeLabelBackground: "#22252b",
        actorBkg: "#2b2f37",
        actorBorder: "#68b5f8",
        actorTextColor: "#f3f4f6",
        actorLineColor: "#9da3ae",
        signalColor: "#f3f4f6",
        signalTextColor: "#f3f4f6",
        labelBoxBkgColor: "#242830",
        labelBoxBorderColor: "#4a505c",
        labelTextColor: "#f3f4f6",
        loopTextColor: "#9da3ae",
        noteBkgColor: "#242830",
        noteTextColor: "#f3f4f6",
        noteBorderColor: "#68b5f8",
      },
      flowchart: { htmlLabels: false },
    });
    mermaidInitialized = true;
  }
  return lib;
}

function mountMermaidDiagram(block, codeEl, rawSource, safeSvg) {
  if (!block.querySelector(".preview-code-mermaid")) {
    const dataCode = escapeHtml(rawSource).replace(/\n/g, "&#10;");
    block.insertAdjacentHTML(
      "afterbegin",
      `<button type="button" class="preview-code-mermaid" aria-label="Show Mermaid code" title="Show Mermaid code" aria-pressed="false" data-code="${dataCode}">${BRACES_SVG}</button>`
    );
  }
  let diagramDiv = block.querySelector(":scope > .mermaid-diagram");
  if (!diagramDiv) {
    diagramDiv = document.createElement("div");
    diagramDiv.className = "mermaid-diagram";
    diagramDiv.setAttribute("role", "img");
    diagramDiv.setAttribute("aria-label", "Mermaid diagram");
    const preEl = codeEl.closest("pre");
    block.insertBefore(diagramDiv, preEl);
  }
  diagramDiv.innerHTML = safeSvg;
  block.dataset.mermaidState = "rendered";
}

export async function hydrateMermaidBlocks(rootEl = document) {
  if (!rootEl?.querySelectorAll) return;
  const codeNodes = rootEl.querySelectorAll(
    ".code-block > pre > code.language-mermaid"
  );
  if (!codeNodes.length) return;
  const lib = initializeMermaid();
  for (const codeEl of codeNodes) {
    const block = codeEl.closest(".code-block");
    if (
      !block ||
      (block.dataset.mermaidState &&
        block.dataset.mermaidState !== "pending")
    ) {
      continue;
    }
    const rawSource = (codeEl.textContent || "").trim();
    if (!rawSource) {
      block.dataset.mermaidState = "fallback";
      block.querySelector(".preview-code-mermaid")?.remove();
      continue;
    }
    const cachedSvg = mermaidSvgCache.get(rawSource);
    if (cachedSvg) {
      mountMermaidDiagram(block, codeEl, rawSource, cachedSvg);
      continue;
    }
    if (!lib?.render) {
      block.dataset.mermaidState = "fallback";
      block.querySelector(".preview-code-mermaid")?.remove();
      continue;
    }
    try {
      mermaidSeq += 1;
      const rendered = await lib.render(
        `mermaid-steering-${mermaidSeq}`,
        rawSource
      );
      const svgRaw = typeof rendered === "string" ? rendered : rendered?.svg;
      const safeSvg = sanitizeMermaidSvg(svgRaw);
      if (!safeSvg) {
        block.dataset.mermaidState = "fallback";
        block.querySelector(".preview-code-mermaid")?.remove();
        continue;
      }
      mermaidSvgCache.set(rawSource, safeSvg);
      if (!block.isConnected) continue;
      mountMermaidDiagram(block, codeEl, rawSource, safeSvg);
    } catch {
      block.dataset.mermaidState = "fallback";
      block.querySelector(".preview-code-mermaid")?.remove();
    }
  }
}

export function toggleCodeMermaid(button) {
  const block = button?.closest?.(".code-block");
  if (
    !block ||
    !block.dataset.mermaidState ||
    block.dataset.mermaidState === "fallback" ||
    block.dataset.mermaidState === "pending"
  ) {
    return;
  }
  const showingCode = block.dataset.mermaidState === "code";
  if (showingCode) {
    block.dataset.mermaidState = "rendered";
    button.setAttribute("aria-pressed", "false");
    button.setAttribute("aria-label", "Show Mermaid code");
    button.title = "Show Mermaid code";
  } else {
    block.dataset.mermaidState = "code";
    button.setAttribute("aria-pressed", "true");
    button.setAttribute("aria-label", "Show Mermaid diagram");
    button.title = "Show Mermaid diagram";
  }
}

export function renderInlineMarkdown(text) {
  let out = escapeHtml(text);
  out = out.replace(/`([^`\n]+)`/g, "<code>$1</code>");
  out = out.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+|#[^\s)]+)\)/g,
    (_m, label, url) => {
      const ext = url.startsWith("#")
        ? ""
        : ' target="_blank" rel="noopener noreferrer"';
      return `<a href="${url}"${ext}>${label}</a>`;
    }
  );
  out = out.replace(
    /(^|[\s(])(https?:\/\/[^\s<>()]+?)(?=[.,;:!?]?(?:[\s)]|$))/g,
    '$1<a href="$2" target="_blank" rel="noopener noreferrer">$2</a>'
  );
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
      const taskMatch = bullet[1].match(/^\[([ xX])\]\s+(.+)$/);
      if (taskMatch) {
        const checkedAttr =
          taskMatch[1].toLowerCase() === "x" ? " checked" : "";
        html.push(
          `<li class="task-list-item"><input type="checkbox" class="task-list-item-checkbox" disabled${checkedAttr}> ${renderInlineMarkdown(taskMatch[2])}</li>`
        );
      } else {
        html.push(`<li>${renderInlineMarkdown(bullet[1])}</li>`);
      }
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
