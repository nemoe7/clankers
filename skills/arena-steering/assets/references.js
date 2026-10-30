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

export function linkReferences(root, state) {
  const targets = referenceTargets(state);
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    const parent = node.parentElement;
    if (!parent?.closest(".message-text, .task-detail, #report") ||
        parent.closest("a, button, pre, script, style, svg, .mermaid, .receipt")) continue;
    const text = node.nodeValue || "";
    const fragments = document.createDocumentFragment();
    let last = 0;
    for (const match of text.matchAll(/[A-Za-z0-9_][A-Za-z0-9_-]*/g)) {
      const type = targets.get(match[0]);
      if (!type) continue;
      fragments.append(document.createTextNode(text.slice(last, match.index)));
      const button = document.createElement("button");
      button.type = "button";
      button.className = "reference-link";
      button.dataset.referenceType = type;
      button.dataset.referenceId = match[0];
      button.textContent = match[0];
      button.title = `Open ${type} ${match[0]}`;
      fragments.append(button);
      last = match.index + match[0].length;
    }
    if (last) {
      fragments.append(document.createTextNode(text.slice(last)));
      node.replaceWith(fragments);
    }
  }
}
