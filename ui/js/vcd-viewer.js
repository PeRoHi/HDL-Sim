/**
 * Simple multi-signal waveform renderer from HDL-Sim JSON timeline.
 */
(function (global) {
  const ROW_HEIGHT = 28;
  const LABEL_WIDTH = 140;
  const PADDING = 8;

  function buildRows(waveform) {
    if (!waveform || !waveform.signals) return [];
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

  function drawWaveform(canvas, waveform, options) {
    const rows = buildRows(waveform);
    if (!rows.length) {
      const ctx = canvas.getContext("2d");
      canvas.width = 400;
      canvas.height = 80;
      ctx.fillStyle = "#16181c";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = "#9aa3b2";
      ctx.font = "12px sans-serif";
      ctx.fillText("実行後に波形が表示されます", 16, 40);
      return;
    }

    const maxTime = timeRange(rows);
    const wrap = options.wrap || canvas.parentElement;
    const viewWidth = Math.max(wrap.clientWidth, 400);
    const plotWidth = viewWidth - LABEL_WIDTH - PADDING * 2;
    const height = Math.max(rows.length * ROW_HEIGHT + PADDING * 2, 120);
    canvas.width = viewWidth;
    canvas.height = height;

    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#16181c";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const scale = plotWidth / Math.max(maxTime, 1);

    ctx.strokeStyle = "#2e3340";
    ctx.lineWidth = 1;
    for (let t = 0; t <= maxTime; t += Math.max(1, Math.floor(maxTime / 10))) {
      const x = LABEL_WIDTH + PADDING + t * scale;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
      ctx.fillStyle = "#6b7280";
      ctx.font = "10px monospace";
      ctx.fillText(String(t), x + 2, 10);
    }

    rows.forEach((row, index) => {
      const y0 = PADDING + index * ROW_HEIGHT + 4;
      const y1 = y0 + ROW_HEIGHT - 10;
      const mid = (y0 + y1) / 2;

      ctx.fillStyle = "#c5c8d4";
      ctx.font = "11px monospace";
      ctx.textAlign = "left";
      ctx.fillText(row.name, 8, mid + 4);

      const points = [];
      const times = new Set([0, maxTime]);
      row.changes.forEach(([t]) => times.add(t));
      const sorted = Array.from(times).sort((a, b) => a - b);

      for (const t of sorted) {
        const x = LABEL_WIDTH + PADDING + t * scale;
        const v = valueAt(row.changes, t);
        const high = v === "1" || (v !== "0" && v !== "x" && v !== "z" && parseInt(v, 2) > 0);
        points.push({ x, y: high ? y0 : y1, v });
      }

      ctx.strokeStyle = "#3d8bfd";
      ctx.lineWidth = 2;
      ctx.beginPath();
      points.forEach((p, i) => {
        if (i === 0) ctx.moveTo(p.x, p.y);
        else {
          ctx.lineTo(p.x, points[i - 1].y);
          ctx.lineTo(p.x, p.y);
        }
      });
      ctx.stroke();
    });
  }

  global.HDLSimWaveform = { drawWaveform, buildRows };
})(typeof window !== "undefined" ? window : globalThis);
