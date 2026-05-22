/**
 * HDL-Sim Silos-style web UI
 */

const DEFAULT_SOURCE = `// ここで Verilog を編集して ▶ 実行 できます
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

let editor = null;
let lastWaveform = null;
let selectedSignal = null;

const $ = (id) => document.getElementById(id);

function setStatus(text, kind = "") {
  const bar = $("status-bar");
  bar.textContent = text;
  bar.className = "toolbar-status" + (kind ? ` ${kind}` : "");
}

function appendConsole(text, kind) {
  const el = $("console-output");
  if (!text) return;
  const prefix = kind === "err" ? "[ERROR] " : kind === "ok" ? "[OK] " : "";
  el.textContent += prefix + text + (text.endsWith("\n") ? "" : "\n");
  el.scrollTop = el.scrollHeight;
}

function clearConsole() {
  $("console-output").textContent = "";
}

function getPayload() {
  const top = $("input-top").value.trim();
  return {
    files: [{ path: "design.v", content: editor.getValue() }],
    top: top || null,
    until: Number($("input-until").value) || null,
    max_events: Number($("input-max-events").value) || 500,
    generate_vcd: true,
  };
}

function renderTree(node, parentEl) {
  const li = document.createElement("li");
  const label = document.createElement("span");
  label.textContent = node.name;
  if (node.kind && node.kind !== "module") {
    const kind = document.createElement("span");
    kind.className = "kind";
    kind.textContent = node.direction || node.kind;
    label.appendChild(kind);
  }
  li.appendChild(label);
  if (node.name === selectedSignal) li.classList.add("selected");
  li.addEventListener("click", () => {
    selectedSignal = node.name;
    document.querySelectorAll("#hierarchy-tree li").forEach((n) => n.classList.remove("selected"));
    li.classList.add("selected");
    highlightSignal(node.name);
  });
  parentEl.appendChild(li);
  if (node.children && node.children.length) {
    const ul = document.createElement("ul");
    li.appendChild(ul);
    node.children.forEach((child) => renderTree(child, ul));
  }
}

function renderHierarchy(tree) {
  const root = $("hierarchy-tree");
  root.innerHTML = "";
  if (!tree) {
    root.textContent = "階層を更新するか実行してください";
    return;
  }
  const ul = document.createElement("ul");
  renderTree(tree, ul);
  root.appendChild(ul);
}

function renderSignalList(signals) {
  const list = $("signal-list");
  list.innerHTML = "";
  if (!signals || !signals.length) {
    const li = document.createElement("li");
    li.textContent = "(信号なし)";
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
    val.textContent = `=${sig.value}`;
    li.appendChild(name);
    li.appendChild(val);
    li.addEventListener("click", () => {
      list.querySelectorAll("li").forEach((n) => n.classList.remove("active"));
      li.classList.add("active");
      selectedSignal = sig.name;
      highlightSignal(sig.name);
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
  if (!filtered.signals.length) filtered.signals = lastWaveform.signals.slice(0, 8);
  drawWave(filtered);
}

function drawWave(waveform) {
  const canvas = $("waveform-canvas");
  window.HDLSimWaveform.drawWaveform(canvas, waveform, { wrap: $("waveform-wrap") });
}

async function api(path, body) {
  const res = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  return res.json();
}

async function loadExamples() {
  const sel = $("select-example");
  try {
    const items = await api("/api/examples");
    sel.innerHTML = '<option value="">— 例を選ぶ —</option>';
    items.forEach((ex) => {
      const opt = document.createElement("option");
      opt.value = ex.id;
      opt.textContent = ex.label;
      sel.appendChild(opt);
    });
  } catch (e) {
    setStatus("例の読み込みに失敗", "err");
  }
}

async function openExample(id) {
  if (!id) return;
  setStatus("例を読み込み中…", "busy");
  const data = await api(`/api/examples/${encodeURIComponent(id)}`);
  editor.setValue(data.content);
  const topGuess = data.content.match(/module\s+(\w+)\s*;/g);
  $("input-top").value = "";
  if (id.includes("silos")) $("input-top").value = "silos_regression_tb";
  else if (id.includes("tb_multi")) $("input-top").value = "tb_multi";
  else if (id.includes("hierarchy")) $("input-top").value = "tb";
  setStatus(`例: ${id}`, "ok");
  runElaborate();
}

async function runElaborate() {
  setStatus("階層を解析中…", "busy");
  $("btn-elab").disabled = true;
  try {
    const data = await api("/api/elaborate", getPayload());
    if (!data.ok) {
      appendConsole(data.error + "\n" + (data.trace || ""), "err");
      setStatus("解析エラー", "err");
      return;
    }
    renderHierarchy(data.hierarchy);
    if (data.top) $("input-top").placeholder = data.top;
    setStatus(`モジュール ${data.overview.module_names.length} / 信号 ${data.net_count}`, "ok");
    appendConsole(`[elab] top=${data.top} nets=${data.net_count}`, "ok");
  } catch (e) {
    setStatus("通信エラー", "err");
    appendConsole(String(e), "err");
  } finally {
    $("btn-elab").disabled = false;
  }
}

async function runSimulate() {
  setStatus("シミュレーション実行中…", "busy");
  $("btn-run").disabled = true;
  clearConsole();
  try {
    const data = await api("/api/simulate", getPayload());
    if (!data.ok) {
      appendConsole(data.error + "\n" + (data.trace || ""), "err");
      setStatus("シミュレーション失敗", "err");
      return;
    }
    appendConsole(data.console || "(出力なし)");
    appendConsole(
      `time=${data.stop_time} events=${data.events_processed} top=${data.top_module}`,
      "ok"
    );
    renderHierarchy(data.hierarchy);
    renderSignalList(data.signals);
    lastWaveform = data.waveform;
    drawWave(data.waveform);
    setStatus(`完了 t=${data.stop_time} イベント=${data.events_processed}`, "ok");
  } catch (e) {
    setStatus("通信エラー", "err");
    appendConsole(String(e), "err");
  } finally {
    $("btn-run").disabled = false;
  }
}

function initMonaco() {
  require.config({
    paths: { vs: "https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs" },
  });
  require(["vs/editor/editor.main"], () => {
    editor = monaco.editor.create($("editor"), {
      value: DEFAULT_SOURCE,
      language: "verilog",
      theme: "vs-dark",
      automaticLayout: true,
      fontSize: 13,
      minimap: { enabled: false },
      scrollBeyondLastLine: false,
      wordWrap: "on",
    });
    loadExamples();
    runElaborate();
  });
}

function bindUi() {
  $("btn-run").addEventListener("click", runSimulate);
  $("btn-elab").addEventListener("click", runElaborate);
  $("btn-clear-console").addEventListener("click", clearConsole);
  $("btn-wave-fit").addEventListener("click", () => drawWave(lastWaveform));
  $("select-example").addEventListener("change", (e) => openExample(e.target.value));
  window.addEventListener("resize", () => {
    if (lastWaveform) drawWave(lastWaveform);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "F5") {
      e.preventDefault();
      runSimulate();
    }
  });
}

bindUi();
initMonaco();
