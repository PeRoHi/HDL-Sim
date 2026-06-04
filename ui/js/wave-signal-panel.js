/**
 * Waveform signal picker — checkboxes, range select, drag reorder.
 */

/**
 * @param {HTMLElement} root
 * @param {{
 *   onChange: () => void,
 *   getSignalNames: () => string[],
 *   getSelection: () => string[],
 *   setSelection: (names: string[]) => void,
 *   getOrder: () => string[],
 *   setOrder: (names: string[]) => void,
 * }} hooks
 */
export function createWaveSignalPanel(root, hooks) {
  let anchorIndex = -1;
  let dragFrom = -1;

  root.innerHTML = `
    <div class="wave-panel-toolbar">
      <button type="button" data-act="all" class="mini-btn" title="すべて表示">全選択</button>
      <button type="button" data-act="none" class="mini-btn" title="表示をすべて解除">解除</button>
      <button type="button" data-act="invert" class="mini-btn" title="表示を反転">反転</button>
      <input type="search" class="wave-panel-filter" placeholder="信号名で絞り込み…" autocomplete="off" />
    </div>
    <p class="wave-panel-hint">Shift+クリックで範囲選択 · Ctrl+クリックで個別 · 左端をドラッグで並べ替え</p>
    <ul class="wave-signal-list" role="listbox" aria-multiselectable="true"></ul>
  `;

  const listEl = root.querySelector(".wave-signal-list");
  const filterEl = root.querySelector(".wave-panel-filter");

  function orderedNames() {
    const all = hooks.getSignalNames();
    const order = hooks.getOrder();
    if (!order.length) return all.slice();
    const set = new Set(all);
    const out = order.filter((n) => set.has(n));
    for (const n of all) {
      if (!out.includes(n)) out.push(n);
    }
    return out;
  }

  function visibleRows() {
    const q = (filterEl.value || "").trim().toLowerCase();
    const names = orderedNames();
    if (!q) return names;
    return names.filter((n) => n.toLowerCase().includes(q));
  }

  function selectionSet() {
    return new Set(hooks.getSelection());
  }

  function applySelection(names) {
    hooks.setSelection(names);
    hooks.onChange();
    render();
  }

  function applyOrder(names) {
    hooks.setOrder(names);
    hooks.onChange();
    render();
  }

  function rowIndex(name) {
    return orderedNames().indexOf(name);
  }

  function selectRange(from, to) {
    const names = orderedNames();
    const a = Math.min(from, to);
    const b = Math.max(from, to);
    const set = selectionSet();
    for (let i = a; i <= b; i++) set.add(names[i]);
    applySelection([...set]);
  }

  function render() {
    const names = visibleRows();
    const sel = selectionSet();
    listEl.innerHTML = "";
    if (!hooks.getSignalNames().length) {
      const li = document.createElement("li");
      li.className = "wave-signal-empty";
      li.textContent = "Run 後に信号一覧が表示されます";
      listEl.appendChild(li);
      return;
    }
    if (!names.length) {
      const li = document.createElement("li");
      li.className = "wave-signal-empty";
      li.textContent = "該当する信号がありません";
      listEl.appendChild(li);
      return;
    }

    names.forEach((name) => {
      const li = document.createElement("li");
      li.className = "wave-signal-row" + (sel.has(name) ? " selected" : "");
      li.dataset.name = name;
      li.draggable = true;

      const grip = document.createElement("span");
      grip.className = "wave-grip";
      grip.title = "ドラッグで並べ替え";
      grip.textContent = "⋮⋮";
      grip.draggable = false;

      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.className = "wave-cb";
      cb.checked = sel.has(name);
      cb.title = "波形に表示";

      const label = document.createElement("span");
      label.className = "wave-name";
      label.textContent = name;

      li.appendChild(grip);
      li.appendChild(cb);
      li.appendChild(label);

      cb.addEventListener("click", (e) => e.stopPropagation());
      cb.addEventListener("change", () => {
        const set = selectionSet();
        if (cb.checked) set.add(name);
        else set.delete(name);
        anchorIndex = rowIndex(name);
        applySelection([...set]);
      });

      li.addEventListener("click", (e) => {
        if (e.target.classList.contains("wave-grip")) return;
        const idx = rowIndex(name);
        if (e.shiftKey && anchorIndex >= 0) {
          selectRange(anchorIndex, idx);
          return;
        }
        if (e.ctrlKey || e.metaKey) {
          const set = selectionSet();
          if (set.has(name)) set.delete(name);
          else set.add(name);
          anchorIndex = idx;
          applySelection([...set]);
          return;
        }
        anchorIndex = idx;
        applySelection([name]);
      });

      li.addEventListener("dragstart", (e) => {
        dragFrom = rowIndex(name);
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", name);
        li.classList.add("dragging");
      });
      li.addEventListener("dragend", () => {
        li.classList.remove("dragging");
        dragFrom = -1;
        listEl.querySelectorAll(".drag-over").forEach((n) => n.classList.remove("drag-over"));
      });
      li.addEventListener("dragover", (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        li.classList.add("drag-over");
      });
      li.addEventListener("dragleave", () => li.classList.remove("drag-over"));
      li.addEventListener("drop", (e) => {
        e.preventDefault();
        li.classList.remove("drag-over");
        const fromName = e.dataTransfer.getData("text/plain");
        if (!fromName || fromName === name) return;
        const order = orderedNames();
        const from = order.indexOf(fromName);
        const to = order.indexOf(name);
        if (from < 0 || to < 0) return;
        order.splice(from, 1);
        order.splice(to, 0, fromName);
        applyOrder(order);
      });

      listEl.appendChild(li);
    });
  }

  root.querySelector(".wave-panel-toolbar").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-act]");
    if (!btn) return;
    const all = orderedNames();
    const act = btn.dataset.act;
    if (act === "all") {
      applySelection(all.slice());
      return;
    }
    if (act === "none") {
      applySelection([]);
      return;
    }
    if (act === "invert") {
      const set = selectionSet();
      applySelection(all.filter((n) => !set.has(n)));
    }
  });

  filterEl.addEventListener("input", () => render());

  return { render };
}
