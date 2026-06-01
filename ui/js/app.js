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

/** Virtual workspace: path → { content, model } */
const fileStore = new Map();
let activeFile = "design.v";
let editor = null;
const fileEditors = new Map();
const mdiWindows = new Map();
let mdiZ = 10;
let lastWaveform = null;
let selectedSignal = null;
let waveformVisible = false;
let waveZoom = 1;
let abortController = null;

/** @type {Split.Instance | null} */
let splitH = null;
/** @type {Split.Instance | null} */
let splitV = null;

const SPLIT_SIZES = {
  h: { explorer: 18, editor: 82, wave: 0 },
  v: { main: 72, console: 28 },
};

let currentProject = "";
let spjDirPath = "";
const RECENT_SPJ_KEY = "hdl-sim-recent-spj";
const RECENT_SPJ_MAX = 8;

const viewState = {
  mainToolbar: true,
  outputPanel: true,
  projectBar: true,
};

let simRunning = false;
let debugSingleStep = false;

function initFiles() {
  fileStore.set("design.v", { content: DEFAULT_SOURCE, model: null });
}

function setStatus(text, kind = "") {
  const bar = $("status-bar");
  bar.textContent = text;
  bar.className = "status-pill" + (kind ? ` ${kind}` : "");
}

function appendConsole(text, kind = "") {
  const targets = [$("console-output"), $("mdi-console-output")].filter(Boolean);
  if (text == null || text === "") return;

  const prefix =
    kind === "err" ? "[ERROR] " :
    kind === "ok" ? "[OK] " :
    kind === "warn" ? "[WARN] " :
    kind === "info" ? "" : "";

  const lines = String(text).replace(/\r\n/g, "\n").split("\n");
  lines.forEach((line, index) => {
    if (line === "" && index === lines.length - 1) return;

    let lineKind = kind;
    if (!lineKind) {
      if (/^(Traceback|Error|Exception|SyntaxError|\.{3})/i.test(line) || /\bError:/i.test(line)) {
        lineKind = "err";
      } else if (/^\s+File "/.test(line) || /^\s+\^/.test(line)) {
        lineKind = "trace";
      } else if (/^PASS|^OK|\bPASS\b/i.test(line)) {
        lineKind = "ok";
      }
    } else if (lineKind === "err" && /^\s+File "/.test(line)) {
      lineKind = "trace";
    }

    const row = document.createElement("div");
    row.className = "console-line" + (lineKind ? ` line-${lineKind}` : "");
    row.textContent = (index === 0 ? prefix : "") + line;
    targets.forEach((el) => el.appendChild(row.cloneNode(true)));
  });
  targets.forEach((el) => { el.scrollTop = el.scrollHeight; });
}

function clearConsole() {
  $("console-output").innerHTML = "";
  const mdiOut = $("mdi-console-output");
  if (mdiOut) mdiOut.innerHTML = "";
}

function saveActiveEditor() {
  for (const [, entry] of fileStore) {
    if (entry.model) entry.content = entry.model.getValue();
  }
}

function getPayload() {
  saveActiveEditor();
  const top = $("input-top").value.trim();
  const files = [];
  for (const [path, entry] of fileStore) {
    files.push({ path, content: entry.content });
  }
  files.sort((a, b) => a.path.localeCompare(b.path));
  return {
    files,
    top: top || null,
    until: Number($("input-until").value) || null,
    max_events: Number($("input-max-events").value) || 500,
    generate_vcd: true,
  };
}

function updateTopModuleList(moduleNames, suggestedTop) {
  const datalist = $("top-module-list");
  datalist.innerHTML = "";
  if (!moduleNames?.length) return;

  const sorted = [...moduleNames].sort((a, b) => {
    const score = (n) => {
      let s = n.length * 0.001;
      if (n === suggestedTop) s -= 10;
      if (n.endsWith("_tb") || n === "tb") s -= 5;
      return s;
    };
    return score(a) - score(b) || a.localeCompare(b);
  });

  sorted.forEach((name) => {
    const opt = document.createElement("option");
    opt.value = name;
    datalist.appendChild(opt);
  });

  const input = $("input-top");
  if (!input.value.trim() && suggestedTop) {
    input.value = suggestedTop;
  }
}

function syncDeleteButton() {
  const btn = $("btn-delete-file");
  if (btn) btn.disabled = fileStore.size <= 1;
}

function mdiCanvas() {
  return $("mdi-canvas");
}

function bringMdiToFront(win) {
  if (!win) return;
  mdiZ += 1;
  win.style.zIndex = String(mdiZ);
  document.querySelectorAll(".mdi-window").forEach((node) => node.classList.remove("active"));
  win.classList.add("active");
}

function createMdiWindow(id, title, { x = 40, y = 40, width = 520, height = 360, bodyClass = "" } = {}) {
  const existing = mdiWindows.get(id);
  if (existing) {
    existing.hidden = false;
    bringMdiToFront(existing);
    return existing;
  }

  const win = document.createElement("section");
  win.className = "mdi-window";
  win.dataset.mdiId = id;
  win.style.left = `${x}px`;
  win.style.top = `${y}px`;
  win.style.width = `${width}px`;
  win.style.height = `${height}px`;

  const titlebar = document.createElement("div");
  titlebar.className = "mdi-titlebar";
  const titleEl = document.createElement("span");
  titleEl.className = "mdi-title";
  titleEl.textContent = title;
  titlebar.appendChild(titleEl);

  const controls = document.createElement("div");
  controls.className = "mdi-controls";
  const close = document.createElement("button");
  close.type = "button";
  close.className = "mdi-btn close";
  close.title = "閉じる";
  close.textContent = "×";
  close.addEventListener("click", (e) => {
    e.stopPropagation();
    win.hidden = true;
    if (id === "waveform") {
      waveformVisible = false;
      $("btn-wave-toggle")?.classList.remove("active");
    }
  });
  controls.appendChild(close);
  titlebar.appendChild(controls);

  const body = document.createElement("div");
  body.className = `mdi-body ${bodyClass}`.trim();

  win.appendChild(titlebar);
  win.appendChild(body);
  mdiCanvas().appendChild(win);
  mdiWindows.set(id, win);
  bringMdiToFront(win);

  let dragging = false;
  let startX = 0;
  let startY = 0;
  let startLeft = 0;
  let startTop = 0;
  titlebar.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    dragging = true;
    bringMdiToFront(win);
    startX = e.clientX;
    startY = e.clientY;
    startLeft = win.offsetLeft;
    startTop = win.offsetTop;
    titlebar.setPointerCapture(e.pointerId);
  });
  titlebar.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    win.style.left = `${Math.max(0, startLeft + e.clientX - startX)}px`;
    win.style.top = `${Math.max(0, startTop + e.clientY - startY)}px`;
  });
  titlebar.addEventListener("pointerup", (e) => {
    dragging = false;
    titlebar.releasePointerCapture(e.pointerId);
  });
  win.addEventListener("pointerdown", () => bringMdiToFront(win));

  return win;
}

function initMdiPan() {
  const desktop = $("mdi-desktop");
  if (!desktop) return;

  let panning = false;
  let startX = 0;
  let startY = 0;
  let startLeft = 0;
  let startTop = 0;

  desktop.addEventListener("pointerdown", (e) => {
    if (e.button !== 1) return;
    e.preventDefault();
    panning = true;
    startX = e.clientX;
    startY = e.clientY;
    startLeft = desktop.scrollLeft;
    startTop = desktop.scrollTop;
    desktop.classList.add("panning");
    desktop.setPointerCapture(e.pointerId);
  });

  desktop.addEventListener("pointermove", (e) => {
    if (!panning) return;
    desktop.scrollLeft = startLeft - (e.clientX - startX);
    desktop.scrollTop = startTop - (e.clientY - startY);
  });

  desktop.addEventListener("pointerup", (e) => {
    if (!panning) return;
    panning = false;
    desktop.classList.remove("panning");
    desktop.releasePointerCapture(e.pointerId);
  });

  desktop.addEventListener("auxclick", (e) => {
    if (e.button === 1) e.preventDefault();
  });
}

function tileFileWindows() {
  let index = 0;
  for (const path of fileStore.keys()) {
    openFile(path, { focus: index === 0, x: 36 + index * 34, y: 32 + index * 34 });
    index += 1;
  }
}

function loadWorkspaceFiles(fileEntries, top) {
  if (!fileEntries?.length) {
    appendConsole("[load] 読み込むファイルがありません", "warn");
    setStatus("No files loaded", "warn");
    return;
  }

  for (const [, view] of fileEditors) view.editor?.dispose();
  fileEditors.clear();
  editor = null;
  for (const [, entry] of fileStore) entry.model?.dispose();
  for (const [id, win] of mdiWindows) {
    if (id.startsWith("file:")) {
      win.remove();
      mdiWindows.delete(id);
    }
  }
  fileStore.clear();

  fileEntries.forEach(({ path, content }) => {
    fileStore.set(path, { content, model: null });
  });

  activeFile = fileEntries[0]?.path || "design.v";
  if (top != null) $("input-top").value = top;
  renderEditorTabs();
  renderFileTree();
  syncDeleteButton();
  if (window.monaco) tileFileWindows();
}

async function loadProjects() {
  const sel = $("select-project");
  if (!sel) return;
  try {
    const projects = await api("/api/projects");
    const selected = currentProject;
    sel.innerHTML = '<option value="">— workspace —</option>';
    projects.forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p.name;
      opt.textContent = `${p.label || p.name} (${p.file_count})`;
      sel.appendChild(opt);
    });
    if (selected && projects.some((p) => p.name === selected)) {
      sel.value = selected;
    }
  } catch {
    setStatus("Projects failed", "err");
  }
}

async function openProject(name) {
  if (!name) {
    currentProject = "";
    return;
  }
  setStatus("Loading project…", "busy");
  try {
    const data = await api(`/api/projects/${encodeURIComponent(name)}`);
    if (!data.files?.length) {
      appendConsole(`[project] ${data.name}: ファイルがありません`, "warn");
      setStatus("Empty project", "warn");
      return;
    }
    currentProject = data.name;
    $("select-example").value = "";
    loadWorkspaceFiles(data.files, data.top || "");
    $("select-project").value = data.name;
    appendConsole(`[project] opened: ${data.name} (${data.files.length} files)`, "info");
    setStatus(`Project: ${data.name}`, "ok");
    runElaborate();
  } catch (e) {
    appendConsole(String(e), "err");
    setStatus("Project load failed", "err");
  }
}

async function createProject() {
  const name = prompt("プロジェクト名 (英数字, _ -):", currentProject || "my_design");
  if (!name?.trim()) return;
  try {
    saveActiveEditor();
    const top = $("input-top").value.trim() || null;
    await api("/api/projects", { name: name.trim(), top });
    currentProject = name.trim();
    await loadProjects();
    $("select-project").value = currentProject;
    await saveCurrentProject(false);
    appendConsole(`[project] created: ${currentProject}`, "ok");
    setStatus(`Created: ${currentProject}`, "ok");
  } catch (e) {
    appendConsole(String(e), "err");
  }
}

async function saveCurrentProject(showPrompt = true) {
  let name = currentProject || $("select-project")?.value;
  if (!name && showPrompt) {
    name = prompt("保存先プロジェクト名:", "my_design");
    if (!name?.trim()) return;
    name = name.trim();
    try {
      await api("/api/projects", { name, top: $("input-top").value.trim() || null });
      currentProject = name;
      await loadProjects();
      $("select-project").value = name;
    } catch (e) {
      appendConsole(String(e), "err");
      return;
    }
  }
  if (!name) return;

  try {
    const payload = getPayload();
    const data = await api(
      `/api/projects/${encodeURIComponent(name)}`,
      { files: payload.files, top: payload.top, label: name },
      undefined,
      "PUT"
    );
    currentProject = data.name;
    await loadProjects();
    $("select-project").value = data.name;
    appendConsole(`[project] saved: ${data.name} (${data.files.length} files)`, "ok");
    setStatus(`Saved: ${data.name}`, "ok");
  } catch (e) {
    appendConsole(String(e), "err");
    setStatus("Save failed", "err");
  }
}

function currentProjectFileName() {
  const base = currentProject || $("input-top").value.trim() || "hdl_sim_project";
  return `${base.replace(/[^A-Za-z0-9_-]+/g, "_")}.spj`;
}

function buildSpjPayload() {
  const payload = getPayload();
  return {
    format: "hdl-sim-project",
    version: 1,
    name: currentProject || currentProjectFileName().replace(/\.spj$/i, ""),
    top: payload.top,
    until: payload.until,
    max_events: payload.max_events,
    files: payload.files,
  };
}

function applySpjData(data, filename) {
  if (data.format !== "hdl-sim-project" || !Array.isArray(data.files)) {
    throw new Error("HDL-Sim project fileではありません");
  }
  currentProject = data.name || String(filename || "").replace(/\.spj$/i, "");
  $("select-project").value = "";
  $("select-example").value = "";
  if (data.until != null) $("input-until").value = data.until;
  if (data.max_events != null) $("input-max-events").value = data.max_events;
  loadWorkspaceFiles(data.files, data.top || "");
}

async function loadSpjFileList(selectName) {
  const sel = $("select-spj");
  if (!sel) return;
  try {
    const info = await api("/api/spj/info");
    spjDirPath = info.path || spjDirPath;
    const keep = selectName || sel.value;
    sel.innerHTML = '<option value="">— .spj —</option>';
    for (const file of info.files || []) {
      const opt = document.createElement("option");
      opt.value = file.name;
      opt.textContent = file.label || file.name;
      sel.appendChild(opt);
    }
    if (keep && [...sel.options].some((o) => o.value === keep)) {
      sel.value = keep;
    }
  } catch (e) {
    appendConsole(String(e), "err");
  }
}

async function saveProjectFile() {
  try {
    const data = buildSpjPayload();
    const filename = currentProjectFileName();
    const saved = await api(
      `/api/spj/${encodeURIComponent(filename)}`,
      data,
      undefined,
      "PUT"
    );
    await loadSpjFileList(saved.filename);
    rememberRecentSpj(saved.filename);
    appendConsole(`[spj] saved: ${saved.path}`, "ok");
    setStatus(`Saved: ${saved.filename}`, "ok");
  } catch (e) {
    appendConsole(String(e), "err");
    setStatus("SPJ save failed", "err");
  }
}

function normalizeSpjFilename(name) {
  let cleaned = name.trim().replace(/\\/g, "/").split("/").pop() || "project.spj";
  if (!cleaned.toLowerCase().endsWith(".spj")) cleaned += ".spj";
  return cleaned.replace(/[^A-Za-z0-9_.-]/g, "_");
}

async function saveProjectFileAs() {
  const suggested = currentProjectFileName();
  const name = prompt("Save As (.spj):", suggested);
  if (!name?.trim()) return;
  try {
    const data = buildSpjPayload();
    const filename = normalizeSpjFilename(name);
    data.name = filename.replace(/\.spj$/i, "");
    const saved = await api(
      `/api/spj/${encodeURIComponent(filename)}`,
      data,
      undefined,
      "PUT"
    );
    await loadSpjFileList(saved.filename);
    rememberRecentSpj(saved.filename);
    appendConsole(`[spj] saved as: ${saved.path}`, "ok");
    setStatus(`Saved: ${saved.filename}`, "ok");
  } catch (e) {
    appendConsole(String(e), "err");
    setStatus("SPJ save failed", "err");
  }
}

function getRecentSpjFiles() {
  try {
    return JSON.parse(localStorage.getItem(RECENT_SPJ_KEY) || "[]");
  } catch {
    return [];
  }
}

function rememberRecentSpj(filename) {
  if (!filename) return;
  const list = getRecentSpjFiles().filter((name) => name !== filename);
  list.unshift(filename);
  localStorage.setItem(RECENT_SPJ_KEY, JSON.stringify(list.slice(0, RECENT_SPJ_MAX)));
  window.HDLSimMenuBar?.refresh();
}

function menuFileExit() {
  window.close();
  appendConsole("ブラウザタブを閉じて終了してください", "info");
}

function currentSpjFilename() {
  const selected = $("select-spj")?.value;
  if (selected) return selected;
  return currentProjectFileName();
}

function getActiveMonacoEditor() {
  if (editor) return editor;
  return fileEditors.get(activeFile)?.editor || null;
}

function triggerEditor(action) {
  const ed = getActiveMonacoEditor();
  if (!ed) {
    appendConsole("[edit] エディタにフォーカスがありません", "warn");
    return false;
  }
  ed.focus();
  ed.trigger("keyboard", action, null);
  return true;
}

function getEditMenuContext() {
  const ed = getActiveMonacoEditor();
  const noSelection = !ed || ed.getSelection()?.isEmpty();
  return {
    "edit.cut": noSelection,
    "edit.copy": noSelection,
    "edit.clear": noSelection,
    "edit.find-next": true,
  };
}

function applyViewState() {
  document.body.classList.toggle("view-hide-main-toolbar", !viewState.mainToolbar);
  document.body.classList.toggle("view-hide-output-panel", !viewState.outputPanel);
  document.body.classList.toggle("view-hide-project-bar", !viewState.projectBar);
  layoutAllEditors();
  if (lastWaveform && waveformVisible) drawWave(lastWaveform);
}

function toggleViewMenu(id) {
  if (id === "view.main-toolbar") viewState.mainToolbar = !viewState.mainToolbar;
  if (id === "view.output-panel") viewState.outputPanel = !viewState.outputPanel;
  if (id === "view.project-bar") viewState.projectBar = !viewState.projectBar;
  applyViewState();
  window.HDLSimMenuBar?.refresh();
}

function menuProjectClose() {
  currentProject = "";
  $("select-project").value = "";
  $("select-spj").value = "";
  appendConsole("[project] closed", "info");
  setStatus("Project closed", "ok");
}

async function menuProjectFiles() {
  const name = currentSpjFilename();
  try {
    const info = await api("/api/spj/info");
    if (info.files?.some((f) => f.name === name)) {
      await openSelectedSpjFile(name);
      return;
    }
    appendConsole(`[project] ${name} が ${spjDirPath} にありません`, "warn");
  } catch (e) {
    appendConsole(String(e), "err");
  }
}

function menuProjectSettings() {
  const top = prompt("Top module:", $("input-top").value.trim());
  if (top != null) $("input-top").value = top;
}

function getWindowFileList() {
  const list = [];
  for (const path of fileStore.keys()) {
    list.push({ path, label: path.includes("/") ? path.split("/").pop() : path });
  }
  const out = mdiWindows.get("output");
  if (out && !out.hidden) list.push({ path: "__output__", label: "Output" });
  const wave = mdiWindows.get("waveform");
  if (wave && !wave.hidden) list.push({ path: "__waveform__", label: "Waveform" });
  return list;
}

function windowCascade() {
  let i = 0;
  for (const [, win] of mdiWindows) {
    if (win.hidden) continue;
    win.style.left = `${36 + i * 28}px`;
    win.style.top = `${32 + i * 28}px`;
    i += 1;
  }
}

function windowTile() {
  const canvas = mdiCanvas();
  if (!canvas) return;
  const visible = [...mdiWindows.entries()].filter(([, w]) => !w.hidden);
  const n = visible.length;
  if (!n) return;
  const cols = Math.ceil(Math.sqrt(n));
  const pad = 8;
  const cellW = Math.max(280, Math.floor((canvas.clientWidth - pad * (cols + 1)) / cols));
  const cellH = Math.max(180, Math.floor((canvas.clientHeight - pad * 2) / Math.ceil(n / cols)));
  visible.forEach(([, win], index) => {
    const col = index % cols;
    const row = Math.floor(index / cols);
    win.style.left = `${pad + col * (cellW + pad)}px`;
    win.style.top = `${pad + row * (cellH + pad)}px`;
    win.style.width = `${cellW}px`;
    win.style.height = `${cellH}px`;
    win.querySelector(".mdi-body")?.firstElementChild?.dispatchEvent(new Event("resize"));
  });
  layoutAllEditors();
}

function windowOpenFile(path) {
  if (path === "__output__") {
    createOutputWindow();
    return;
  }
  if (path === "__waveform__") {
    toggleWaveform(true);
    return;
  }
  openFile(path);
}

function toggleDebugSingleStep() {
  debugSingleStep = !debugSingleStep;
  appendConsole(`[debug] Single step/breakpoints ${debugSingleStep ? "enabled" : "disabled"}`, "info");
  window.HDLSimMenuBar?.refresh();
}

async function debugRestart() {
  await runElaborate();
  await runSimulate();
}

function menuHelpGuide() {
  appendConsole(
    "[help] Run(F5) でシミュレーション / Save .spj で ./spj/ に保存 / 中クリック長押しでワークスペース移動",
    "info"
  );
}

async function menuHelpAbout() {
  try {
    const info = await api("/api/ui-info");
    alert(`HDL-Sim ${info.version}\nVerilog シミュレータ + Web IDE\n${info.spj_dir || ""}`);
  } catch {
    alert("HDL-Sim 0.4.2\nVerilog シミュレータ + Web IDE");
  }
}

function getMenuContext() {
  return {
    checked: {
      "view.main-toolbar": viewState.mainToolbar,
      "view.output-panel": viewState.outputPanel,
      "view.project-bar": viewState.projectBar,
      "debug.single-step": debugSingleStep,
    },
    disabled: {
      ...getEditMenuContext(),
      "debug.break": !simRunning,
      "debug.finish": true,
      "debug.restart": false,
      "debug.step": !debugSingleStep,
    },
    hints: {
      currentSpj: currentSpjFilename(),
    },
    recent: {
      fileRecent: getRecentSpjFiles(),
      projectRecent: getRecentSpjFiles(),
    },
    windowFiles: getWindowFileList(),
    activeWindow: activeFile,
  };
}

async function openSelectedSpjFile(name) {
  const filename = (name || $("select-spj")?.value || "").trim();
  if (!filename) {
    appendConsole(`[spj] 開くファイルを一覧から選んでください (${spjDirPath})`, "warn");
    return;
  }
  const data = await api(`/api/spj/${encodeURIComponent(filename)}`);
  applySpjData(data, filename);
  $("select-spj").value = filename;
  rememberRecentSpj(filename);
  appendConsole(`[spj] opened: ${filename} (${data.files.length} files)`, "ok");
  setStatus(`Opened: ${filename}`, "ok");
  runElaborate();
}

async function openProjectFilePicker() {
  try {
    await loadSpjFileList();
    const sel = $("select-spj");
    if (sel?.value) {
      await openSelectedSpjFile(sel.value);
      return;
    }
    const info = await api("/api/spj/info");
    if (!info.files?.length) {
      appendConsole(`[spj] ${spjDirPath} に .spj がありません`, "warn");
      return;
    }
    if (info.files.length === 1) {
      await openSelectedSpjFile(info.files[0].name);
      return;
    }
    appendConsole(`[spj] 一覧から .spj を選んで Open .spj を押してください`, "info");
  } catch (e) {
    appendConsole(String(e), "err");
    setStatus("SPJ open failed", "err");
  }
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
      layoutAllEditors();
      if (lastWaveform) drawWave(lastWaveform);
    },
  });

  splitH = Split(["#pane-explorer", "#pane-editor"], {
    direction: "horizontal",
    sizes: [SPLIT_SIZES.h.explorer, SPLIT_SIZES.h.editor],
    minSize: [140, 360],
    gutterSize: 4,
    snapOffset: 0,
    onDragEnd: (sizes) => {
      SPLIT_SIZES.h.explorer = sizes[0];
      SPLIT_SIZES.h.editor = sizes[1];
      layoutAllEditors();
      if (lastWaveform) drawWave(lastWaveform);
    },
  });
}

function toggleWaveform(show) {
  waveformVisible = show ?? !waveformVisible;
  const btn = $("btn-wave-toggle");

  if (waveformVisible) {
    createWaveformWindow();
    btn.classList.add("active");
    if (lastWaveform) drawWave(lastWaveform);
  } else {
    const win = mdiWindows.get("waveform");
    if (win) win.hidden = true;
    btn.classList.remove("active");
  }
  layoutAllEditors();
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

  const header = document.createElement("div");
  header.className = "tree-node";
  header.innerHTML = `<span class="twist">▼</span><span class="icon">📁</span><span class="label">WORKSPACE</span>`;
  root.appendChild(header);

  const body = document.createElement("div");
  body.className = "tree-children";
  renderFileTreeNode(body, buildFileTree(), 0);
  root.appendChild(body);
  syncDeleteButton();
}

function buildFileTree() {
  /** @type {Map<string, { dirs: Map<string, any>, files: string[] }>} */
  const root = { dirs: new Map(), files: [] };

  for (const path of fileStore.keys()) {
    const parts = path.split("/");
    let node = root;
    for (let i = 0; i < parts.length - 1; i++) {
      const dir = parts[i];
      if (!node.dirs.has(dir)) node.dirs.set(dir, { dirs: new Map(), files: [] });
      node = node.dirs.get(dir);
    }
    node.files.push(path);
  }
  return root;
}

function renderFileTreeNode(parentEl, node, depth) {
  const sortedDirs = [...node.dirs.keys()].sort();
  sortedDirs.forEach((dirName) => {
    const dirNode = node.dirs.get(dirName);
    const row = document.createElement("div");
    row.className = "tree-node";
    row.style.paddingLeft = `${depth * 12 + 4}px`;
    row.innerHTML = `<span class="twist">▼</span><span class="icon">📁</span><span class="label">${dirName}</span>`;
    parentEl.appendChild(row);

    const childWrap = document.createElement("div");
    childWrap.className = "tree-children";
    renderFileTreeNode(childWrap, dirNode, depth + 1);
    parentEl.appendChild(childWrap);

    const twist = row.querySelector(".twist");
    twist.addEventListener("click", (e) => {
      e.stopPropagation();
      const collapsed = childWrap.classList.toggle("collapsed");
      twist.textContent = collapsed ? "▶" : "▼";
    });
  });

  node.files.sort().forEach((path) => {
    const row = document.createElement("div");
    row.className = "tree-node" + (path === activeFile ? " selected" : "");
    row.style.paddingLeft = `${depth * 12 + 4}px`;
    const name = path.includes("/") ? path.split("/").pop() : path;
    row.innerHTML = `<span class="twist empty"></span><span class="icon">📄</span><span class="label">${name}</span>`;
    row.title = path;
    row.addEventListener("click", () => openFile(path));
    parentEl.appendChild(row);
  });
}

function getOrCreateModel(path, content) {
  const entry = fileStore.get(path);
  if (entry?.model) return entry.model;
  const uri = monaco.Uri.parse(`file:///${path}`);
  const model = monaco.editor.getModel(uri) || monaco.editor.createModel(content, "verilog", uri);
  if (entry) entry.model = model;
  return model;
}

function layoutAllEditors() {
  for (const [, view] of fileEditors) view.editor?.layout();
}

function fileWindowId(path) {
  return `file:${path}`;
}

function openFile(path, options = {}) {
  if (!fileStore.has(path)) return;
  saveActiveEditor();
  activeFile = path;
  const entry = fileStore.get(path);
  const id = fileWindowId(path);
  const index = [...fileStore.keys()].indexOf(path);
  const win = createMdiWindow(id, path, {
    x: options.x ?? 40 + Math.max(index, 0) * 28,
    y: options.y ?? 38 + Math.max(index, 0) * 28,
    width: 560,
    height: 390,
    bodyClass: "mdi-editor",
  });
  win.hidden = false;

  let view = fileEditors.get(path);
  if (!view) {
    const body = win.querySelector(".mdi-body");
    const model = getOrCreateModel(path, entry.content);
    const ed = monaco.editor.create(body, {
      model,
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
    ed.onDidFocusEditorText(() => {
      activeFile = path;
      editor = ed;
      renderEditorTabs();
      renderFileTree();
      bringMdiToFront(win);
    });
    view = { editor: ed, window: win };
    fileEditors.set(path, view);
  }
  editor = view.editor;
  bringMdiToFront(win);
  view.editor.layout();
  renderEditorTabs();
  renderFileTree();
}

function addFile(name) {
  let path = name || prompt("ファイル名 (例: dut.v または lib/and2.v):", "dut.v");
  if (!path) return;
  path = path.trim().replace(/\\/g, "/");
  if (!path.endsWith(".v") && !path.endsWith(".sv")) path += ".v";
  putFileContent(path, `// ${path}\n`);
  openFile(path);
  switchExplorerTab("files");
}

function putFileContent(path, content) {
  const existing = fileStore.get(path);
  if (existing?.model) {
    existing.model.dispose();
  }
  fileStore.set(path, { content, model: null });
}

function readFileAsText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error || new Error(`read failed: ${file.name}`));
    reader.readAsText(file);
  });
}

async function importLocalFiles(fileList) {
  if (!fileList?.length) return;

  const files = Array.from(fileList);
  const loaded = [];

  for (const file of files) {
    const path = file.name.replace(/\\/g, "/");
    try {
      const content = await readFileAsText(file);
      putFileContent(path, content);
      loaded.push(path);
    } catch (err) {
      appendConsole(`Failed to read ${path}: ${err}`, "err");
    }
  }

  if (!loaded.length) return;

  loaded.forEach((path, index) => openFile(path, { focus: index === loaded.length - 1 }));
  switchExplorerTab("files");
  renderEditorTabs();
  renderFileTree();
  appendConsole(`[open] ${loaded.join(", ")}`, "info");
  setStatus(`${loaded.length} file(s) opened`, "ok");
}

function openFilePicker() {
  $("file-import-input")?.click();
}

function deleteFile(path, { confirmDelete = true } = {}) {
  const target = path || activeFile;
  if (fileStore.size <= 1) return;
  if (!fileStore.has(target)) return;
  if (confirmDelete && !window.confirm(`「${target}」を削除しますか？`)) return;

  const entry = fileStore.get(target);
  const view = fileEditors.get(target);
  if (editor === view?.editor) editor = null;
  if (view?.editor) view.editor.dispose();
  fileEditors.delete(target);
  const win = mdiWindows.get(fileWindowId(target));
  if (win) {
    win.remove();
    mdiWindows.delete(fileWindowId(target));
  }
  if (entry?.model) {
    entry.content = entry.model.getValue();
    entry.model.dispose();
  }
  fileStore.delete(target);

  if (activeFile === target) {
    activeFile = fileStore.keys().next().value;
    openFile(activeFile);
  } else {
    renderEditorTabs();
    renderFileTree();
  }
  syncDeleteButton();
}

function closeFile(path) {
  deleteFile(path, { confirmDelete: false });
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

function createOutputWindow() {
  const win = createMdiWindow("output", "Output", {
    x: 70,
    y: 330,
    width: 640,
    height: 250,
    bodyClass: "mdi-output",
  });
  const body = win.querySelector(".mdi-body");
  if (!body.id) {
    body.id = "mdi-console-output";
    body.classList.add("console-output");
  }
  win.hidden = false;
  bringMdiToFront(win);
  return win;
}

function createWaveformWindow() {
  const win = createMdiWindow("waveform", "Waveform", {
    x: 760,
    y: 80,
    width: 720,
    height: 360,
    bodyClass: "mdi-waveform",
  });
  const body = win.querySelector(".mdi-body");
  if (!body.querySelector("#waveform-canvas")) {
    body.innerHTML = `
      <div class="wave-toolbar">
        <button type="button" id="btn-wave-zoom-out" class="mini-btn" title="時間軸を縮小">−</button>
        <button type="button" id="btn-wave-zoom-in" class="mini-btn" title="時間軸を拡大">＋</button>
        <button type="button" id="btn-wave-fit" class="mini-btn" title="全体表示に戻す">Fit</button>
        <label class="check"><input type="checkbox" id="chk-auto-scroll" checked /> Auto-scroll</label>
      </div>
      <div id="waveform-wrap" class="waveform-wrap">
        <canvas id="waveform-canvas"></canvas>
      </div>
    `;
    body.querySelector("#btn-wave-fit")?.addEventListener("click", fitWaveform);
    body.querySelector("#btn-wave-zoom-in")?.addEventListener("click", () => setWaveZoom(waveZoom * 1.5));
    body.querySelector("#btn-wave-zoom-out")?.addEventListener("click", () => setWaveZoom(waveZoom / 1.5));
    body.querySelector("#chk-auto-scroll")?.addEventListener("change", () => {
      if (lastWaveform) drawWave(lastWaveform);
    });
    if (window.ResizeObserver) {
      const observer = new ResizeObserver(() => {
        if (!win.hidden && lastWaveform) drawWave(lastWaveform);
      });
      observer.observe(body);
    }
  }
  win.hidden = false;
  waveformVisible = true;
  bringMdiToFront(win);
  return win;
}

function drawWave(waveform) {
  if (!waveform || !window.HDLSimWaveform?.drawWaveform) return;
  createWaveformWindow();
  const canvas = $("waveform-canvas");
  window.HDLSimWaveform.drawWaveform(canvas, waveform, {
    wrap: $("waveform-wrap"),
    autoScroll: $("chk-auto-scroll")?.checked,
    zoom: waveZoom,
  });
}

function fitWaveform() {
  waveZoom = 1;
  const wrap = $("waveform-wrap");
  if (wrap) wrap.scrollLeft = 0;
  drawWave(lastWaveform);
}

function setWaveZoom(nextZoom) {
  waveZoom = Math.min(32, Math.max(1, nextZoom));
  const auto = $("chk-auto-scroll");
  if (auto) auto.checked = false;
  drawWave(lastWaveform);
}

/* ── API ── */

async function api(path, body, signal, method) {
  const init = { signal };
  if (body !== undefined && body !== null) {
    init.method = method || "POST";
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  } else {
    init.method = method || "GET";
  }
  const res = await fetch(path, init);
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) {
    const detail = data?.detail ?? data?.error ?? `HTTP ${res.status}`;
    const message = typeof detail === "string" ? detail : JSON.stringify(detail);
    const err = new Error(message);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

function setRunning(running) {
  simRunning = running;
  $("btn-run").disabled = running;
  $("btn-stop").disabled = !running;
  $("btn-elab").disabled = running;
  $("btn-step").disabled = running;
  window.HDLSimMenuBar?.refresh();
}

async function loadExamples() {
  const sel = $("select-example");
  try {
    const items = await api("/api/examples");
    sel.innerHTML = '<option value="">— プロジェクト / 例 —</option>';

    const projects = items.filter((ex) => ex.kind === "project");
    const singles = items.filter((ex) => ex.kind !== "project");

    if (projects.length) {
      const grp = document.createElement("optgroup");
      grp.label = "Projects (複数ファイル)";
      projects.forEach((ex) => {
        const opt = document.createElement("option");
        opt.value = ex.id;
        opt.textContent = ex.label;
        grp.appendChild(opt);
      });
      sel.appendChild(grp);
    }

    if (singles.length) {
      const grp = document.createElement("optgroup");
      grp.label = "Single file";
      singles.forEach((ex) => {
        const opt = document.createElement("option");
        opt.value = ex.id;
        opt.textContent = ex.label;
        grp.appendChild(opt);
      });
      sel.appendChild(grp);
    }
  } catch {
    setStatus("Examples failed", "err");
  }
}

async function openExample(id) {
  if (!id) return;
  setStatus("Loading…", "busy");
  try {
    const data = await api(`/api/examples/${encodeURIComponent(id)}`);
    const files = data.files?.length
      ? data.files
      : [{ path: id.includes("/") ? id.split("/").pop() : id, content: data.content }];

    currentProject = "";
    $("select-project").value = "";
    loadWorkspaceFiles(files, data.top || "");
    const label = data.label || id;
    setStatus(`Loaded: ${label} (${files.length} files)`, "ok");
    appendConsole(`[example] ${label}`, "info");
    appendConsole(`[load] ${files.map((f) => f.path).join(", ")}`, "info");
    runElaborate();
  } catch (e) {
    appendConsole(String(e), "err");
    setStatus("Example load failed", "err");
  } finally {
    $("select-example").value = "";
  }
}

async function runElaborate() {
  setStatus("Elaborating…", "busy");
  createOutputWindow();
  try {
    const payload = getPayload();
    appendConsole(`[elab] ${payload.files.length} file(s): ${payload.files.map((f) => f.path).join(", ")}`, "info");
    const data = await api("/api/elaborate", payload);
    if (!data.ok) {
      appendConsole(data.error, "err");
      if (data.trace) appendConsole(data.trace, "err");
      renderHierarchy(null);
      renderSignalList([]);
      setStatus("Elab error", "err");
      switchExplorerTab("hierarchy");
      return;
    }
    renderHierarchy(data.hierarchy);
    updateTopModuleList(data.module_names || data.overview?.module_names, data.top);
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
  createOutputWindow();
  clearConsole();
  abortController = new AbortController();

  try {
    const payload = getPayload();
    const topLabel = payload.top || "(auto)";
    appendConsole(`[run] ${payload.files.length} file(s): ${payload.files.map((f) => f.path).join(", ")}`, "info");
    appendConsole(`[run] top=${topLabel}`, "info");

    const data = await api("/api/simulate", payload, abortController.signal);
    if (!data.ok) {
      appendConsole(data.error, "err");
      if (data.trace) appendConsole(data.trace, "err");
      if (data.console) appendConsole(data.console);
      renderHierarchy(null);
      renderSignalList([]);
      setStatus("Sim failed", "err");
      return;
    }
    if (data.console) appendConsole(data.console);
    appendConsole(`time=${data.stop_time} events=${data.events_processed} top=${data.top_module}`, "ok");
    updateTopModuleList(data.module_names || data.overview?.module_names, data.top_module);
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

    tileFileWindows();
    renderEditorTabs();
    renderFileTree();
    renderHierarchy(null);
    loadExamples();
    loadProjects();
    verifyUiBuild();
  });
}

function bindUi() {
  $("btn-run").addEventListener("click", runSimulate);
  $("btn-stop").addEventListener("click", stopSimulation);
  $("btn-step").addEventListener("click", runStep);
  $("btn-elab").addEventListener("click", runElaborate);
  $("btn-clear-console").addEventListener("click", clearConsole);
  $("btn-wave-toggle").addEventListener("click", () => toggleWaveform());
  $("btn-wave-close")?.addEventListener("click", () => toggleWaveform(false));
  $("btn-wave-fit")?.addEventListener("click", fitWaveform);
  $("btn-open-files").addEventListener("click", () => openFilePicker());
  $("btn-new-file").addEventListener("click", () => addFile());
  $("btn-delete-file").addEventListener("click", () => deleteFile());
  $("file-import-input")?.addEventListener("change", (e) => {
    importLocalFiles(e.target.files);
    e.target.value = "";
  });
  $("select-example").addEventListener("change", (e) => openExample(e.target.value));
  $("select-project")?.addEventListener("change", (e) => openProject(e.target.value));
  $("btn-new-project")?.addEventListener("click", () => createProject());
  $("btn-save-project")?.addEventListener("click", () => saveCurrentProject());
  $("btn-open-spj")?.addEventListener("click", openProjectFilePicker);
  $("btn-save-spj")?.addEventListener("click", saveProjectFile);
  $("select-spj")?.addEventListener("change", (e) => {
    if (e.target.value) openSelectedSpjFile(e.target.value);
  });

  document.querySelectorAll(".pane-tab").forEach((tab) => {
    tab.addEventListener("click", () => switchExplorerTab(tab.dataset.pane));
  });

  window.addEventListener("resize", () => {
    layoutAllEditors();
    if (lastWaveform && waveformVisible) drawWave(lastWaveform);
  });

  document.addEventListener("keydown", (e) => {
    if (handleMenuShortcut(e)) return;
  });

  $("chk-auto-scroll")?.addEventListener("change", () => {
    if (lastWaveform) drawWave(lastWaveform);
  });

  initMenuBar();
}

function initMenuBar() {
  window.HDLSimMenuBar?.init({
    getMenuContext,
    actions: {
      "file.new": () => createProject(),
      "file.open": () => openProjectFilePicker(),
      "file.save": () => saveProjectFile(),
      "file.save-as": () => saveProjectFileAs(),
      "file.recent": (filename) => openSelectedSpjFile(filename),
      "file.exit": () => menuFileExit(),
      "edit.undo": () => triggerEditor("undo"),
      "edit.cut": () => triggerEditor("editor.action.clipboardCutAction"),
      "edit.copy": () => triggerEditor("editor.action.clipboardCopyAction"),
      "edit.paste": () => triggerEditor("editor.action.clipboardPasteAction"),
      "edit.clear": () => {
        const ed = getActiveMonacoEditor();
        if (!ed || ed.getSelection()?.isEmpty()) return;
        ed.executeEdits("clear", [{ range: ed.getSelection(), text: "", forceMoveMarkers: true }]);
      },
      "edit.select-all": () => triggerEditor("editor.action.selectAll"),
      "edit.find": () => triggerEditor("actions.find"),
      "edit.find-next": () => triggerEditor("editor.action.nextMatchFindAction"),
      "edit.replace": () => triggerEditor("editor.action.startFindReplaceAction"),
      "edit.goto-line": () => triggerEditor("editor.action.gotoLine"),
      "view.main-toolbar": () => toggleViewMenu("view.main-toolbar"),
      "view.output-panel": () => toggleViewMenu("view.output-panel"),
      "view.project-bar": () => toggleViewMenu("view.project-bar"),
      "project.new": () => createProject(),
      "project.open": () => openProjectFilePicker(),
      "project.files": () => menuProjectFiles(),
      "project.save-as": () => saveProjectFileAs(),
      "project.close": () => menuProjectClose(),
      "project.reload-files": () => runElaborate(),
      "project.settings": () => menuProjectSettings(),
      "project.recent": (filename) => openSelectedSpjFile(filename),
      "debug.single-step": () => toggleDebugSingleStep(),
      "debug.go": () => runSimulate(),
      "debug.break": () => stopSimulation(),
      "debug.restart": () => debugRestart(),
      "debug.step": () => runStep(),
      "window.cascade": () => windowCascade(),
      "window.tile": () => windowTile(),
      "window.waveform": () => toggleWaveform(true),
      "window.open-file": (path) => windowOpenFile(path),
      "help.guide": () => menuHelpGuide(),
      "help.about": () => menuHelpAbout(),
    },
  });
  applyViewState();
}

function handleMenuShortcut(e) {
  const tag = e.target?.tagName;
  const inField = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";

  if (e.key === "F5" && !e.shiftKey && !e.altKey) {
    if (inField) return false;
    e.preventDefault();
    runSimulate();
    return true;
  }
  if (e.key === "F5" && e.shiftKey) {
    if (inField) return false;
    e.preventDefault();
    debugRestart();
    return true;
  }
  if (e.key === "F6") {
    if (inField) return false;
    e.preventDefault();
    toggleWaveform(true);
    return true;
  }
  if (e.key === "F10") {
    if (inField) return false;
    e.preventDefault();
    runStep();
    return true;
  }
  if (e.key === "Escape") {
    if (inField) return false;
    stopSimulation();
    window.HDLSimMenuBar?.close();
    return true;
  }
  if (e.altKey && e.key === "F5") {
    e.preventDefault();
    runElaborate().then(() => runSimulate());
    return true;
  }
  if (!(e.ctrlKey || e.metaKey)) return false;
  if (inField) return false;

  const key = e.key.toLowerCase();
  const map = {
    n: () => createProject(),
    o: () => openProjectFilePicker(),
    s: () => saveProjectFile(),
    z: () => triggerEditor("undo"),
    x: () => triggerEditor("editor.action.clipboardCutAction"),
    c: () => triggerEditor("editor.action.clipboardCopyAction"),
    v: () => triggerEditor("editor.action.clipboardPasteAction"),
    a: () => triggerEditor("editor.action.selectAll"),
    f: () => triggerEditor("actions.find"),
    h: () => triggerEditor("editor.action.startFindReplaceAction"),
    g: () => triggerEditor("editor.action.gotoLine"),
    l: () => runElaborate(),
  };
  if (map[key]) {
    e.preventDefault();
    map[key]();
    return true;
  }
  return false;
}

async function verifyUiBuild() {
  const badge = $("app-version");
  try {
    const info = await api("/api/ui-info");
    if (info.version_label && badge) {
      badge.textContent = info.version_label;
      badge.title = `HDL-Sim UI ${info.version}${info.ide_layout ? " (IDE)" : ""}`;
    }
    if (!info.ide_layout) {
      setStatus("旧UI — サーバー再起動", "err");
      appendConsole(
        `[ui] IDE layout not detected. ui_dir=${info.ui_dir}`,
        "warn"
      );
      return;
    }
    if (info.spj_dir) {
      spjDirPath = info.spj_dir;
      appendConsole(`[spj] folder: ${spjDirPath}`, "info");
    }
    await loadSpjFileList();
    setStatus("Ready", "ok");
  } catch {
    /* keep static badge */
  }
}

initFiles();
initSplits();
bindUi();
initMdiPan();
initMonaco();
