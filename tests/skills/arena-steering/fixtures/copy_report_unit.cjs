// Exercise the Reports-only selection copy without relying on browser clipboard permissions.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const asset = fs.readFileSync(
  path.resolve(__dirname, "../../../../skills/arena-steering/assets/copy.js"),
  "utf8",
);
assert.ok(asset.includes("export function copyText("), "selection-copy helper is present");
assert.ok(!asset.includes("navigator.clipboard"), "Copy does not use the Clipboard API");
const helper = asset.replace("export function", "function");

for (const outcome of [true, false, "throw", "missing", "append-throw"]) {
  let appended = false;
  let selected = false;
  let removed = false;
  let apiCalls = 0;
  const field = {
    value: "",
    style: {},
    setAttribute(name, value) {
      assert.equal(name, "readonly");
      assert.equal(value, "");
    },
    select() { selected = true; },
    remove() { removed = true; },
  };
  const document = {
    activeElement: null,
    getSelection() { return null; },
    createElement(name) {
      assert.equal(name, "textarea");
      return field;
    },
    body: {
      append(element) {
        assert.equal(element, field);
        appended = true;
        if (outcome === "append-throw") throw new Error("document unavailable");
      },
    },
    execCommand: outcome === "missing" ? undefined : (command) => {
      assert.equal(command, "copy");
      assert.equal(field.value, "v1-copy-probe");
      assert.ok(selected);
      if (outcome === "throw") throw new Error("copy denied");
      return outcome;
    },
  };
  const navigator = {
    clipboard: {
      writeText() { apiCalls += 1; throw new Error("Clipboard API denied"); },
    },
  };
  const copied = vm.runInNewContext(
    `${helper}\ncopyText("v1-copy-probe")`,
    { document, navigator, HTMLElement: class {} },
  );
  assert.equal(copied, outcome === true, `unexpected result: ${outcome}`);
  assert.ok(appended && removed, `missing cleanup: ${outcome}`);
  assert.equal(selected, outcome !== "append-throw");
  assert.equal(apiCalls, 0, "Reports Copy must not attempt the Clipboard API");
}
