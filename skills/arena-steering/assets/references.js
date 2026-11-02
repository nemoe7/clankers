// Link exact, unambiguous references in rendered prose.
export function referenceTargets(state) {
  const targets = new Map();
  for (const [type, items] of [["message", state.messages], ["report", state.reports], ["task", state.tasks]]) {
    for (const item of items || []) {
      if (!item.id) continue;
      targets.set(item.id, targets.has(item.id) ? null : type);
    }
  }
  return targets;
}

function referenceButton(id, type) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "reference-link";
  button.dataset.autoReference = "true";
  button.dataset.referenceType = type;
  button.dataset.referenceId = id;
  button.textContent = id;
  button.title = `Open ${type} ${id}`;
  return button;
}

export function linkReferences(root, state) {
  const targets = referenceTargets(state);
  // Retained message cards can outlive the set of loaded reference targets.
  // Reconsider only links generated here, not explicit receipt links.
  for (const link of root.querySelectorAll("[data-auto-reference]")) {
    if (targets.get(link.dataset.referenceId) !== link.dataset.referenceType) {
      link.replaceWith(document.createTextNode(link.textContent || ""));
    }
  }
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    const parent = node.parentElement;
    if (!parent?.closest(".message-text, .task-detail, #report") ||
        parent.closest("a, button, pre, script, style, svg, .mermaid, .receipt")) continue;
    const text = node.nodeValue || "";
    if (parent.tagName === "CODE") {
      const type = targets.get(text);
      if (type && parent.textContent === text) node.replaceWith(referenceButton(text, type));
      continue;
    }
    // Task details are escaped plain text, so their complete backticked IDs need an inline code element.
    if (!parent.classList.contains("task-detail")) continue;
    const fragments = document.createDocumentFragment();
    let last = 0;
    for (const match of text.matchAll(/`([A-Za-z0-9_][A-Za-z0-9_-]*)`/g)) {
      if (text[match.index - 1] === "`" || text[match.index + match[0].length] === "`") continue;
      const type = targets.get(match[1]);
      if (!type) continue;
      fragments.append(document.createTextNode(text.slice(last, match.index)));
      const code = document.createElement("code");
      code.append(referenceButton(match[1], type));
      fragments.append(code);
      last = match.index + match[0].length;
    }
    if (last) {
      fragments.append(document.createTextNode(text.slice(last)));
      node.replaceWith(fragments);
    }
  }
}
