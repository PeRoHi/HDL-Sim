/**
 * Multi-signal waveform renderer — VS Code / EDA style
 */
(function (global) {
  const ROW_HEIGHT = 24;
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
    cursor: "#007acc",
  };

  function buildRows(waveform) {
    if (!waveform?.signals) return [];
    return waveform.signals.map((sig) => ({
      name: sig.name,
      width: sig.width,
      changes: sig.changes || [],
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

  function drawWaveform(canvas, waveform, options = {}) {
    const rows = buildRows(waveform);
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
    const viewWidth = Math.max(wrap?.clientWidth || 400, 400);
    const plotWidth = viewWidth - LABEL_WIDTH - PADDING * 2;
    const bodyHeight = rows.length * ROW_HEIGHT + PADDING;
    const height = bodyHeight + HEADER_H + PADDING;
    canvas.width = viewWidth;
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

    const tickStep = Math.max(1, Math.pow(10, Math.floor(Math.log10(maxTime || 1))));
    for (let t = 0; t <= maxTime; t += tickStep) {
      const x = plotLeft + t * scale;
      ctx.beginPath();
      ctx.moveTo(x, HEADER_H);
      ctx.lineTo(x, height);
      ctx.stroke();
      ctx.fillStyle = COLORS.gridText;
      ctx.font = "9px monospace";
      ctx.textAlign = "left";
      ctx.fillText(String(t), x + 2, HEADER_H - 4);
    }

    if (waveform.timescale) {
      ctx.fillStyle = COLORS.labelDim;
      ctx.font = "9px monospace";
      ctx.textAlign = "right";
      ctx.fillText(waveform.timescale, viewWidth - 6, HEADER_H - 4);
    }

    // Signal rows
    rows.forEach((row, index) => {
      const y0 = HEADER_H + PADDING + index * ROW_HEIGHT + 3;
      const y1 = y0 + ROW_HEIGHT - 8;
      const mid = (y0 + y1) / 2;

      // Row separator
      ctx.strokeStyle = "#252526";
      ctx.beginPath();
      ctx.moveTo(0, y0 - 3);
      ctx.lineTo(canvas.width, y0 - 3);
      ctx.stroke();

      // Label background
      ctx.fillStyle = "#252526";
      ctx.fillRect(0, y0 - 3, LABEL_WIDTH, ROW_HEIGHT);

      // Label text
      ctx.fillStyle = row.width > 1 ? COLORS.bus : COLORS.label;
      ctx.font = "10px monospace";
      ctx.textAlign = "left";
      const shortName = row.name.length > 20 ? "…" + row.name.slice(-18) : row.name;
      ctx.fillText(shortName, 6, mid + 3);
      if (row.width > 1) {
        ctx.fillStyle = COLORS.labelDim;
        ctx.font = "9px monospace";
        ctx.textAlign = "right";
        ctx.fillText(`[${row.width}]`, LABEL_WIDTH - 4, mid + 3);
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

      // Draw waveform
      ctx.lineWidth = row.width > 1 ? 1.5 : 2;
      for (let i = 0; i < points.length; i++) {
        const p = points[i];
        const color = colorForLevel(p.level);
        ctx.strokeStyle = color;
        ctx.fillStyle = color;

        if (i > 0) {
          const prev = points[i - 1];
          ctx.beginPath();
          ctx.moveTo(prev.x, prev.y);
          ctx.lineTo(p.x, prev.y);
          ctx.lineTo(p.x, p.y);
          ctx.stroke();
        }

        // Bus / multi-bit: show value text at transitions
        if (row.width > 1 && p.v && p.v !== "0" && p.v !== "1") {
          const nextX = i < points.length - 1 ? points[i + 1].x : plotLeft + maxTime * scale;
          const segW = nextX - p.x;
          if (segW > 18) {
            ctx.font = "9px monospace";
            ctx.textAlign = "center";
            ctx.fillStyle = COLORS.bus;
            ctx.fillText(p.v, p.x + segW / 2, mid - 2);
          }
        }
      }
    });

    // Auto-scroll to end
    if (options.autoScroll && wrap) {
      wrap.scrollLeft = wrap.scrollWidth;
    }
  }

  global.HDLSimWaveform = { drawWaveform, buildRows };
})(typeof window !== "undefined" ? window : globalThis);
