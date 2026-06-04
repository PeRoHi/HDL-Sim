/**
 * HDL-Sim IDE-style web UI
 */

import { createWorkspaceTree, scanModulesInWorkspace } from "./workspace-tree.js";
import { createWaveSignalPanel } from "./wave-signal-panel.js";

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
let lastWaveformFull = null;
let lastTopModule = "";
/** @type {Set<string> | null} */
let lastSignalNames = null;
/** @type {string[]} */
let waveformSelection = [];
/** @type {string[]} 波形ビューでの表示順 */
let waveformDisplayOrder = [];
let selectedSignal = null;
/** @type {ReturnType<typeof createWaveSignalPanel> | null} */
let waveSignalPanel = null;
let waveformVisible = false;
let waveZoom = 1;
let abortController = null;

/** @type {Split.Instance | null} */
let splitH = null;
/** @type {Split.Instance | null} */
let splitV = null;

const SPLIT_SIZES = {
  h: { explorer: 18, editor: 82, wave: 0 },
  v: { main: 65, console: 35 },
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

/** @type {ReturnType<typeof createWorkspaceTree> | null} */
let workspaceTree = null;

const UI_VERSION_KEY = "hdl-sim-ui-version";
const DISMISS_UPDATE_KEY = "hdl-sim-dismiss-update";

function initFiles() {
  fileStore.set("design.v", { content: DEFAULT_SOURCE, model: null });
}

function setStatus(text, kind = "") {
  const bar = $("status-bar");
  bar.textContent = text;
  bar.className = "status-pill" + (kind ? ` ${kind}` : "");
}

let lastConsoleErrorText = "";
let consoleBuffer = "";

function isConsoleElement(el) {
  return el?.classList?.contains("console-output") || el?.id === "console-output";
}

function getConsoleElements() {
  return [$("console-output"), $("mdi-console-output")].filter(Boolean);
}

function getConsolePlainText() {
  const el = $("console-output");
  if (!el) return consoleBuffer;
  if (el.tagName === "TEXTAREA") return el.value;
  return consoleBuffer;
}

function syncConsoleViews() {
  getConsoleElements().forEach((el) => {
    if (el.tagName === "TEXTAREA") {
      el.value = consoleBuffer;
      el.scrollTop = el.scrollHeight;
    }
  });
}

function focusConsole(selectAll = false) {
  const el = $("console-output");
  if (!el || el.tagName !== "TEXTAREA") return;
  el.focus();
  if (selectAll) {
    el.select();
  }
}

function initConsoleKeyboard() {
  getConsoleElements().forEach((el) => {
    if (el.tagName !== "TEXTAREA") return;
    el.addEventListener("focus", () => {
      el.scrollTop = el.scrollHeight;
    });
  });
  $("pane-console")?.addEventListener("mousedown", (e) => {
    if (e.target.closest(".pane-header-bar button")) return;
    focusConsole(false);
  });
}

async function copyConsoleText({ errorsOnly = false } = {}) {
  const text = errorsOnly
    ? lastConsoleErrorText || getConsolePlainText()
    : getConsolePlainText();
  if (!text) {
    appendConsole("[console] コピーする内容がありません", "warn");
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    appendConsole(errorsOnly ? "[console] エラー内容をクリップボードにコピーしました" : "[console] 出力をコピーしました", "info");
  } catch {
    const area = document.createElement("textarea");
    area.value = text;
    area.style.position = "fixed";
    area.style.left = "-9999px";
    document.body.appendChild(area);
    area.select();
    try {
      document.execCommand("copy");
      appendConsole(errorsOnly ? "[console] エラー内容をコピーしました" : "[console] 出力をコピーしました", "info");
    } catch (err) {
      appendConsole(`[console] コピーに失敗: ${err}`, "err");
    }
    area.remove();
  }
}

function appendConsole(text, kind = "") {
  if (text == null || text === "") return;
  if (kind === "err") {
    lastConsoleErrorText = String(text);
  }

  const prefix =
    kind === "err" ? "[ERROR] " :
    kind === "ok" ? "[OK] " :
    kind === "warn" ? "[WARN] " :
    kind === "info" ? "" : "";

  const lines = String(text).replace(/\r\n/g, "\n").split("\n");
  lines.forEach((line, index) => {
    if (line === "" && index === lines.length - 1) return;
    consoleBuffer += (index === 0 ? prefix : "") + line + "\n";
  });
  syncConsoleViews();
  if (kind === "err") {
    ensureConsoleVisible();
    focusConsole(false);
  }
}

function clearConsole() {
  consoleBuffer = "";
  lastConsoleErrorText = "";
  syncConsoleViews();
}

function saveActiveEditor() {
  for (const [, entry] of fileStore) {
    if (entry.model) entry.content = entry.model.getValue();
  }
}

function getSelectedTop() {
  return $("select-top")?.value.trim() || "";
}

function guessTopModuleName(modules) {
  if (!modules?.length) return "";
  const pick =
    modules.find((m) => m.name.endsWith("_tp")) ||
    modules.find((m) => m.name.endsWith("_tb") || m.name.startsWith("tb_")) ||
    modules.find((m) => m.name === "tb") ||
    modules.find((m) => m.name === "stimulus") ||
    modules[0];
  return pick?.name || "";
}

/** Top sent to API: drop stale names (e.g. tb) not in workspace modules. */
function effectiveTopForPayload() {
  const selected = getSelectedTop();
  const modules = scanModulesInWorkspace(fileStore, saveActiveEditor);
  const has = (name) => modules.some((m) => m.name === name);
  if (selected && has(selected)) return selected;
  const guessed = guessTopModuleName(modules);
  return guessed || null;
}

function syncTopPickerToModules() {
  const sel = $("select-top");
  if (!sel) return;
  const selected = getSelectedTop();
  const modules = scanModulesInWorkspace(fileStore, saveActiveEditor);
  const has = (name) => modules.some((m) => m.name === name);
  if (selected && !has(selected)) {
    const guessed = guessTopModuleName(modules);
    if (guessed) sel.value = guessed;
    else sel.value = "";
  }
}

function getPayload() {
  saveActiveEditor();
  const top = effectiveTopForPayload();
  const files = [];
  for (const [path, entry] of fileStore) {
    const item = { path, content: entry.content };
    if (entry.includeOnly) item.include_only = true;
    files.push(item);
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

function refreshTopModulePicker(suggestedTop) {
  const sel = $("select-top");
  if (!sel) return;
  const current = sel.value;
  const modules = scanModulesInWorkspace(fileStore, saveActiveEditor);
  sel.innerHTML = '<option value="">(auto — *_tp 優先)</option>';
  modules.forEach(({ name, path }) => {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = `${name}  —  ${path}`;
    sel.appendChild(opt);
  });
  const has = (name) => modules.some((m) => m.name === name);
  if (current && has(current)) sel.value = current;
  else if (suggestedTop && has(suggestedTop)) sel.value = suggestedTop;
  else {
    const guessed = guessTopModuleName(modules);
    if (guessed) sel.value = guessed;
  }
}

function scheduleTopModuleRefresh() {
  refreshTopModulePicker();
  syncTopPickerToModules();
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

function showMdiWindow(win) {
  if (!win) return;
  win.hidden = false;
  win.style.removeProperty("display");
  bringMdiToFront(win);
}

function hideMdiWindow(win) {
  if (!win) return;
  win.hidden = true;
}

function minimizeMdiWindow(win) {
  if (!win) return;
  win.classList.add("mdi-minimized");
  win.dataset.mdiMaximized = "0";
}

function restoreMdiWindow(win) {
  if (!win) return;
  win.classList.remove("mdi-minimized");
  if (win.dataset.mdiMaximized === "1") {
    delete win.dataset.mdiMaximized;
    win.style.left = win.dataset.mdiPrevLeft || win.style.left;
    win.style.top = win.dataset.mdiPrevTop || win.style.top;
    win.style.width = win.dataset.mdiPrevWidth || win.style.width;
    win.style.height = win.dataset.mdiPrevHeight || win.style.height;
  }
  showMdiWindow(win);
}

function toggleMaximizeMdiWindow(win) {
  if (!win) return;
  const canvas = mdiCanvas();
  if (win.dataset.mdiMaximized === "1") {
    restoreMdiWindow(win);
    return;
  }
  win.dataset.mdiPrevLeft = win.style.left;
  win.dataset.mdiPrevTop = win.style.top;
  win.dataset.mdiPrevWidth = win.style.width;
  win.dataset.mdiPrevHeight = win.style.height;
  win.classList.remove("mdi-minimized");
  win.style.left = "8px";
  win.style.top = "8px";
  win.style.width = `${Math.max(260, canvas.clientWidth - 16)}px`;
  win.style.height = `${Math.max(160, canvas.clientHeight - 16)}px`;
  win.dataset.mdiMaximized = "1";
  showMdiWindow(win);
  layoutAllEditors();
  if (win.dataset.mdiId === "waveform" && lastWaveform) drawWave(lastWaveform);
}

function closeMdiWindow(id, win) {
  if (id === "waveform") {
    toggleWaveform(false);
    return;
  }
  hideMdiWindow(win);
}

function attachMdiTitlebar(win, id, titlebar) {
  let dragging = false;
  let startX = 0;
  let startY = 0;
  let startLeft = 0;
  let startTop = 0;

  titlebar.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    if (e.target.closest(".mdi-controls")) return;
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
    if (!dragging) return;
    dragging = false;
    try {
      titlebar.releasePointerCapture(e.pointerId);
    } catch {
      /* already released */
    }
  });
  titlebar.addEventListener("dblclick", (e) => {
    if (e.target.closest(".mdi-controls")) return;
    toggleMaximizeMdiWindow(win);
  });
}

function createMdiWindow(id, title, { x = 40, y = 40, width = 520, height = 360, bodyClass = "", show = true } = {}) {
  const existing = mdiWindows.get(id);
  if (existing) {
    if (show) showMdiWindow(existing);
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

  const btnMin = document.createElement("button");
  btnMin.type = "button";
  btnMin.className = "mdi-btn min";
  btnMin.title = "最小化";
  btnMin.setAttribute("aria-label", "最小化");
  btnMin.textContent = "─";

  const btnRestore = document.createElement("button");
  btnRestore.type = "button";
  btnRestore.className = "mdi-btn restore";
  btnRestore.title = "ウィンドウを表示 / 最大化";
  btnRestore.setAttribute("aria-label", "ウィンドウ表示");
  btnRestore.textContent = "□";

  const btnClose = document.createElement("button");
  btnClose.type = "button";
  btnClose.className = "mdi-btn close";
  btnClose.title = "ウィンドウを閉じる（ファイルはワークスペースに残す）";
  btnClose.setAttribute("aria-label", "閉じる");
  btnClose.textContent = "×";

  const stopCtl = (e) => {
    e.stopPropagation();
    e.preventDefault();
  };

  btnMin.addEventListener("pointerdown", stopCtl);
  btnMin.addEventListener("click", (e) => {
    stopCtl(e);
    minimizeMdiWindow(win);
  });

  btnRestore.addEventListener("pointerdown", stopCtl);
  btnRestore.addEventListener("click", (e) => {
    stopCtl(e);
    if (win.hidden || win.classList.contains("mdi-minimized")) {
      restoreMdiWindow(win);
      return;
    }
    toggleMaximizeMdiWindow(win);
  });

  btnClose.addEventListener("pointerdown", stopCtl);
  btnClose.addEventListener("click", (e) => {
    stopCtl(e);
    closeMdiWindow(id, win);
  });

  controls.append(btnMin, btnRestore, btnClose);
  titlebar.appendChild(controls);

  const body = document.createElement("div");
  body.className = `mdi-body ${bodyClass}`.trim();

  win.appendChild(titlebar);
  win.appendChild(body);
  mdiCanvas().appendChild(win);
  mdiWindows.set(id, win);
  attachMdiTitlebar(win, id, titlebar);
  win.addEventListener("pointerdown", () => bringMdiToFront(win));

  if (show) showMdiWindow(win);
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

  fileEntries.forEach(({ path, content, include_only }) => {
    fileStore.set(path, { content, model: null, includeOnly: Boolean(include_only) });
  });

  activeFile = fileEntries[0]?.path || "design.v";
  renderEditorTabs();
  workspaceTree?.render();
  refreshTopModulePicker(top || undefined);
  syncTopPickerToModules();
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
    const top = getSelectedTop() || null;
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
      await api("/api/projects", { name, top: getSelectedTop() || null });
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
  const base = currentProject || getSelectedTop() || "hdl_sim_project";
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
  const top = prompt("Top module:", getSelectedTop());
  if (top != null && $("select-top")) $("select-top").value = top;
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
    [
      "[help] Top: (auto) または *_tp / *_tb モジュールを選択（古い tb は自動補正）",
      "[help] Elab → Run(F5) → Hierarchy/Signals クリックで波形 / Wave の All で全信号",
      "[help] Until: 長い TB では 15000 以上推奨 / Save .spj → ./spj/",
      "[help] 詳細: リポジトリ docs/LOCAL_DEBUG_HANDOFF.md",
    ].join("\n"),
    "info",
  );
  switchExplorerTab("hierarchy");
}

async function menuHelpAbout() {
  try {
    const info = await api("/api/ui-info");
    alert(`HDL-Sim ${info.version}\nVerilog シミュレータ + Web IDE\n${info.spj_dir || ""}`);
  } catch {
    alert("HDL-Sim 0.5.20\nVerilog シミュレータ + Web IDE");
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
    minSize: [160, 120],
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
    btn?.classList.add("active");
    if (lastWaveform) drawWave(lastWaveform);
  } else {
    const win = mdiWindows.get("waveform");
    if (win) hideMdiWindow(win);
    btn?.classList.remove("active");
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
  $("view-wave")?.classList.toggle("active", name === "wave");
  if ($("view-wave")) $("view-wave").hidden = name !== "wave";
  if (name === "wave") waveSignalPanel?.render();
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
  workspaceTree?.render();
}

function initWorkspaceTreeView() {
  workspaceTree = createWorkspaceTree({
    fileStore,
    getRootElement: () => $("file-tree"),
    getActiveFile: () => activeFile,
    onOpenFile: (path) => openFile(path),
    onDeleteFile: (path) => deleteFile(path),
    onNewFile: (folder) => addFileInFolder(folder),
    onNewFolder: (parent) => createFolder(parent),
    onRenameFile: (path) => renameFilePrompt(path),
    onRenameFolder: (path) => renameFolderPrompt(path),
    onDeleteFolder: (path) => deleteFolder(path),
    onMovePath: (from, to) => moveFilePath(from, to),
    onAfterRender: () => syncDeleteButton(),
  });
  workspaceTree.render();
}

function renameFilePath(oldPath, newPath) {
  oldPath = oldPath.replace(/\\/g, "/");
  newPath = newPath.replace(/\\/g, "/");
  if (oldPath === newPath || !fileStore.has(oldPath) || fileStore.has(newPath)) return false;

  const entry = fileStore.get(oldPath);
  const view = fileEditors.get(oldPath);
  const oldWinId = fileWindowId(oldPath);
  const win = mdiWindows.get(oldWinId);

  fileStore.delete(oldPath);
  fileStore.set(newPath, entry);

  if (view) {
    fileEditors.delete(oldPath);
    fileEditors.set(newPath, view);
  }
  if (win) {
    mdiWindows.delete(oldWinId);
    win.dataset.mdiId = fileWindowId(newPath);
    const title = win.querySelector(".mdi-title");
    if (title) title.textContent = newPath;
    mdiWindows.set(fileWindowId(newPath), win);
  }
  if (entry?.model) {
    const uri = monaco.Uri.parse(`file:///${newPath}`);
    monaco.editor.setModelLanguage(entry.model, "verilog");
    // keep same model, update uri by recreating if needed
  }
  if (activeFile === oldPath) activeFile = newPath;
  renderEditorTabs();
  workspaceTree?.render();
  refreshTopModulePicker();
  return true;
}

function moveFilePath(from, to) {
  if (renameFilePath(from, to)) {
    appendConsole(`[files] moved: ${from} → ${to}`, "info");
    return true;
  }
  appendConsole(`[files] move failed: ${from} → ${to}`, "warn");
  return false;
}

function renameFilePrompt(path) {
  const base = path.includes("/") ? path.split("/").pop() : path;
  const next = prompt("新しいファイル名:", base);
  if (!next?.trim()) return;
  let fileName = next.trim().replace(/\\/g, "/");
  if (!fileName.endsWith(".v") && !fileName.endsWith(".sv")) fileName += ".v";
  fileName = fileName.split("/").pop();
  const folder = path.includes("/") ? path.split("/").slice(0, -1).join("/") : "";
  const dest = folder ? `${folder}/${fileName}` : fileName;
  if (moveFilePath(path, dest)) runElaborate();
}

function renameFolderPrompt(folderPath) {
  const name = folderPath.includes("/") ? folderPath.split("/").pop() : folderPath;
  const next = prompt("新しいフォルダ名:", name);
  if (!next?.trim()) return;
  const parent = folderPath.includes("/") ? folderPath.split("/").slice(0, -1).join("/") : "";
  const newName = next.trim().replace(/\\/g, "/").split("/").pop();
  const newFolder = parent ? `${parent}/${newName}` : newName;
  if (newFolder === folderPath) return;

  const paths = [...fileStore.keys()].filter((p) => p.startsWith(`${folderPath}/`));
  for (const p of paths) {
    const dest = newFolder + p.slice(folderPath.length);
    renameFilePath(p, dest);
  }
  workspaceTree?.removeVirtualFolderPrefix(folderPath);
  workspaceTree?.addVirtualFolder(newFolder);
  workspaceTree?.setContextFolder(newFolder);
  workspaceTree?.render();
}

function deleteFolder(folderPath) {
  const paths = [...fileStore.keys()].filter((p) => p.startsWith(`${folderPath}/`));
  if (paths.length && !window.confirm(`「${folderPath}」内の ${paths.length} ファイルを削除しますか？`)) {
    return;
  }
  paths.forEach((p) => deleteFile(p, { confirmDelete: false }));
  workspaceTree?.removeVirtualFolderPrefix(folderPath);
  workspaceTree?.render();
}

function createFolder(parent) {
  const name = prompt("フォルダ名:", "src");
  if (!name?.trim()) return;
  const cleaned = name.trim().replace(/\\/g, "/").split("/").pop();
  const folder = parent ? `${parent}/${cleaned}` : cleaned;
  workspaceTree?.addVirtualFolder(folder);
  workspaceTree?.setContextFolder(folder);
  workspaceTree?.render();
  appendConsole(`[files] folder: ${folder}`, "info");
}

function addFileInFolder(folder) {
  const defaultName = folder ? `${folder}/design.v` : "design.v";
  addFile(defaultName, { skipPrompt: false, defaultName });
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
  showMdiWindow(win);

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
      workspaceTree?.render();
      bringMdiToFront(win);
    });
    ed.onDidChangeModelContent(() => {
      scheduleTopModuleRefresh();
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

function addFile(name, options = {}) {
  const folder = workspaceTree?.getContextFolder() || "";
  const defaultName = options.defaultName || (folder ? `${folder}/design.v` : "design.v");
  let path = name;
  if (!options.skipPrompt) {
    path = prompt("ファイル名 (フォルダ/ファイル.v):", defaultName);
  }
  if (!path) return;
  path = path.trim().replace(/\\/g, "/");
  if (!path.endsWith(".v") && !path.endsWith(".sv")) path += ".v";
  putFileContent(path, `// ${path}\nmodule ${path.split("/").pop().replace(/\.(v|sv)$/i, "")};\nendmodule\n`);
  openFile(path);
  switchExplorerTab("files");
  refreshTopModulePicker();
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
  workspaceTree?.render();
  refreshTopModulePicker();
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

function resolveWaveformSignalNames(path) {
  if (!path) return [];
  const names = lastWaveformFull?.signals?.map((s) => s.name) || [...(lastSignalNames || [])];
  if (!names.length) return [];
  const candidates = [path];
  if (lastTopModule && !path.startsWith(`${lastTopModule}.`)) {
    candidates.push(`${lastTopModule}.${path}`);
  }
  for (const candidate of candidates) {
    if (names.includes(candidate)) return [candidate];
    const suffix = `.${candidate}`;
    const matches = names.filter((n) => n === candidate || n.endsWith(suffix));
    if (matches.length) return matches;
  }
  return [];
}

function allWaveformSignalNames() {
  return lastWaveformFull?.signals?.map((s) => s.name) || [];
}

function buildDisplayWaveform() {
  if (!lastWaveformFull) return null;
  const byName = new Map(lastWaveformFull.signals.map((s) => [s.name, s]));
  let order = waveformDisplayOrder.length
    ? waveformDisplayOrder.filter((n) => byName.has(n))
    : lastWaveformFull.signals.map((s) => s.name);
  for (const s of lastWaveformFull.signals) {
    if (!order.includes(s.name)) order.push(s.name);
  }
  const pick = waveformSelection.length ? new Set(waveformSelection) : null;
  if (pick) order = order.filter((n) => pick.has(n));
  let signals = order.map((n) => byName.get(n)).filter(Boolean);
  if (!signals.length) {
    signals = pick
      ? [...pick].map((n) => byName.get(n)).filter(Boolean)
      : lastWaveformFull.signals.slice(0, 12);
  }
  return {
    timescale: lastWaveformFull.timescale,
    signals,
  };
}

function updateWaveSignalCountLabel() {
  const el = $("wave-signal-count");
  if (!el) return;
  const total = lastWaveformFull?.signals?.length || 0;
  const shown = lastWaveform?.signals?.length || 0;
  if (!total) {
    el.textContent = "Run 後に波形表示";
    return;
  }
  el.textContent =
    waveformSelection.length > 0
      ? `${shown}/${total} 信号`
      : `${total} 信号（Hierarchy または All）`;
}

function refreshWaveformView() {
  lastWaveform = buildDisplayWaveform();
  updateWaveSignalCountLabel();
  if (lastWaveform) drawWave(lastWaveform);
  syncHierarchyWaveMarks();
  waveSignalPanel?.render();
}

function toggleWaveformSignal(path) {
  const resolved = resolveWaveformSignalNames(path);
  if (!resolved.length) {
    const hint = lastSignalNames?.size
      ? "Wave タブで選択するか、Hierarchy の信号をクリックしてください。"
      : "先に Run してください。";
    appendConsole(`[wave] 波形に "${path}" がありません。${hint}`, "warn");
    return;
  }
  const set = new Set(waveformSelection);
  const removing = resolved.every((n) => set.has(n));
  for (const name of resolved) {
    if (removing) set.delete(name);
    else set.add(name);
  }
  waveformSelection = [...set];
  const order = waveformDisplayOrder.length ? [...waveformDisplayOrder] : allWaveformSignalNames();
  for (const name of resolved) {
    if (!order.includes(name)) order.push(name);
  }
  waveformDisplayOrder = order;
  if (!waveformVisible) toggleWaveform(true);
  switchExplorerTab("wave");
  refreshWaveformView();
}

function syncHierarchyWaveMarks() {
  const active = new Set(waveformSelection);
  document.querySelectorAll("#hierarchy-tree .tree-node[data-signal-path]").forEach((row) => {
    const path = row.dataset.signalPath;
    const resolved = resolveWaveformSignalNames(path);
    const onWave = resolved.some((n) => active.has(n));
    row.classList.toggle("on-wave", onWave);
    row.classList.toggle("no-wave-data", Boolean(lastSignalNames?.size && !resolved.length));
  });
}

function renderTreeNode(node, parentEl, depth = 0) {
  const hasChildren = node.children && node.children.length > 0;
  const signalPath = node.signalPath || null;
  const row = document.createElement("div");
  row.className = "tree-node" + (signalPath && signalPath === selectedSignal ? " selected" : "");
  row.style.paddingLeft = `${depth * 4 + 4}px`;
  if (signalPath) row.dataset.signalPath = signalPath;

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

  if (signalPath) {
    const waveMark = document.createElement("span");
    waveMark.className = "wave-mark";
    waveMark.title = "クリックで Wave タブに追加/削除";
    waveMark.textContent = "〜";
    row.appendChild(waveMark);
  }

  row.addEventListener("click", (e) => {
    e.stopPropagation();
    if (signalPath) {
      selectedSignal = signalPath;
      document.querySelectorAll("#hierarchy-tree .tree-node").forEach((n) => n.classList.remove("selected"));
      row.classList.add("selected");
      toggleWaveformSignal(signalPath);
      return;
    }
    selectedSignal = node.name;
    document.querySelectorAll("#hierarchy-tree .tree-node").forEach((n) => n.classList.remove("selected"));
    row.classList.add("selected");
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
  const hint = document.createElement("div");
  hint.className = "empty-hint hierarchy-hint";
  const waveHint = lastSignalNames?.size
    ? `Run 済み — クリックで Wave に追加（詳細は Wave タブ）`
    : "信号クリックで Wave タブへ（Run 後）";
  hint.textContent = waveHint;
  root.appendChild(hint);
  renderTreeNode(tree, root);
  syncHierarchyWaveMarks();
}

function applySuggestedUntil(value) {
  const input = $("input-until");
  if (!input || value == null) return;
  const current = Number(input.value);
  if (!current || current <= 50) input.value = String(value);
}

function updateSignalCountBadge(count) {
  const badge = $("signal-count-badge");
  if (!badge) return;
  if (count > 0) {
    badge.textContent = `(${count})`;
    badge.title = "Run/Elab 後の elaborated 信号数";
  } else {
    badge.textContent = "";
    badge.title = "";
  }
}

function renderSignalList(signals) {
  const list = $("signal-list");
  list.innerHTML = "";
  updateSignalCountBadge(signals?.length || 0);
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
    const onWave = waveformSelection.includes(sig.name);
    if (onWave) li.classList.add("on-wave");
    const name = document.createElement("span");
    name.textContent = sig.name;
    const val = document.createElement("span");
    val.className = "val";
    val.textContent = sig.value;
    li.appendChild(name);
    li.appendChild(val);
    li.title = "クリックで Wave タブに追加/削除";
    li.addEventListener("click", () => {
      list.querySelectorAll("li").forEach((n) => n.classList.remove("active"));
      li.classList.add("active");
      selectedSignal = sig.name;
      toggleWaveformSignal(sig.name);
    });
    list.appendChild(li);
  });
}

function highlightSignal(name) {
  if (!name) return;
  toggleWaveformSignal(name);
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
  if (!body.querySelector("textarea.console-output")) {
    const area = document.createElement("textarea");
    area.id = "mdi-console-output";
    area.className = "console-output";
    area.readOnly = true;
    area.spellcheck = false;
    body.appendChild(area);
  }
  showMdiWindow(win);
  return win;
}

function createWaveformWindow() {
  const win = createMdiWindow("waveform", "Waveform", {
    x: 760,
    y: 80,
    width: 720,
    height: 360,
    bodyClass: "mdi-waveform",
    show: waveformVisible,
  });
  const body = win.querySelector(".mdi-body");
  if (!body.querySelector("#waveform-canvas")) {
    body.innerHTML = `
      <div class="wave-toolbar">
        <span id="wave-signal-count" class="wave-signal-count">Run 後に波形表示</span>
        <button type="button" id="btn-wave-zoom-out" class="mini-btn" title="時間軸を縮小">−</button>
        <button type="button" id="btn-wave-zoom-in" class="mini-btn" title="時間軸を拡大">＋</button>
        <button type="button" id="btn-wave-fit" class="mini-btn" title="全体表示に戻す">Fit</button>
        <button type="button" id="btn-wave-all" class="mini-btn" title="Run 後の全 VCD 信号を表示">All</button>
        <label class="check"><input type="checkbox" id="chk-auto-scroll" checked /> Auto-scroll</label>
      </div>
      <div id="waveform-wrap" class="waveform-wrap">
        <canvas id="waveform-canvas"></canvas>
      </div>
    `;
    body.querySelector("#btn-wave-fit")?.addEventListener("click", fitWaveform);
    body.querySelector("#btn-wave-all")?.addEventListener("click", () => {
      if (!lastWaveformFull) return;
      const names = lastWaveformFull.signals.map((s) => s.name);
      waveformSelection = names;
      waveformDisplayOrder = names.slice();
      refreshWaveformView();
      switchExplorerTab("wave");
    });
    body.querySelector("#btn-wave-zoom-in")?.addEventListener("click", () => setWaveZoom(waveZoom * 1.5));
    body.querySelector("#btn-wave-zoom-out")?.addEventListener("click", () => setWaveZoom(waveZoom / 1.5));
    body.querySelector("#chk-auto-scroll")?.addEventListener("change", () => {
      if (waveformVisible && lastWaveform) redrawWaveformCanvas(lastWaveform);
    });
    if (window.ResizeObserver) {
      const observer = new ResizeObserver(() => {
        if (waveformVisible && !win.hidden && lastWaveform) {
          redrawWaveformCanvas(lastWaveform);
        }
      });
      observer.observe(body);
    }
  }
  if (waveformVisible) showMdiWindow(win);
  return win;
}

function redrawWaveformCanvas(waveform) {
  if (!waveform || !window.HDLSimWaveform?.drawWaveform) return;
  const canvas = $("waveform-canvas");
  if (!canvas) return;
  window.HDLSimWaveform.drawWaveform(canvas, waveform, {
    wrap: $("waveform-wrap"),
    zoom: waveZoom,
    autoScroll: $("chk-auto-scroll")?.checked !== false,
  });
}

function drawWave(waveform) {
  if (!waveform || !window.HDLSimWaveform?.drawWaveform) return;
  if (!waveformVisible) return;
  createWaveformWindow();
  redrawWaveformCanvas(waveform);
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

function ensureConsoleVisible() {
  document.body.classList.remove("view-hide-output-panel");
  if (!splitV) return;
  const sizes = splitV.getSizes();
  if (sizes[1] < 18) splitV.setSizes([65, 35]);
}

async function runElaborate() {
  setStatus("Elaborating…", "busy");
  ensureConsoleVisible();
  try {
    const payload = getPayload();
    appendConsole(`[elab] ${payload.files.length} file(s): ${payload.files.map((f) => f.path).join(", ")}`, "info");
    const data = await api("/api/elaborate", payload);
    if (!data.ok) {
      appendConsole([data.error, data.trace].filter(Boolean).join("\n\n"), "err");
      renderHierarchy(null);
      renderSignalList([]);
      setStatus("Elab error", "err");
      switchExplorerTab("hierarchy");
      return;
    }
    lastSignalNames = new Set(data.signal_names || []);
    renderHierarchy(data.hierarchy);
    applySuggestedUntil(data.suggested_until);
    refreshTopModulePicker(data.top);
    syncTopPickerToModules();
    setStatus(`top=${data.top} · ${data.net_count} nets`, "ok");
    appendConsole(`[elab] top=${data.top} nets=${data.net_count}`, "ok");
    if (data.top_requested && data.top_requested !== data.top) {
      appendConsole(
        `[hint] Top を ${data.top_requested} → ${data.top} に自動変更しました（モジュール一覧に合わせて選択）`,
        "warn",
      );
    }
    if (data.suggested_until != null) {
      appendConsole(`[hint] Until の推奨値: ${data.suggested_until}（parameter STEP ベンチ向け）`, "info");
    }
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
  ensureConsoleVisible();
  clearConsole();
  abortController = new AbortController();

  try {
    const payload = getPayload();
    const topLabel = effectiveTopForPayload() || "(auto)";
    appendConsole(`[run] ${payload.files.length} file(s): ${payload.files.map((f) => f.path).join(", ")}`, "info");
    appendConsole(`[run] top=${topLabel}`, "info");

    const data = await api("/api/simulate", payload, abortController.signal);
    if (!data.ok) {
      appendConsole([data.error, data.trace].filter(Boolean).join("\n\n"), "err");
      if (data.console) appendConsole(data.console);
      renderHierarchy(null);
      renderSignalList([]);
      setStatus("Sim failed", "err");
      return;
    }
    if (data.console) appendConsole(data.console);
    appendConsole(`time=${data.stop_time} events=${data.events_processed} top=${data.top_module}`, "ok");
    if (data.top_requested && data.top_requested !== data.top) {
      appendConsole(
        `[hint] Top を ${data.top_requested} → ${data.top} に自動変更しました`,
        "warn",
      );
    }
    refreshTopModulePicker(data.top_module || data.top);
    renderHierarchy(data.hierarchy);
    renderSignalList(data.signals);
    lastTopModule = data.top_module || "";
    lastSignalNames = new Set(data.signal_names || data.signals?.map((s) => s.name) || []);
    lastWaveformFull = data.waveform;
    const waveNames = data.waveform?.signals?.map((s) => s.name) || [];
    waveformSelection = waveNames.slice();
    waveformDisplayOrder = waveNames.slice();
    applySuggestedUntil(data.suggested_until);
    refreshWaveformView();
    const waveCount = data.waveform?.signals?.length || 0;
    if (waveCount > 0) {
      appendConsole(`[wave] ${waveCount} signals — Wave タブで選択・並べ替え`, "info");
    } else {
      appendConsole("[wave] 波形データが空です。Run が成功していても VCD に信号がありません。", "warn");
    }
    if (data.hints?.length) {
      data.hints.forEach((h) => appendConsole(`[hint] ${h}`, "warn"));
    }
    switchExplorerTab("hierarchy");
    setStatus(`top=${data.top_module} t=${data.stop_time} ev=${data.events_processed}`, "ok");
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

    initWorkspaceTreeView();
    tileFileWindows();
    renderEditorTabs();
    refreshTopModulePicker();
    renderHierarchy(null);
    loadExamples();
    loadProjects();
    verifyUiBuild();
  });
}

function initWaveSignalPanelUi() {
  const root = $("wave-signal-panel");
  if (!root) return;
  waveSignalPanel = createWaveSignalPanel(root, {
    getSignalNames: () => allWaveformSignalNames(),
    getSelection: () => waveformSelection.slice(),
    setSelection: (names) => {
      waveformSelection = names;
    },
    getOrder: () => waveformDisplayOrder.slice(),
    setOrder: (names) => {
      waveformDisplayOrder = names;
    },
    onChange: () => {
      if (!waveformVisible && waveformSelection.length) toggleWaveform(true);
      refreshWaveformView();
    },
  });
  waveSignalPanel.render();
}

function bindUi() {
  initWaveSignalPanelUi();
  $("btn-run").addEventListener("click", runSimulate);
  $("btn-stop").addEventListener("click", stopSimulation);
  $("btn-step").addEventListener("click", runStep);
  $("btn-elab").addEventListener("click", runElaborate);
  $("btn-clear-console").addEventListener("click", clearConsole);
  $("btn-copy-console")?.addEventListener("click", () => copyConsoleText());
  $("btn-copy-console-err")?.addEventListener("click", () => copyConsoleText({ errorsOnly: true }));
  $("btn-select-console")?.addEventListener("click", () => focusConsole(true));
  $("btn-wave-toggle").addEventListener("click", () => toggleWaveform());
  $("btn-wave-close")?.addEventListener("click", () => toggleWaveform(false));
  $("btn-wave-fit")?.addEventListener("click", fitWaveform);
  $("btn-open-files").addEventListener("click", () => openFilePicker());
  $("btn-new-file").addEventListener("click", () => addFileInFolder(workspaceTree?.getContextFolder() || ""));
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
    if (waveformVisible && lastWaveform) redrawWaveformCanvas(lastWaveform);
  });

  initConsoleKeyboard();

  initMenuBar();
}

function initMenuBar() {
  window.HDLSimMenuBar?.init({
    getMenuContext,
    actions: {
      "file.new": () => addFileInFolder(workspaceTree?.getContextFolder() || ""),
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

  const key = e.key.toLowerCase();
  if (
    key === "c" &&
    (isConsoleElement(e.target) || e.target?.closest?.("#pane-console, .mdi-output"))
  ) {
    return false;
  }
  if (inField) return false;
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

function compareSemver(a, b) {
  const pa = String(a).split(".").map((n) => parseInt(n, 10) || 0);
  const pb = String(b).split(".").map((n) => parseInt(n, 10) || 0);
  for (let i = 0; i < 3; i += 1) {
    const da = pa[i] || 0;
    const db = pb[i] || 0;
    if (da !== db) return da - db;
  }
  return 0;
}

function showUpdateBanner(options) {
  const banner = $("update-banner");
  if (!banner) return;

  const {
    latestVersion,
    currentVersion,
    releaseUrl,
    downloadUrl,
    mode = "remote",
  } = options;

  const url = downloadUrl || releaseUrl || "https://github.com/PeRoHi/HDL-Sim/releases/latest";
  const linkLabel = downloadUrl
    ? (downloadUrl.toLowerCase().endsWith(".zip") ? "ZIP をダウンロード" : "ダウンロード")
    : "リリースを見る";

  let message;
  if (mode === "local") {
    message =
      `<strong>更新あり:</strong> HDL-Sim ${latestVersion} ` +
      `(前回 ${currentVersion})。ページを再読み込みしてください。`;
  } else {
    message =
      `<strong>新しいバージョンがあります:</strong> ${latestVersion} ` +
      `(現在 ${currentVersion})。` +
      ` 新しい ZIP を取得し、フォルダごと入れ替えて更新してください。`;
  }

  banner.innerHTML =
    `<span>${message}</span>` +
    `<a href="${url}" target="_blank" rel="noopener">${linkLabel}</a>` +
    `<button type="button" id="btn-dismiss-update">後で</button>`;
  banner.hidden = false;

  $("btn-dismiss-update")?.addEventListener("click", () => {
    banner.hidden = true;
    localStorage.setItem(DISMISS_UPDATE_KEY, latestVersion);
    if (mode === "local") {
      localStorage.setItem(UI_VERSION_KEY, latestVersion);
    }
  });
}

function checkForLocalUpdates(info) {
  if (!info?.version) return;
  const previous = localStorage.getItem(UI_VERSION_KEY);
  localStorage.setItem(UI_VERSION_KEY, info.version);
  if (!previous || compareSemver(info.version, previous) <= 0) return;
  if (localStorage.getItem(DISMISS_UPDATE_KEY) === info.version) return;
  showUpdateBanner({
    latestVersion: info.version,
    currentVersion: previous,
    releaseUrl: info.release_url,
    mode: "local",
  });
  appendConsole(`[update] ${previous} → ${info.version}`, "info");
}

async function checkForRemoteUpdates(currentVersion) {
  try {
    const data = await api("/api/update-check");
    if (!data.ok || !data.update_available) return;
    if (localStorage.getItem(DISMISS_UPDATE_KEY) === data.latest_version) return;
    showUpdateBanner({
      latestVersion: data.latest_version,
      currentVersion: data.current_version || currentVersion,
      releaseUrl: data.release_url,
      downloadUrl: data.download_url,
      mode: "remote",
    });
    appendConsole(
      `[update] 新しいリリース ${data.latest_version} があります (現在 ${data.current_version})`,
      "info"
    );
  } catch {
    /* offline or GitHub unreachable */
  }
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
    checkForLocalUpdates(info);
    await checkForRemoteUpdates(info.version);
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
