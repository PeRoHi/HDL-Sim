import { createWaveSignalPanel } from "./wave-signal-panel.js";
import { loadWaveViewSettings, saveWaveViewSettings } from "./wave-prefs.js";

const $ = (id) => document.getElementById(id);

let waveZoom = 1;
let waveTickStep = loadWaveViewSettings().tickStep;
let waveSignalPanel = null;
let currentWaveform = null;
let selection = [];
let displayOrder = [];
let resizeObserver = null;

function renderWave() {
  if (!currentWaveform || !window.HDLSimWaveform?.drawWaveform) return;
  const canvas = $("waveform-canvas");
  if (!canvas) return;
  
  // 親の drawWaveform で使っているのと同じフィルタ済みwaveformを渡す
  // もし HDLSimWaveform 側で selection を考慮してくれないなら、ここでフィルタするか、
  // 親から受け取った filtered waveform をそのまま描画する
  const ctx = window.opener?.getLatestWaveformContext?.();
  const waveToDraw = ctx?.filteredWaveform || currentWaveform;

  updateWaveTickUnitLabel(waveToDraw.timescale || currentWaveform?.timescale);
  window.HDLSimWaveform.drawWaveform(canvas, waveToDraw, {
    wrap: $("waveform-wrap"),
    zoom: waveZoom,
    tickStep: waveTickStep,
    autoScroll: $("chk-auto-scroll")?.checked !== false,
  });
}

function updateWaveTickUnitLabel(timescale) {
  const unitEl = $("wave-tick-unit");
  if (!unitEl) return;
  const unit = window.HDLSimWaveform?.parseTimescaleUnit?.(timescale) || "";
  unitEl.textContent = unit ? unit : "";
}

function applyWaveTickStep(raw) {
  const text = String(raw ?? "").trim();
  const next = text === "" ? 0 : Number(text);
  waveTickStep = Number.isFinite(next) && next > 0 ? next : 0;
  saveWaveViewSettings({ tickStep: waveTickStep });
  const tickInput = $("inp-wave-tick");
  if (tickInput) {
    if (waveTickStep > 0) tickInput.value = String(waveTickStep);
    else tickInput.value = "";
  }
  renderWave();
}

function fitWaveform() {
  waveZoom = 1;
  const wrap = $("waveform-wrap");
  if (wrap) wrap.scrollLeft = 0;
  renderWave();
}

function setWaveZoom(nextZoom) {
  waveZoom = Math.min(32, Math.max(1, nextZoom));
  const auto = $("chk-auto-scroll");
  if (auto) auto.checked = false;
  renderWave();
}

function initSignalPanel() {
  const root = $("wave-signal-panel");
  waveSignalPanel = createWaveSignalPanel(root, {
    getSignalNames: () => {
      return currentWaveform?.signals?.map(s => s.name) || [];
    },
    getSelection: () => selection,
    setSelection: (names) => {
      selection = names;
      if (window.opener?.setWaveformSelection) {
        window.opener.setWaveformSelection(names);
      }
    },
    getOrder: () => displayOrder,
    setOrder: (names) => {
      displayOrder = names;
      if (window.opener?.setWaveformOrder) {
        window.opener.setWaveformOrder(names);
      }
    },
    onChange: () => {
      renderWave();
    },
  });
}

let lastUpdateKey = "";

async function syncFromBackend() {
  try {
    const res = await fetch("/api/waveform_sync");
    if (!res.ok) return;
    const ctx = await res.json();
    
    if (!ctx || !ctx.waveform) {
      $("status").textContent = "Waiting for waveform data...";
      return;
    }

    const currentKey = ctx.waveform.stop_time + "_" + (ctx.selection || []).join(",");
    if (currentKey !== lastUpdateKey) {
      currentWaveform = ctx.filteredWaveform || ctx.waveform;
      selection = ctx.selection || [];
      displayOrder = ctx.order || [];
      lastUpdateKey = currentKey;
      
      $("status").textContent = `Linked to Main UI (${currentWaveform.signals.length} signals)`;
      
      if (waveSignalPanel) {
        waveSignalPanel.render();
      }
      renderWave();
    }
  } catch (err) {
    $("status").textContent = "Disconnected from backend.";
  }
}

window.addEventListener("message", (e) => {
  if (e.data === "waveform_updated") {
    syncFromBackend();
  }
});

document.addEventListener("DOMContentLoaded", () => {
  initSignalPanel();
  
  $("btn-fit").addEventListener("click", fitWaveform);
  $("btn-zoom-in").addEventListener("click", () => setWaveZoom(waveZoom * 1.5));
  $("btn-zoom-out").addEventListener("click", () => setWaveZoom(waveZoom / 1.5));
  const tickInput = $("inp-wave-tick");
  if (tickInput) {
    if (waveTickStep > 0) tickInput.value = String(waveTickStep);
    tickInput.addEventListener("change", () => applyWaveTickStep(tickInput.value));
    tickInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        applyWaveTickStep(tickInput.value);
        tickInput.blur();
      }
    });
  }
  $("btn-all").addEventListener("click", () => {
    if (!currentWaveform) return;
    const names = currentWaveform.signals.map((s) => s.name);
    selection = names;
    displayOrder = names.slice();
    // Update locally and attempt to update backend if needed (optional)
    waveSignalPanel?.render();
    renderWave();
  });
  $("chk-auto-scroll").addEventListener("change", renderWave);
  
  if (window.ResizeObserver) {
    resizeObserver = new ResizeObserver(() => {
      if (currentWaveform) renderWave();
    });
    resizeObserver.observe($("waveform-wrap"));
  }
  
  syncFromBackend();
  setInterval(syncFromBackend, 1000); // 1秒ごとに同期チェック
});
