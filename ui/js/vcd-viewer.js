/**
 * Multi-signal waveform renderer — VS Code / EDA style
 */
(function (global) {
  const ROW_HEIGHT = 24;
  const ANALOG_ROW_HEIGHT = 52;
  const LABEL_WIDTH = 160;
  const PADDING = 6;
  const HEADER_H = 18;

  const COLORS = {
    bg: "#1a1a1a",
    grid: "#2d2d2d",
    gridText: "#6a6a6a",
    label: "#cccccc",
    labelDim: "#858585",
    high: "#4fc1ff",
    low: "#569cd6",
    x: "#ce9178",
    z: "#808080",
    bus: "#dcdcaa",
    analog: "#4ec9b0",
    analogGrid: "#2a3d38",
    cursor: "#007acc",
  };

  function analogSignalSet(options) {
    const set = new Set();
    if (options.analogSignals) {
      for (const name of options.analogSignals) set.add(name);
    }
    return set;
  }

  function isAnalogSignal(sig, analogSet) {
    if (sig.kind === "real") return true;
    return analogSet.has(sig.name);
  }

  function buildRows(waveform, options = {}) {
    if (!waveform?.signals) return [];
    const analogSet = analogSignalSet(options);
    return waveform.signals.map((sig) => ({
      name: sig.name,
      width: sig.width,
      kind: sig.kind || "wire",
      changes: sig.changes || [],
      analog: isAnalogSignal(sig, analogSet),
    }));
  }

  function timeRange(rows) {
    let max = 10;
    for (const row of rows) {
      for (const [t] of row.changes) {
        if (t > max) max = t;
      }
    }
    return max;
  }

  function valueAt(changes, time) {
    let val = changes.length ? changes[0][1] : "0";
    for (const [t, v] of changes) {
      if (t > time) break;
      val = v;
    }
    return val;
  }

  function signalLevel(v, width) {
    const ch = String(v).toLowerCase();
    if (ch === "x") return "x";
    if (ch === "z") return "z";
    if (width > 1) return "bus";
    if (ch === "1") return "high";
    if (ch === "0") return "low";
    const n = parseInt(ch, 2);
    if (!Number.isNaN(n) && n > 0) return "bus";
    return "low";
  }

  function colorForLevel(level) {
    switch (level) {
      case "high": return COLORS.high;
      case "x": return COLORS.x;
      case "z": return COLORS.z;
      case "bus": return COLORS.bus;
      default: return COLORS.low;
    }
  }

  function yForLevel(level, y0, y1) {
    const mid = (y0 + y1) / 2;
    if (level === "bus" || level === "x" || level === "z") return mid;
    return level === "high" ? y0 : y1;
  }

  function formatBusValue(v, width) {
    const s = String(v);
    if (/^[01xzXZ]+$/.test(s)) {
      const n = parseInt(s.replace(/x/gi, "0").replace(/z/gi, "0"), 2);
      if (!Number.isNaN(n)) {
        const hex = n.toString(16).toUpperCase();
        return width > 4 ? `'h${hex}` : `'h${hex}`;
      }
    }
    return s;
  }

  function drawScalarWave(ctx, points, y0, y1) {
    ctx.lineWidth = 2;
    for (let i = 1; i < points.length; i++) {
      const prev = points[i - 1];
      const p = points[i];
      const color = colorForLevel(p.level);
      ctx.strokeStyle = color;
      ctx.beginPath();
      ctx.moveTo(prev.x, prev.y);
      ctx.lineTo(p.x, prev.y);
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
    }
  }

  function parseAnalogSample(v, row) {
    const raw = String(v);
    if (row.kind === "real" || raw.startsWith("r")) {
      const num = parseFloat(raw.startsWith("r") ? raw.slice(1) : raw);
      return Number.isFinite(num) ? num : 0;
    }
    let bits = raw;
    if (bits.startsWith("b")) bits = bits.slice(1);
    if (!/^[01xzXZ]+$/.test(bits)) {
      const n = Number(bits);
      return Number.isFinite(n) ? n : 0;
    }
    const width = row.width || 32;
    const n = parseInt(bits.replace(/[xzXZ]/g, "0"), 2);
    if (!Number.isFinite(n)) return 0;
    if (width > 0 && width < 64) {
      const sign = 1 << (width - 1);
      const mod = 1 << width;
      if (n & sign) return n - mod;
    }
    return n;
  }

  function formatAnalogValue(value) {
    const abs = Math.abs(value);
    if (abs >= 10000 || (abs > 0 && abs < 0.01)) return value.toExponential(2);
    if (Number.isInteger(value)) return String(value);
    return value.toFixed(2).replace(/\.?0+$/, "");
  }

  function drawAnalogWave(ctx, row, plotLeft, scale, y0, y1, maxTime) {
    const times = new Set([0, maxTime]);
    row.changes.forEach(([t]) => times.add(t));
    const sorted = Array.from(times).sort((a, b) => a - b);

    const samples = sorted.map((t) => ({
      t,
      x: plotLeft + t * scale,
      value: parseAnalogSample(valueAt(row.changes, t), row),
    }));

    let vmin = samples[0]?.value ?? 0;
    let vmax = samples[0]?.value ?? 0;
    for (const s of samples) {
      if (s.value < vmin) vmin = s.value;
      if (s.value > vmax) vmax = s.value;
    }
    if (vmin === vmax) {
      vmin -= 1;
      vmax += 1;
    }
    const pad = (vmax - vmin) * 0.08 || 1;
    vmin -= pad;
    vmax += pad;
    const span = vmax - vmin || 1;

    const valueToY = (value) => y1 - ((value - vmin) / span) * (y1 - y0);

    // Value grid (mid + zero if in range)
    ctx.strokeStyle = COLORS.analogGrid;
    ctx.lineWidth = 1;
    const midVal = (vmin + vmax) / 2;
    for (const gv of [vmin, midVal, vmax]) {
      const gy = valueToY(gv);
      ctx.beginPath();
      ctx.moveTo(plotLeft, gy);
      ctx.lineTo(plotLeft + maxTime * scale, gy);
      ctx.stroke();
    }
    if (vmin < 0 && vmax > 0) {
      const zy = valueToY(0);
      ctx.strokeStyle = COLORS.grid;
      ctx.beginPath();
      ctx.moveTo(plotLeft, zy);
      ctx.lineTo(plotLeft + maxTime * scale, zy);
      ctx.stroke();
    }

    ctx.strokeStyle = COLORS.analog;
    ctx.lineWidth = 1.75;
    ctx.beginPath();
    for (let i = 0; i < samples.length; i++) {
      const s = samples[i];
      const y = valueToY(s.value);
      if (i === 0) ctx.moveTo(s.x, y);
      else {
        const prev = samples[i - 1];
        ctx.lineTo(s.x, valueToY(prev.value));
        ctx.lineTo(s.x, y);
      }
    }
    ctx.stroke();

    // Range label on left
    ctx.fillStyle = COLORS.labelDim;
    ctx.font = "8px monospace";
    ctx.textAlign = "right";
    ctx.fillText(formatAnalogValue(vmax), LABEL_WIDTH - 6, y0 + 8);
    ctx.fillText(formatAnalogValue(vmin), LABEL_WIDTH - 6, y1 - 2);
  }

  function drawBusWave(ctx, points, y0, y1, mid, width) {
    const railTop = y0 + 2;
    const railBot = y1 - 2;
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = COLORS.bus;
    ctx.fillStyle = COLORS.bus;

    for (let i = 0; i < points.length; i++) {
      const p = points[i];
      const nextX = i < points.length - 1 ? points[i + 1].x : p.x;

      if (i > 0) {
        ctx.beginPath();
        ctx.moveTo(p.x, railTop);
        ctx.lineTo(p.x, railBot);
        ctx.stroke();
      }

      if (nextX > p.x) {
        ctx.beginPath();
        ctx.moveTo(p.x, railTop);
        ctx.lineTo(nextX, railTop);
        ctx.moveTo(p.x, railBot);
        ctx.lineTo(nextX, railBot);
        ctx.stroke();

        const segW = nextX - p.x;
        if (segW > 16 && p.v != null) {
          ctx.font = "9px monospace";
          ctx.textAlign = "center";
          ctx.fillText(formatBusValue(p.v, width), p.x + segW / 2, mid + 3);
        }
      }
    }
  }

  function parseTimescaleUnit(timescale) {
    if (!timescale) return "";
    const part = String(timescale).split("/")[0].trim();
    const match = part.match(/^(\d+)(.+)$/);
    return match ? match[2] : "";
  }

  /** Pick a readable tick interval from span and plot width (~1 label per 48px). */
  function computeAutoTickStep(maxTime, plotWidth, minLabelPx = 48) {
    if (maxTime <= 0) return 1;
    const targetCount = Math.max(2, Math.floor(plotWidth / minLabelPx));
    const rough = maxTime / targetCount;
    if (rough <= 1) return 1;
    const magnitude = Math.pow(10, Math.floor(Math.log10(rough)));
    const normalized = rough / magnitude;
    let nice;
    if (normalized <= 1) nice = 1;
    else if (normalized <= 2) nice = 2;
    else if (normalized <= 5) nice = 5;
    else nice = 10;
    return Math.max(1, Math.round(nice * magnitude));
  }

  function resolveTickStep(maxTime, plotWidth, userStep) {
    const step = Number(userStep);
    if (Number.isFinite(step) && step > 0) return step;
    return computeAutoTickStep(maxTime, plotWidth);
  }

  function buildTickTimes(maxTime, tickStep) {
    const times = [];
    if (maxTime <= 0) return [0];
    const step = Math.max(1, tickStep);
    for (let t = 0; t < maxTime; t += step) times.push(t);
    if (times[times.length - 1] !== maxTime) times.push(maxTime);
    return times;
  }

  function drawWaveform(canvas, waveform, options = {}) {
    const rows = buildRows(waveform, options);
    const wrap = options.wrap || canvas.parentElement;

    if (!rows.length) {
      const ctx = canvas.getContext("2d");
      canvas.width = Math.max(wrap?.clientWidth || 400, 400);
      canvas.height = 80;
      ctx.fillStyle = COLORS.bg;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = COLORS.labelDim;
      ctx.font = "11px sans-serif";
      ctx.fillText("Run simulation to view waveforms", 12, 44);
      return;
    }

    const maxTime = timeRange(rows);
    const zoom = Math.max(1, Number(options.zoom) || 1);
    const viewWidth = Math.max(wrap?.clientWidth || 400, 400);
    const plotWidth = (viewWidth - LABEL_WIDTH - PADDING * 2) * zoom;
    const canvasWidth = LABEL_WIDTH + PADDING * 2 + plotWidth;
    const bodyHeight = rows.reduce((sum, row) => sum + (row.analog ? ANALOG_ROW_HEIGHT : ROW_HEIGHT), 0) + PADDING;
    const height = bodyHeight + HEADER_H + PADDING;
    canvas.width = canvasWidth;
    canvas.height = height;

    const ctx = canvas.getContext("2d");
    ctx.fillStyle = COLORS.bg;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const scale = plotWidth / Math.max(maxTime, 1);
    const plotLeft = LABEL_WIDTH + PADDING;

    // Time axis header
    ctx.fillStyle = "#252526";
    ctx.fillRect(0, 0, canvas.width, HEADER_H);
    ctx.strokeStyle = COLORS.grid;
    ctx.lineWidth = 1;

    const tickStep = resolveTickStep(maxTime, plotWidth, options.tickStep);
    const timeUnit = parseTimescaleUnit(waveform.timescale);
    const tickTimes = buildTickTimes(maxTime, tickStep);

    for (const t of tickTimes) {
      const x = plotLeft + t * scale;
      ctx.beginPath();
      ctx.moveTo(x, HEADER_H);
      ctx.lineTo(x, height);
      ctx.stroke();
      ctx.fillStyle = COLORS.gridText;
      ctx.font = "9px monospace";
      ctx.textAlign = "left";
      const label = timeUnit ? `${t}${timeUnit}` : String(t);
      ctx.fillText(label, x + 2, HEADER_H - 4);
    }

    if (waveform.timescale) {
      ctx.fillStyle = COLORS.labelDim;
      ctx.font = "9px monospace";
      ctx.textAlign = "right";
      const stepHint = Number(options.tickStep) > 0 ? ` · ${tickStep}${timeUnit || ""}` : "";
      ctx.fillText(`${waveform.timescale}${stepHint}`, canvasWidth - 6, HEADER_H - 4);
    }

    // Signal rows
    let rowTop = HEADER_H + PADDING;
    rows.forEach((row) => {
      const rowH = row.analog ? ANALOG_ROW_HEIGHT : ROW_HEIGHT;
      const y0 = rowTop + 3;
      const y1 = rowTop + rowH - 8;
      const mid = (y0 + y1) / 2;
      rowTop += rowH;

      // Row separator
      ctx.strokeStyle = "#252526";
      ctx.beginPath();
      ctx.moveTo(0, y0 - 3);
      ctx.lineTo(canvas.width, y0 - 3);
      ctx.stroke();

      // Label background
      ctx.fillStyle = "#252526";
      ctx.fillRect(0, y0 - 3, LABEL_WIDTH, rowH);

      // Label text
      ctx.fillStyle = row.analog ? COLORS.analog : row.width > 1 ? COLORS.bus : COLORS.label;
      ctx.font = "10px monospace";
      ctx.textAlign = "left";
      const shortName = row.name.length > 20 ? "…" + row.name.slice(-18) : row.name;
      ctx.fillText(shortName, 6, mid + 3);
      ctx.fillStyle = COLORS.labelDim;
      ctx.font = "9px monospace";
      ctx.textAlign = "right";
      if (row.analog) {
        ctx.fillText(row.kind === "real" ? "~real" : "~int", LABEL_WIDTH - 4, mid + 3);
      } else if (row.width > 1) {
        ctx.fillText(`[${row.width}]`, LABEL_WIDTH - 4, mid + 3);
      }

      if (row.analog) {
        drawAnalogWave(ctx, row, plotLeft, scale, y0, y1, maxTime);
        return;
      }

      const points = [];
      const times = new Set([0, maxTime]);
      row.changes.forEach(([t]) => times.add(t));
      const sorted = Array.from(times).sort((a, b) => a - b);

      for (const t of sorted) {
        const x = plotLeft + t * scale;
        const v = valueAt(row.changes, t);
        const level = signalLevel(v, row.width);
        points.push({ x, y: yForLevel(level, y0, y1), v, level });
      }

      if (row.width > 1) {
        drawBusWave(ctx, points, y0, y1, mid, row.width);
      } else {
        drawScalarWave(ctx, points, y0, y1);
      }
    });

    // Auto-scroll to end
    if (options.autoScroll && wrap) {
      wrap.scrollLeft = wrap.scrollWidth;
    }
  }

  global.HDLSimWaveform = {
    drawWaveform,
    buildRows,
    computeAutoTickStep,
    resolveTickStep,
    parseTimescaleUnit,
  };
})(typeof window !== "undefined" ? window : globalThis);
