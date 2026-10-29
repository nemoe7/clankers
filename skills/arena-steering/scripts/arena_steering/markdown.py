"""Server-side CommonMark renderer powered by markdown-it-py for Arena Steering."""

from __future__ import annotations

import html
import re
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.rules_inline.state_inline import Delimiter

ICON_COPY = (
  '<svg class="lucide lucide-copy" width="14" height="14" viewBox="0 0 24 24" '
  'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
  'stroke-linejoin="round" aria-hidden="true" focusable="false">'
  '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"></rect>'
  '<path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"></path></svg>'
)
ICON_MARKDOWN = (
  '<svg class="markdown-icon" width="14" height="14" viewBox="0 0 24 24" '
  'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
  'stroke-linejoin="round" aria-hidden="true" focusable="false">'
  '<path d="M22.27 19.385H1.73A1.73 1.73 0 0 1 0 17.655V6.345a1.73 1.73 0 0 1 '
  "1.73-1.73h20.54A1.73 1.73 0 0 1 24 6.345v11.308a1.73 1.73 0 0 1-1.73 1.731Z"
  "m-16.501-3.462v-4.5l2.308 2.885 2.307-2.885v4.5h2.308V8.078h-2.308l-2.307 "
  "2.885-2.308-2.885H3.46v7.847Zm15.463-3.923h-2.309V8.077h-2.307V12h-2.308"
  'l3.461 4.039Z" fill="currentColor" stroke="none"></path></svg>'
)
ICON_BRACES = (
  '<svg class="lucide lucide-braces" width="14" height="14" viewBox="0 0 24 24" '
  'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
  'stroke-linejoin="round" aria-hidden="true" focusable="false">'
  '<path d="M8 3H7a2 2 0 0 0-2 2v5a2 2 0 0 1-2 2 2 2 0 0 1 2 2v5c0 1.1.9 2 2 2h1"></path>'
  '<path d="M16 21h1a2 2 0 0 0 2-2v-5c0-1.1.9-2 2-2a2 2 0 0 1-2-2V5a2 2 0 0 0-2-2h-1"></path></svg>'
)

CODE_LANG_NAMES = {
  "bash": "Bash",
  "c": "C",
  "cjs": "JavaScript",
  "cpp": "C++",
  "cs": "C#",
  "css": "CSS",
  "diff": "Diff",
  "go": "Go",
  "html": "HTML",
  "java": "Java",
  "javascript": "JavaScript",
  "js": "JavaScript",
  "json": "JSON",
  "jsx": "JSX",
  "kt": "Kotlin",
  "markdown": "Markdown",
  "md": "Markdown",
  "mermaid": "Mermaid",
  "mjs": "JavaScript",
  "php": "PHP",
  "patch": "Diff",
  "plaintext": "Text",
  "py": "Python",
  "python": "Python",
  "rb": "Ruby",
  "rs": "Rust",
  "rust": "Rust",
  "sh": "Shell",
  "shell": "Shell",
  "sql": "SQL",
  "svg": "SVG",
  "swift": "Swift",
  "text": "Text",
  "toml": "TOML",
  "ts": "TypeScript",
  "tsx": "TSX",
  "txt": "Text",
  "typescript": "TypeScript",
  "xml": "XML",
  "yaml": "YAML",
  "yml": "YAML",
  "zsh": "Zsh",
}

SLUG_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def slugify_heading(text: str) -> str:
  """Build a stable `sec-...` anchor slug from a heading's plain text."""
  slug = SLUG_NON_ALNUM_RE.sub("-", str(text or "").lower()).strip("-")
  return f"sec-{slug}" if slug else "sec-heading"


def format_code_language(raw_lang: str) -> str:
  """Return a human-readable display label for a fenced code block language."""
  key = str(raw_lang or "").strip().split(None, 1)[0].lower() if raw_lang else ""
  if not key:
    return "Code"
  return CODE_LANG_NAMES.get(key, key[:1].upper() + key[1:])


def highlight_diff_code(raw_code: str) -> str:
  """Highlight unified diff / patch lines with semantic token spans."""
  lines = raw_code.split("\n")
  if lines and lines[-1] == "":
    lines = lines[:-1]
  out: list[str] = []
  for line in lines:
    escaped = html.escape(line, quote=False)
    if line.startswith(("diff ", "index ", "--- ", "+++ ")):
      out.append(f'<span class="token comment">{escaped}</span>')
    elif line.startswith("@@"):
      out.append(f'<span class="token coord">{escaped}</span>')
    elif line.startswith("+"):
      out.append(f'<span class="token inserted">{escaped}</span>')
    elif line.startswith("-"):
      out.append(f'<span class="token deleted">{escaped}</span>')
    else:
      out.append(escaped)
  return "\n".join(out)


def _highlight_mark_plugin(parser: MarkdownIt) -> None:
  """Register `==highlight==` inline `<mark>` delimiters on `parser`."""

  def tokenize(state: Any, silent: bool) -> bool:
    if silent or state.src[state.pos] != "=":
      return False
    scanned = state.scanDelims(state.pos, True)
    length = scanned.length
    if length < 2:
      return False
    if length % 2:
      state.push("text", "", 0).content = "="
      length -= 1
    for _ in range(0, length, 2):
      state.push("text", "", 0).content = "=="
      if scanned.can_open or scanned.can_close:
        state.delimiters.append(
          Delimiter(
            marker=ord("="),
            length=0,
            token=len(state.tokens) - 1,
            end=-1,
            open=scanned.can_open,
            close=scanned.can_close,
          )
        )
    state.pos += scanned.length
    return True

  def post_process(state: Any) -> None:
    groups = [state.delimiters] + [
      meta["delimiters"] for meta in state.tokens_meta if meta and "delimiters" in meta
    ]
    for delimiters in groups:
      lone: list[int] = []
      for start in delimiters:
        if start.marker != ord("=") or start.end == -1:
          continue
        end = delimiters[start.end]
        for index, nesting in ((start.token, 1), (end.token, -1)):
          token = state.tokens[index]
          token.type = "mark_open" if nesting == 1 else "mark_close"
          token.tag, token.nesting = "mark", nesting
          token.markup, token.content = "==", ""
        previous = state.tokens[end.token - 1]
        if previous.type == "text" and previous.content == "=":
          lone.append(end.token - 1)
      while lone:
        index = lone.pop()
        end_idx = index + 1
        while (
          end_idx < len(state.tokens) and state.tokens[end_idx].type == "mark_close"
        ):
          end_idx += 1
        end_idx -= 1
        if index != end_idx:
          state.tokens[index], state.tokens[end_idx] = (
            state.tokens[end_idx],
            state.tokens[index],
          )

  parser.inline.ruler.before("emphasis", "mark", tokenize)
  parser.inline.ruler2.before("emphasis", "mark", post_process)


def render_code_block(raw_lang: str, raw_code: str) -> str:
  """Render a fenced or indented code block with header, copy button, and diff tokens."""
  lang_key = str(raw_lang or "").strip().split(None, 1)[0].lower() if raw_lang else ""
  code_without_trailing = raw_code.removesuffix("\n")
  payload = html.escape(code_without_trailing, quote=True).replace("\n", "&#10;")

  if lang_key in {"diff", "patch"}:
    inner_code = highlight_diff_code(code_without_trailing)
  else:
    inner_code = html.escape(code_without_trailing, quote=False)

  lang_attr = (
    f' class="language-{html.escape(lang_key, quote=True)}"' if lang_key else ""
  )
  md_button = (
    f'<button type="button" class="preview-code-md" aria-label="Preview Markdown" '
    f'title="Preview Markdown" aria-pressed="false" data-code="{payload}">{ICON_MARKDOWN}</button>'
    if lang_key in {"markdown", "md"}
    else ""
  )
  mermaid_button = (
    f'<button type="button" class="preview-code-mermaid" aria-label="Show Mermaid code" '
    f'title="Show Mermaid code" aria-pressed="false" data-code="{payload}">{ICON_BRACES}</button>'
    if lang_key == "mermaid"
    else ""
  )
  copy_button = (
    f'<button type="button" class="copy-code" aria-label="Copy code" '
    f'title="Copy code" data-code="{payload}">{ICON_COPY}</button>'
  )
  lang_label = html.escape(format_code_language(lang_key), quote=True)
  header = (
    f'<div class="code-block-header"><span class="code-block-lang">'
    f"{ICON_BRACES}<span>{lang_label}</span></span></div>"
  )
  return (
    f'<div class="code-block">{md_button}{mermaid_button}{copy_button}{header}'
    f"<pre><code{lang_attr}>{inner_code}</code></pre></div>"
  )


def _create_parser(*, breaks: bool = False) -> MarkdownIt:
  parser = MarkdownIt("commonmark", {"html": False, "breaks": breaks}).enable(
    ["table", "strikethrough"]
  )
  _highlight_mark_plugin(parser)

  def _render_link_open(
    renderer: Any, tokens: Any, idx: int, options: Any, env: Any
  ) -> str:
    token = tokens[idx]
    href = token.attrGet("href") or ""
    if href and not href.startswith("#"):
      token.attrSet("target", "_blank")
      token.attrSet("rel", "noopener noreferrer")
    return str(renderer.renderToken(tokens, idx, options, env))

  def _render_heading_open(
    renderer: Any, tokens: Any, idx: int, options: Any, env: Any
  ) -> str:
    token = tokens[idx]
    inline_token = tokens[idx + 1] if idx + 1 < len(tokens) else None
    raw_text = (inline_token.content if inline_token is not None else "").strip()
    heading_id = slugify_heading(raw_text)
    token.attrSet("id", heading_id)
    headings = env.get("headings") if isinstance(env, dict) else None
    if isinstance(headings, list) and token.tag.startswith("h"):
      try:
        level = int(token.tag[1:])
      except ValueError:
        level = 2
      headings.append({"id": heading_id, "level": level, "text": raw_text})
    return str(renderer.renderToken(tokens, idx, options, env))

  def _render_fence(
    _renderer: Any, tokens: Any, idx: int, _options: Any, _env: Any
  ) -> str:
    token = tokens[idx]
    info = html.unescape(token.info.strip()) if token.info else ""
    return render_code_block(info, token.content)

  def _render_code_block(
    _renderer: Any, tokens: Any, idx: int, _options: Any, _env: Any
  ) -> str:
    token = tokens[idx]
    return render_code_block("", token.content)

  parser.add_render_rule("link_open", _render_link_open)
  parser.add_render_rule("heading_open", _render_heading_open)
  parser.add_render_rule("fence", _render_fence)
  parser.add_render_rule("code_block", _render_code_block)
  return parser


_PARSER_STANDARD = _create_parser(breaks=False)
_PARSER_BREAKS = _create_parser(breaks=True)


def render_markdown(
  markdown: str,
  *,
  breaks: bool = False,
  headings: list[dict[str, Any]] | None = None,
) -> str:
  """Render CommonMark text to safe HTML using markdown-it-py."""
  parser = _PARSER_BREAKS if breaks else _PARSER_STANDARD
  env: dict[str, Any] = {}
  if headings is not None:
    env["headings"] = headings
  return str(parser.render(str(markdown or ""), env)).strip()
