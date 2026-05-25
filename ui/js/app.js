/**
 * HDL-Sim IDE-style web UI
 */

const DEFAULT_SOURCE = `// Verilog を編集して Run (F5) で実行
\`timescale 1ns/1ps

module counter #(parameter WIDTH = 4) (
    input clk,
    input rst,
    output [WIDTH-1:0] q
);
    reg [WIDTH-1:0] q;
    always @(posedge clk) begin
        if (rst) q <= 0;
        else q <= q + 1;
    end
endmodule

module tb;
    reg clk, rst;
    wire [3:0] count;
    counter dut (.clk(clk), .rst(rst), .q(count));
    initial begin
        clk = 0;
        forever #5 clk = ~clk;
    end
    initial begin
        rst = 1;
        #12 rst = 0;
    end
    initial begin
        #50 begin
            $display("PASS count=%0d", count);
            $finish;
        end
    end
endmodule
`;

const $ = (id) => document.getElementById(id);

/** @type {Map<string, {content: string, model: monaco.editor.ITextModel | null}>} */
const fileStore = new Map();
let activeFile = "design.v";
let editor = null;
let lastWaveform = null;
let selectedSignal = null;
let waveformVisible = false;
let abortController = null;

/** @type {Split.Instance | null} */
let splitH = null;
/** @type {Split.Instance | null} */
let splitV = null;

const SPLIT_SIZES = {
  h: { explorer: 18, editor: 82, wave: 0 },
  v: { main: 72, console: 28 },
};

function initFiles() {
  fileStore.set("design.v", { content: DEFAULT_SOURCE, model: null });
}

function setStatus(text, kind = "") {
  const bar = $("status-bar");
  bar.textContent = text;
  bar.className = "status-pill" + (kind ? ` ${kind}` : "");
}

function appendConsole(text, kind) {
  const el = $("console-output");
  if (!text) return;
  const prefix = kind === "err" ? "[ERROR] " : kind === "ok" ? "[OK] " : kind === "warn" ? "[WARN] " : "";
  const line = document.createElement("span");
  line.className = kind ? `line-${kind}` : "";
  line.textContent = prefix + text + (text.endsWith("\n") ? "" : "\n");
  el.appendChild(line);
  el.scrollTop = el.scrollHeight;
}

function clearConsole() {
  $("console-output").innerHTML = "";
}

function saveActiveEditor() {
  if (!editor || !activeFile) return;
  const entry = fileStore.get(activeFile);
  if (entry) entry.content = editor.getValue();
}

function getPayload() {
  saveActiveEditor();
  const top = $("input-top").value.trim();
  const files = [];
  for (const [path, entry] of fileStore) {
    files.push({ path, content: entry.content });
  }
  return {
    files,
    top: top || null,
    until: Number($("input-until").value) || null,
    max_events: Number($("input-max-events").value) || 500,
    generate_vcd: true,
  };
}

/* ── Split.js layout ── */

function initSplits() {
  splitV = Split(["#split-h-main", "#pane-console"], {
    direction: "vertical",
    sizes: [SPLIT_SIZES.v.main, SPLIT_SIZES.v.console],
    minSize: [160, 60],
    gutterSize: 4,
    snapOffset: 0,
    onDragEnd: (sizes) => {
      SPLIT_SIZES.v.main = sizes[0];
      SPLIT_SIZES.v.console = sizes[1];
      editor?.layout();
      if (lastWaveform) drawWave(lastWaveform);
    },
  });

  splitH = Split(["#pane-explorer", "#pane-editor", "#pane-waveform"], {
    direction: "horizontal",
    sizes: [SPLIT_SIZES.h.explorer, SPLIT_SIZES.h.editor, 0],
    minSize: [140, 280, 0],
    gutterSize: 4,
    snapOffset: 0,
    onDragEnd: (sizes) => {
      SPLIT_SIZES.h.explorer = sizes[0];
      SPLIT_SIZES.h.editor = sizes[1];
      SPLIT_SIZES.h.wave = sizes[2];
      editor?.layout();
      if (lastWaveform) drawWave(lastWaveform);
    },
  });
}

function toggleWaveform(show) {
  waveformVisible = show ?? !waveformVisible;
  const btn = $("btn-wave-toggle");

  if (waveformVisible) {
    const wave = Math.max(SPLIT_SIZES.h.wave || 28, 22);
    const explorer = SPLIT_SIZES.h.explorer;
    const editor = 100 - explorer - wave;
    splitH.setSizes([explorer, editor, wave]);
    SPLIT_SIZES.h.wave = wave;
    btn.classList.add("active");
    if (lastWaveform) drawWave(lastWaveform);
  } else {
    const sizes = splitH.getSizes();
    SPLIT_SIZES.h.explorer = sizes[0];
    SPLIT_SIZES.h.editor = sizes[1] + sizes[2];
    SPLIT_SIZES.h.wave = 0;
    splitH.setSizes([SPLIT_SIZES.h.explorer, SPLIT_SIZES.h.editor, 0]);
    btn.classList.remove("active");
  }
  editor?.layout();
}

/* ── Explorer tabs ── */

function switchExplorerTab(name) {
  document.querySelectorAll(".pane-tab").forEach((tab) => {
    const active = tab.dataset.pane === name;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  $("view-files").classList.toggle("active", name === "files");
  $("view-files").hidden = name !== "files";
  $("view-hierarchy").classList.toggle("active", name === "hierarchy");
  $("view-hierarchy").hidden = name !== "hierarchy";
}

/* ── File tree & editor tabs ── */

function renderEditorTabs() {
  const container = $("editor-tabs");
  container.innerHTML = "";
  for (const path of fileStore.keys()) {
    const tab = document.createElement("button");
    tab.type = "button";
    tab.className = "editor-tab" + (path === activeFile ? " active" : "");
    tab.setAttribute("role", "tab");
    tab.dataset.path = path;
    tab.innerHTML = `<span class="label">${path}</span>` +
      (fileStore.size > 1 ? `<span class="close" data-close="${path}">×</span>` : "");
    tab.addEventListener("click", (e) => {
      if (e.target.classList.contains("close")) {
        closeFile(e.target.dataset.close);
      } else {
        openFile(path);
      }
    });
    container.appendChild(tab);
  }
}

function renderFileTree() {
  const root = $("file-tree");
  root.innerHTML = "";
  const section = document.createElement("div");
  section.className = "tree-node";
  section.innerHTML = `<span class="twist">▼</span><span class="icon">📁</span><span class="label">WORKSPACE</span>`;
  root.appendChild(section);

  const children = document.createElement("div");
  children.className = "tree-children";
  for (const path of fileStore.keys()) {
    const node = document.createElement("div");
    node.className = "tree-node" + (path === activeFile ? " selected" : "");
    node.innerHTML = `<span class="twist empty"></span><span class="icon">📄</span><span class="label">${path}</span>`;
    node.addEventListener("click", () => openFile(path));
    node.addEventListener("dblclick", () => openFile(path));
    children.appendChild(node);
  }
  root.appendChild(children);
}

function getOrCreateModel(path, content) {
  const entry = fileStore.get(path);
  if (entry?.model) return entry.model;
  const uri = monaco.Uri.parse(`file:///${path}`);
  const model = monaco.editor.getModel(uri) || monaco.editor.createModel(content, "verilog", uri);
  if (entry) entry.model = model;
  return model;
}

function openFile(path) {
  if (!fileStore.has(path)) return;
  saveActiveEditor();
  activeFile = path;
  const entry = fileStore.get(path);
  editor.setModel(getOrCreateModel(path, entry.content));
  renderEditorTabs();
  renderFileTree();
}

function addFile(name) {
  let path = name || prompt("ファイル名 (例: dut.v):", "new.v");
  if (!path) return;
  path = path.trim();
  if (!path.endsWith(".v")) path += ".v";
  if (fileStore.has(path)) {
    openFile(path);
    return;
  }
  fileStore.set(path, { content: "// new file\n", model: null });
  openFile(path);
}

function closeFile(path) {
  if (fileStore.size <= 1) return;
  const entry = fileStore.get(path);
  if (entry?.model) {
    entry.content = entry.model.getValue();
    entry.model.dispose();
  }
  fileStore.delete(path);
  if (activeFile === path) {
    activeFile = fileStore.keys().next().value;
    openFile(activeFile);
  } else {
    renderEditorTabs();
    renderFileTree();
  }
}

/* ── Hierarchy tree ── */

function renderTreeNode(node, parentEl, depth = 0) {
  const hasChildren = node.children && node.children.length > 0;
  const row = document.createElement("div");
  row.className = "tree-node" + (node.name === selectedSignal ? " selected" : "");
  row.style.paddingLeft = `${depth * 4 + 4}px`;

  const twist = document.createElement("span");
  twist.className = "twist" + (hasChildren ? "" : " empty");
  twist.textContent = hasChildren ? "▼" : "";
  row.appendChild(twist);

  const icon = document.createElement("span");
  icon.className = "icon";
  icon.textContent = node.kind === "port" ? "◆" : node.kind === "module" ? "▣" : "○";
  row.appendChild(icon);

  const label = document.createElement("span");
  label.className = "label";
  label.textContent = node.name;
  row.appendChild(label);

  if (node.direction || (node.kind && node.kind !== "module")) {
    const badge = document.createElement("span");
    badge.className = "badge";
    badge.textContent = node.direction || node.kind;
    row.appendChild(badge);
  }

  row.addEventListener("click", (e) => {
    e.stopPropagation();
    selectedSignal = node.name;
    document.querySelectorAll("#hierarchy-tree .tree-node").forEach((n) => n.classList.remove("selected"));
    row.classList.add("selected");
    highlightSignal(node.name);
  });

  parentEl.appendChild(row);

  if (hasChildren) {
    const childWrap = document.createElement("div");
    childWrap.className = "tree-children";
    node.children.forEach((child) => renderTreeNode(child, childWrap, depth + 1));
    parentEl.appendChild(childWrap);

    twist.addEventListener("click", (e) => {
      e.stopPropagation();
      const collapsed = childWrap.classList.toggle("collapsed");
      twist.textContent = collapsed ? "▶" : "▼";
    });
  }
}

function renderHierarchy(tree) {
  const root = $("hierarchy-tree");
  root.innerHTML = "";
  if (!tree) {
    root.innerHTML = '<div class="empty-hint">Run または Elab で階層を表示</div>';
    return;
  }
  renderTreeNode(tree, root);
}

function renderSignalList(signals) {
  const list = $("signal-list");
  list.innerHTML = "";
  if (!signals?.length) {
    const li = document.createElement("li");
    li.textContent = "(none)";
    li.style.color = "var(--text-dim)";
    list.appendChild(li);
    return;
  }
  signals.forEach((sig) => {
    const li = document.createElement("li");
    li.dataset.name = sig.name;
    const name = document.createElement("span");
    name.textContent = sig.name;
    const val = document.createElement("span");
    val.className = "val";
    val.textContent = sig.value;
    li.appendChild(name);
    li.appendChild(val);
    li.addEventListener("click", () => {
      list.querySelectorAll("li").forEach((n) => n.classList.remove("active"));
      li.classList.add("active");
      selectedSignal = sig.name;
      highlightSignal(sig.name);
      if (!waveformVisible) toggleWaveform(true);
    });
    list.appendChild(li);
  });
}

function highlightSignal(name) {
  if (!lastWaveform) return;
  const filtered = {
    timescale: lastWaveform.timescale,
    signals: lastWaveform.signals.filter(
      (s) => s.name === name || s.name.endsWith("." + name) || name.endsWith(s.name)
    ),
  };
  if (!filtered.signals.length) filtered.signals = lastWaveform.signals.slice(0, 12);
  drawWave(filtered);
}

function drawWave(waveform) {
  if (!waveform) return;
  const canvas = $("waveform-canvas");
  window.HDLSimWaveform.drawWaveform(canvas, waveform, {
    wrap: $("waveform-wrap"),
    autoScroll: $("chk-auto-scroll")?.checked,
  });
}

/* ── API ── */

async function api(path, body, signal) {
  const res = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
    signal,
  });
  return res.json();
}

function setRunning(running) {
  $("btn-run").disabled = running;
  $("btn-stop").disabled = !running;
  $("btn-elab").disabled = running;
  $("btn-step").disabled = running;
}

async function loadExamples() {
  const sel = $("select-example");
  try {
    const items = await api("/api/examples");
    sel.innerHTML = '<option value="">—</option>';
    items.forEach((ex) => {
      const opt = document.createElement("option");
      opt.value = ex.id;
      opt.textContent = ex.label;
      sel.appendChild(opt);
    });
  } catch {
    setStatus("Examples failed", "err");
  }
}

async function openExample(id) {
  if (!id) return;
  setStatus("Loading…", "busy");
  const data = await api(`/api/examples/${encodeURIComponent(id)}`);
  const fileName = id.includes("/") ? id.split("/").pop() : id;
  fileStore.clear();
  fileStore.set(fileName, { content: data.content, model: null });
  activeFile = fileName;
  editor.setModel(getOrCreateModel(fileName, data.content));
  renderEditorTabs();
  renderFileTree();

  $("input-top").value = "";
  if (id.includes("silos")) $("input-top").value = "silos_regression_tb";
  else if (id.includes("tb_multi")) $("input-top").value = "tb_multi";
  else if (id.includes("hierarchy")) $("input-top").value = "tb";

  setStatus(`Loaded: ${id}`, "ok");
  runElaborate();
}

async function runElaborate() {
  setStatus("Elaborating…", "busy");
  try {
    const data = await api("/api/elaborate", getPayload());
    if (!data.ok) {
      appendConsole(data.error + "\n" + (data.trace || ""), "err");
      setStatus("Elab error", "err");
      switchExplorerTab("hierarchy");
      return;
    }
    renderHierarchy(data.hierarchy);
    if (data.top) $("input-top").placeholder = data.top;
    setStatus(`${data.net_count} nets · ${data.overview.module_names.length} modules`, "ok");
    appendConsole(`[elab] top=${data.top} nets=${data.net_count}`, "ok");
  } catch (e) {
    if (e.name !== "AbortError") {
      setStatus("Network error", "err");
      appendConsole(String(e), "err");
    }
  }
}

async function runSimulate() {
  setStatus("Running…", "busy");
  setRunning(true);
  clearConsole();
  abortController = new AbortController();

  try {
    const data = await api("/api/simulate", getPayload(), abortController.signal);
    if (!data.ok) {
      appendConsole(data.error + "\n" + (data.trace || ""), "err");
      setStatus("Sim failed", "err");
      return;
    }
    appendConsole(data.console || "(no output)");
    appendConsole(`time=${data.stop_time} events=${data.events_processed} top=${data.top_module}`, "ok");
    renderHierarchy(data.hierarchy);
    renderSignalList(data.signals);
    lastWaveform = data.waveform;
    if (!waveformVisible) toggleWaveform(true);
    drawWave(data.waveform);
    switchExplorerTab("hierarchy");
    setStatus(`Done t=${data.stop_time} ev=${data.events_processed}`, "ok");
  } catch (e) {
    if (e.name === "AbortError") {
      appendConsole("Simulation stopped by user", "warn");
      setStatus("Stopped", "warn");
    } else {
      setStatus("Network error", "err");
      appendConsole(String(e), "err");
    }
  } finally {
    setRunning(false);
    abortController = null;
  }
}

function stopSimulation() {
  abortController?.abort();
}

function runStep() {
  appendConsole("Step execution is not yet supported by the simulator backend.", "warn");
  setStatus("Step: not implemented", "warn");
}

/* ── Monaco ── */

function initMonaco() {
  require.config({
    paths: { vs: "https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs" },
  });
  require(["vs/editor/editor.main"], () => {
    monaco.editor.defineTheme("hdl-dark", {
      base: "vs-dark",
      inherit: true,
      rules: [
        { token: "comment", foreground: "6A9955" },
        { token: "keyword", foreground: "569CD6" },
        { token: "number", foreground: "B5CEA8" },
        { token: "string", foreground: "CE9178" },
      ],
      colors: {
        "editor.background": "#1e1e1e",
        "editor.foreground": "#d4d4d4",
        "editorLineNumber.foreground": "#858585",
        "editorLineNumber.activeForeground": "#cccccc",
        "editor.selectionBackground": "#264f78",
        "editor.inactiveSelectionBackground": "#3a3d41",
        "editorCursor.foreground": "#aeafad",
        "editor.lineHighlightBackground": "#2a2d2e",
      },
    });

    editor = monaco.editor.create($("editor-host"), {
      model: getOrCreateModel(activeFile, fileStore.get(activeFile).content),
      theme: "hdl-dark",
      automaticLayout: true,
      fontSize: 13,
      fontFamily: "'Cascadia Code', 'Consolas', 'Source Code Pro', monospace",
      lineNumbers: "on",
      minimap: { enabled: true, scale: 1, maxColumn: 80 },
      scrollBeyondLastLine: false,
      wordWrap: "off",
      renderWhitespace: "selection",
      tabSize: 4,
      insertSpaces: true,
      folding: true,
      glyphMargin: true,
    });

    editor.onDidChangeModelContent(() => {
      const entry = fileStore.get(activeFile);
      if (entry) entry.content = editor.getValue();
    });

    renderEditorTabs();
    renderFileTree();
    loadExamples();
    runElaborate();
  });
}

function bindUi() {
  $("btn-run").addEventListener("click", runSimulate);
  $("btn-stop").addEventListener("click", stopSimulation);
  $("btn-step").addEventListener("click", runStep);
  $("btn-elab").addEventListener("click", runElaborate);
  $("btn-clear-console").addEventListener("click", clearConsole);
  $("btn-wave-toggle").addEventListener("click", () => toggleWaveform());
  $("btn-wave-close").addEventListener("click", () => toggleWaveform(false));
  $("btn-wave-fit").addEventListener("click", () => drawWave(lastWaveform));
  $("btn-new-file").addEventListener("click", () => addFile());
  $("select-example").addEventListener("change", (e) => openExample(e.target.value));

  document.querySelectorAll(".pane-tab").forEach((tab) => {
    tab.addEventListener("click", () => switchExplorerTab(tab.dataset.pane));
  });

  window.addEventListener("resize", () => {
    editor?.layout();
    if (lastWaveform) drawWave(lastWaveform);
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "F5") {
      e.preventDefault();
      runSimulate();
    }
  });

  $("chk-auto-scroll")?.addEventListener("change", () => {
    if (lastWaveform) drawWave(lastWaveform);
  });
}

initFiles();
initSplits();
bindUi();
initMonaco();
