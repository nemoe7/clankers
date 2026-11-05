// Archived v1-only autosave integration block.
{
  const { test } = require("node:test");
  const { spawn } = require("node:child_process");
  test("autosave round-trips live preview HTTP responses and state import", async () => {
    const pyScript = `
import importlib, importlib.util, json, os, subprocess, sys, tempfile, threading
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

root = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("preview_mod", root / "skills/refs/arena-skill/scripts/preview.py")
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)

sys.path.insert(0, str(root / "skills/arena-skill/arena-egress-proxy/scripts"))
proxy_core = importlib.import_module("arena_proxy.core")
proxy_transfers = importlib.import_module("arena_proxy.transfers")

tmp = tempfile.TemporaryDirectory()
repo = Path(tmp.name) / "r"
repo.mkdir()
subprocess.run(["git", "init", "-b", "arena/11223344-r"], cwd=repo, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
state_dir = repo / "arena-state"
store = preview.Store(state_dir, create=True)
store.note("first-note", "initial note")
store.write_task("t-1", "Verify autosave", ["Check round-trip"], task_type="code")
report_md = state_dir / "sample-report.md"
report_md.write_text("# Sample Report\\n\\nProceed? {#go}\\n- (x) Yes\\n- ( ) No\\n", encoding="utf-8")
store.publish("sample-report", "Sample Report", report_md)

server = preview.ThreadingHTTPServer(("127.0.0.1", 0), preview.handler(store))
thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
thread.start()

proxy_state_dir = Path(tmp.name) / "proxy-state"
proxy_state_dir.mkdir()
proxy_server = proxy_core.build_server(SimpleNamespace(
  host="127.0.0.1",
  port=0,
  key="test-agent-key-0123456789",
  master="test-master-key-0123456789",
  token="",
  api="http://127.0.0.1:9",
  state_dir=str(proxy_state_dir),
  fetch_cap=proxy_transfers.DEFAULT_FETCH_CAP,
  stage_cap=proxy_transfers.DEFAULT_STAGE_CAP,
  quiet_polls=True,
  log_sink=lambda _line: None,
))
proxy_thread = threading.Thread(target=proxy_server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
proxy_thread.start()

print(json.dumps({
  "base": f"http://127.0.0.1:{server.server_port}",
  "proxy_base": f"http://127.0.0.1:{proxy_server.server_address[1]}",
}), flush=True)

for raw in sys.stdin:
  cmd = json.loads(raw)
  op = cmd["op"]
  if op == "mutate":
    store.note("second-note", "second note")
    store.write_task("t-1", "Verify autosave", ["Check round-trip"], status="finished", task_type="code")
    print(json.dumps({"ok": True}), flush=True)
  elif op == "diverge":
    snap = store.userscript_snapshot()
    history = [
      {
        "type": "userscript-autosave",
        "version": 1,
        "save_id": "11111111-1111-4111-8111-111111111111",
        "scope": snap["scope"],
        "digest": snap["digest"],
        "core": snap["core"],
        "stamp": "2098-01-01T00:00:00+00:00",
        "confirmed_at": "2098-01-01T00:00:00+00:00",
        "receipts": {},
      },
      {
        "type": "userscript-autosave",
        "version": 1,
        "save_id": "22222222-2222-4222-8222-222222222222",
        "scope": snap["scope"],
        "digest": snap["digest"],
        "core": snap["core"],
        "stamp": "2099-01-01T00:00:00+00:00",
        "confirmed_at": "2099-01-01T00:00:00+00:00",
        "receipts": {},
      },
    ]
    with closing(store.connect()) as db, db:
      db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (preview.AUTOSAVE_HISTORY, json.dumps(history)))
    store.note("third-note", "diverged note")
    print(json.dumps({"ok": True}), flush=True)
  elif op == "clear":
    store.clear_state()
    print(json.dumps({"ok": True, "force": store.userscript_snapshot().get("force")}), flush=True)
  elif op == "restore_prev":
    store.restore_state(previous=True)
    print(json.dumps({"ok": True, "force": store.userscript_snapshot().get("force")}), flush=True)
  elif op == "inspect":
    snap = store.userscript_snapshot()
    state_notes = {item["id"]: item for item in store.state()["notes"]}
    backup_notes = [
      {
        "id": item["id"],
        "quiet": item.get("quiet"),
        "blocking": item.get("blocking"),
        "type": (state_notes.get(item["id"]) or {}).get("type"),
        "text": item.get("text"),
        "attachments": [att["path"] for att in (item.get("attachments") or [])],
      }
      for item in store.read(include_quiet=True)["pending"]
      if (state_notes.get(item["id"]) or {}).get("type") == "state-backup"
    ]
    visible_notes = [
      item["id"] for item in store.state()["notes"] if not item.get("quiet")
    ]
    proxy_snap = proxy_server.state_store.get_state("r", "arena/11223344-r", include_text=True)
    print(json.dumps({
      "lastsave": snap["lastsave"],
      "beforelastsave": snap["beforelastsave"],
      "digest": snap["digest"],
      "force": snap.get("force"),
      "backup_notes": backup_notes,
      "visible_notes": visible_notes,
      "proxy_revision": proxy_snap.get("revision"),
      "proxy_text": proxy_snap.get("text", ""),
    }), flush=True)
  elif op == "import":
    dest = Path(tmp.name) / "imported" / "r"
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "arena/11223344-r"], cwd=dest, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=dest, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=dest, check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=dest, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    fresh = preview.Store(dest / "arena-state", create=True)
    counts = fresh.import_state(cmd["text"], replace_tasks=True)
    with closing(fresh.connect()) as db:
      row = db.execute("SELECT source FROM reports WHERE id = ?", ("sample-report",)).fetchone()
    hist_lines = fresh.userscript_history()
    fresh_snap = fresh.userscript_snapshot()
    print(json.dumps({
      "counts": counts,
      "report_source": row[0] if row else None,
      "history_count": len(hist_lines),
      "lastsave": fresh_snap.get("lastsave"),
      "beforelastsave": fresh_snap.get("beforelastsave"),
    }), flush=True)
  elif op == "quit":
    proxy_server.shutdown()
    proxy_server.server_close()
    server.shutdown()
    server.server_close()
    tmp.cleanup()
    print(json.dumps({"ok": True}), flush=True)
    break
`;
    const repoRoot = path.resolve(__dirname, "../..");
    const proc = spawn("python3", ["-c", pyScript, repoRoot], { stdio: ["pipe", "pipe", "inherit"] });
    const lines = [];
    let waiters = [];
    let buffer = "";
    proc.stdout.setEncoding("utf8");
    proc.stdout.on("data", chunk => {
      buffer += chunk;
      let idx;
      while ((idx = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, idx).trim();
        buffer = buffer.slice(idx + 1);
        if (!line) continue;
        const parsed = JSON.parse(line);
        if (waiters.length) waiters.shift()(parsed);
        else lines.push(parsed);
      }
    });
    const nextMessage = () => lines.length ? Promise.resolve(lines.shift()) : new Promise(resolve => waiters.push(resolve));
    const callPy = async payload => {
      proc.stdin.write(JSON.stringify(payload) + "\n");
      return nextMessage();
    };

    try {
      const { base, proxy_base: proxyBase } = await nextMessage();
      const source = fs.readFileSync(path.join(repoRoot, "userscripts/arena.user.js"), "utf8");
      const saved = new Map();
      const menus = new Map();
      const timers = [];
      let inFlight = [];
      const proxyWrites = [];
      const makeElement = tag => ({
        tagName: tag,
        children: [],
        style: {},
        attributes: {},
        listeners: {},
        textContent: "",
        click() {},
        setAttribute(name, value) { this.attributes[name] = String(value); },
        getAttribute(name) { return name in this.attributes ? this.attributes[name] : null; },
        appendChild(child) { child.parentNode = this; this.children.push(child); return child; },
        removeChild(child) { this.children = this.children.filter(item => item !== child); return child; },
        addEventListener(name, callback) { this.listeners[name] = callback; },
      });
      const body = makeElement("body");
      const iframe = { getAttribute: name => (name === "title" ? "App preview on port 8000" : null), src: base + "/" };
      const context = {
        document: {
          body,
          title: "Arena | r",
          visibilityState: "visible",
          createElement: makeElement,
          getElementById: id => body.children.find(child => child.id === id) || null,
          querySelectorAll: selector => (selector === "iframe[title]" ? [iframe] : []),
          querySelector: selector => {
            if (selector.indexOf("div.relative.z-10") === 0) {
              return {
                querySelectorAll(sel) {
                  if (sel === "span.truncate") return [{ textContent: "o/r" }];
                  if (sel === "a, [title]") {
                    return [{ getAttribute: name => (name === "href" ? "https://github.com/o/r/tree/arena/11223344-r" : null) }];
                  }
                  return [];
                },
              };
            }
            return null;
          },
          addEventListener: () => {},
        },
        location: { href: "https://arena.ai/agent/11223344", pathname: "/agent/11223344", search: "" },
        navigator: {},
        sessionStorage: { getItem: key => (key === "clankers-arena-agent-slug" ? "r" : null), setItem: () => {} },
        localStorage: { getItem: () => null, setItem: () => {} },
        MutationObserver: class { observe() {} disconnect() {} },
        setInterval: callback => { timers.push(callback); return timers.length; },
        clearInterval: () => {},
        setTimeout: callback => { callback(); return 0; },
        clearTimeout: () => {},
        fetch: () => Promise.reject(new Error("offline")),
        Blob: class { constructor(parts) { this.parts = parts; } },
        URL,
        console: { log() {}, warn() {}, error() {}, debug() {}, info() {} },
        GM_getValue: (key, fallback) => {
          if (saved.has(key)) return saved.get(key);
          if (key === "clankers-arena-show-settings-button") return false;
          return fallback;
        },
        GM_setValue: (key, value) => { saved.set(key, value); },
        GM_deleteValue: key => { saved.delete(key); },
        GM_registerMenuCommand: (label, callback) => { menus.set(label, callback); return label; },
        GM_unregisterMenuCommand: label => { menus.delete(label); },
        GM_xmlhttpRequest: options => {
          const targetUrl = String(options.url || "").replace("https://arena-proxy.example.ts.net", proxyBase);
          if ((options.method || "GET") === "POST" && targetUrl.includes("/v1/state")) {
            proxyWrites.push(JSON.parse(options.data));
          }
          const p = fetch(targetUrl, {
            method: options.method || "GET",
            headers: options.headers || {},
            body: options.data,
          }).then(async res => {
            const responseText = await res.text();
            if (options.onload) options.onload({ status: res.status, responseText });
          }).catch(err => {
            if (options.onerror) options.onerror(err);
          });
          inFlight.push(p);
        },
        GM_addStyle: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        matchMedia: () => ({ matches: false, addEventListener: () => {}, removeEventListener: () => {} }),
      };
      context.window = context;
      context.self = context;
      saved.set("clankers-arena-state-hinted", true);
      saved.set("clankers-arena-feature-prompt-fill", false);
      saved.set("clankers-arena-proxy-host", "https://arena-proxy.example.ts.net");
      saved.set("clankers-arena-proxy-master", "test-master-key-0123456789");
      vm.runInNewContext(source, context, { filename: "arena.user.js" });

      const drain = async () => {
        for (let i = 0; i < 6; i += 1) {
          const batch = inFlight;
          inFlight = [];
          await Promise.all(batch);
          await new Promise(setImmediate);
        }
      };
      const tick = () => timers.forEach(callback => callback());
      const panel = () => body.children.find(child => child.id === "clankers-state-panel") || null;
      const receiptKey = "clankers-arena-state-receipt-r-arena-11223344-r";

      await drain();
      assert.equal(proxyWrites.length, 1, "cold boot writes and confirms the first snapshot to /v1/state");
      assert.ok(Array.isArray(proxyWrites[0].core), "first cold-boot write sends full core");
      const firstReceipt = structuredClone(saved.get(receiptKey));
      const firstServer = await callPy({ op: "inspect" });
      assert.ok(firstReceipt && firstReceipt.lastsave);
      assert.equal(firstReceipt.lastsave, firstServer.lastsave);
      assert.equal(firstReceipt.beforelastsave, null);
      assert.equal(firstServer.proxy_revision, 1);

      await callPy({ op: "mutate" });
      tick();
      await drain();
      assert.equal(proxyWrites.length, 2, "second autosave relays full snapshot to /v1/state");
      assert.ok(Array.isArray(proxyWrites[1].core), "second autosave sends full core");
      assert.equal(proxyWrites[1].diff, undefined);
      const secondReceipt = structuredClone(saved.get(receiptKey));
      const secondServer = await callPy({ op: "inspect" });
      assert.equal(secondReceipt.lastsave, secondServer.lastsave);
      assert.equal(secondReceipt.beforelastsave, firstReceipt.lastsave);
      assert.equal(secondServer.proxy_revision, 2);

      await callPy({ op: "diverge" });
      tick();
      await drain();
      assert.equal(proxyWrites.length, 2, "diverged server stamps block automatic overwrite");
      assert.equal(panel(), null);
      const divergedServer = await callPy({ op: "inspect" });
      assert.equal(divergedServer.backup_notes.length, 1, "mismatch auto-uploads hydrated backup once to inbox");
      assert.equal(divergedServer.backup_notes[0].quiet, 1, "backup note is non-user-visible");
      assert.equal(divergedServer.backup_notes[0].blocking, 1, "backup note requires agent ack");
      assert.equal(divergedServer.backup_notes[0].type, "state-backup");
      assert.equal(divergedServer.visible_notes.includes(divergedServer.backup_notes[0].id), false);
      assert.match(divergedServer.backup_notes[0].text, /arena-preview state compare/);
      assert.match(divergedServer.backup_notes[0].text, /import with -r if newer/);
      assert.equal(divergedServer.backup_notes[0].attachments.length, 1);
      tick();
      await drain();
      const divergedAgain = await callPy({ op: "inspect" });
      assert.equal(divergedAgain.backup_notes.length, 1, "repeated ticks on same mismatch do not re-upload");

      menus.get("State - force save")();
      await drain();
      assert.equal(proxyWrites.length, 3, "Force save writes and re-synchronizes after divergence");
      assert.equal(panel(), null);
      const thirdReceipt = structuredClone(saved.get(receiptKey));
      const thirdServer = await callPy({ op: "inspect" });

      const imported = await callPy({ op: "import", text: thirdServer.proxy_text });
      assert.deepEqual(imported.counts, { notes: 3, tasks: 1, answers: 0, reports: 1 });
      assert.ok(imported.report_source && imported.report_source.endsWith("sample-report.md"));
      assert.equal(imported.history_count, 2);
      assert.equal(imported.lastsave, thirdReceipt.lastsave);
      assert.equal(imported.beforelastsave, thirdReceipt.beforelastsave);

      const clearedResp = await callPy({ op: "clear" });
      assert.equal(clearedResp.force, true, "clear_state sets force=true on userscript snapshot");
      tick();
      await drain();
      assert.equal(proxyWrites.length, 4, "server-side force flag writes cleared state without mismatch prompt");
      const afterClearServer = await callPy({ op: "inspect" });
      assert.equal(afterClearServer.force, false, "confirmation clears force flag");

      const restoredResp = await callPy({ op: "restore_prev" });
      assert.equal(restoredResp.force, true, "restore_state sets force=true on userscript snapshot");
      tick();
      await drain();
      assert.equal(proxyWrites.length, 5, "server-side force flag writes restored state without mismatch prompt");
      const afterRestoreServer = await callPy({ op: "inspect" });
      assert.match(afterRestoreServer.proxy_text, /third-note/);
    } finally {
      await callPy({ op: "quit" }).catch(() => {});
    }
  });
}
