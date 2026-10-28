// Parse checks for the vendored offline Mermaid bundle.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');

const assets = path.resolve(__dirname, '../../../skills/refs/arena-skill/assets');
const bundlePath = path.join(assets, 'mermaid.min.js');
const licensePath = path.join(assets, 'mermaid.LICENSE');

function loadMermaid() {
  // The browser bundle sets a script global, so load it as a classic script.
  const sandbox = { console };
  sandbox.window = sandbox;
  sandbox.self = sandbox;
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(bundlePath, 'utf8'), sandbox, {
    filename: 'mermaid.min.js',
  });
  sandbox.mermaid.initialize({
    startOnLoad: false,
    securityLevel: 'strict',
    suppressErrorRendering: true,
  });
  return sandbox.mermaid;
}

test('vendored bundle is single-file and ships the MIT license', () => {
  const bundle = fs.readFileSync(bundlePath, 'utf8');
  assert.equal(bundle.includes('import('), false);
  assert.match(fs.readFileSync(licensePath, 'utf8'), /The MIT License \(MIT\)/);
});

test('vendored mermaid parses valid diagrams', async () => {
  const mermaid = loadMermaid();
  assert.equal((await mermaid.parse('graph TD\n  A-->B')).diagramType, 'flowchart-v2');
  assert.equal(
    (await mermaid.parse('sequenceDiagram\n  Alice->>Bob: Hi')).diagramType,
    'sequence'
  );
});

test('vendored mermaid rejects invalid syntax', async () => {
  const mermaid = loadMermaid();
  await assert.rejects(mermaid.parse('graph TD\n  A-->'), /Parse error/);
});
