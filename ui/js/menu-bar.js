/**
 * Silos-style top menu bar with hover-to-switch dropdowns.
 */
(function (global) {
  const MENU_DEFS = {
    file: {
      label: "File",
      items: [
        { id: "file.new", label: "New", shortcut: "Ctrl+N" },
        { id: "file.open", label: "Open...", shortcut: "Ctrl+O" },
        { id: "file.save", label: "Save", shortcut: "Ctrl+S" },
        { id: "file.save-as", label: "Save As..." },
        { type: "sep" },
        { type: "recent", recentKey: "fileRecent" },
        { type: "sep" },
        { id: "file.exit", label: "Exit" },
      ],
    },
    edit: {
      label: "Edit",
      items: [
        { id: "edit.undo", label: "Undo", shortcut: "Ctrl+Z" },
        { type: "sep" },
        { id: "edit.cut", label: "Cut", shortcut: "Ctrl+X", disabledKey: "edit.cut" },
        { id: "edit.copy", label: "Copy", shortcut: "Ctrl+C", disabledKey: "edit.copy" },
        { id: "edit.paste", label: "Paste", shortcut: "Ctrl+V" },
        { id: "edit.clear", label: "Clear", shortcut: "Del", disabledKey: "edit.clear" },
        { id: "edit.select-all", label: "Select All", shortcut: "Ctrl+A" },
        { type: "sep" },
        { id: "edit.find", label: "Find...", shortcut: "Ctrl+F" },
        { id: "edit.find-next", label: "Find Next", shortcut: "F3", disabledKey: "edit.find-next" },
        { id: "edit.replace", label: "Replace...", shortcut: "Ctrl+H" },
        { id: "edit.goto-line", label: "Goto Line...", shortcut: "Ctrl+G" },
      ],
    },
    view: {
      label: "View",
      items: [
        { id: "view.zoom-in", label: "Zoom In", shortcut: "Ctrl+=" },
        { id: "view.zoom-out", label: "Zoom Out", shortcut: "Ctrl+-" },
        { id: "view.zoom-reset", label: "Reset Zoom", shortcut: "Ctrl+Numpad0" },
        { type: "sep" },
        { id: "view.main-toolbar", label: "Main Toolbar", checkKey: "view.main-toolbar" },
        { id: "view.output-panel", label: "Output Panel", checkKey: "view.output-panel" },
        { id: "view.project-bar", label: "Project Bar", checkKey: "view.project-bar" },
      ],
    },
    project: {
      label: "Project",
      items: [
        { id: "project.new", label: "New..." },
        { id: "project.open", label: "Open..." },
        { id: "project.files", label: "Files...", hintKey: "currentSpj" },
        { id: "project.save-as", label: "Save As..." },
        { id: "project.close", label: "Close" },
        { type: "sep" },
        { id: "project.reload-files", label: "Load/Reload Input Files", shortcut: "Ctrl+L" },
        { id: "project.settings", label: "Project Settings..." },
        { type: "sep" },
        { type: "recent", recentKey: "projectRecent" },
      ],
    },
    debug: {
      label: "Debug",
      items: [
        { id: "debug.single-step", label: "Enable Single Step/Breakpoints", checkKey: "debug.single-step" },
        { type: "sep" },
        { id: "debug.go", label: "Go", shortcut: "F5" },
        { id: "debug.break", label: "Break Simulation", shortcut: "Esc", disabledKey: "debug.break" },
        { id: "debug.finish", label: "Finish Current Timepoint", disabledKey: "debug.finish" },
        { id: "debug.restart", label: "Restart Simulation", shortcut: "Shift+F5", disabledKey: "debug.restart" },
        { type: "sep" },
        { id: "debug.step", label: "Step", shortcut: "F10", disabledKey: "debug.step" },
        { type: "sep" },
        { id: "debug.breakpoints", label: "Breakpoints...", shortcut: "Ctrl+B", disabled: true },
      ],
    },
    window: {
      label: "Window",
      items: [
        { id: "window.cascade", label: "Cascade" },
        { id: "window.tile", label: "Tile" },
        { id: "window.arrange-icons", label: "Arrange Icons", disabled: true },
        { type: "sep" },
        { id: "window.waveform", label: "Open Waveform", shortcut: "F6" },
        { type: "sep" },
        { type: "window-files" },
      ],
    },
    help: {
      label: "Help",
      items: [
        { id: "help.tutorial", label: "チュートリアルを表示" },
        { type: "sep" },
        { id: "help.guide", label: "使い方..." },
        { type: "sep" },
        { id: "help.about", label: "About HDL-Sim..." },
      ],
    },
  };

  let actions = {};
  let getMenuContext = () => ({});
  let openMenuId = null;
  let barEl = null;
  let dropdownEl = null;

  function $(id) {
    return document.getElementById(id);
  }

  function closeMenu() {
    openMenuId = null;
    if (dropdownEl) dropdownEl.hidden = true;
    barEl?.classList.remove("menu-open");
    document.querySelectorAll(".menubar-btn").forEach((btn) => {
      btn.classList.remove("active");
    });
  }

  function isItemDisabled(item, ctx) {
    if (item.disabled) return true;
    if (item.disabledKey && ctx.disabled?.[item.disabledKey]) return true;
    return false;
  }

  function renderMenuRow(item, ctx) {
    if (item.type === "sep") {
      const sep = document.createElement("div");
      sep.className = "menu-sep";
      sep.setAttribute("role", "separator");
      return sep;
    }

    if (item.type === "recent") {
      const key = item.recentKey || "fileRecent";
      const recent = ctx.recent?.[key] || [];
      const frag = document.createDocumentFragment();
      if (!recent.length) return frag;
      recent.forEach((name, index) => {
        const row = document.createElement("button");
        row.type = "button";
        row.className = "menu-item";
        row.dataset.action = key === "projectRecent" ? "project.recent" : "file.recent";
        row.dataset.filename = name;
        row.innerHTML = `<span class="menu-check"></span><span class="menu-label">${index + 1} ${name}</span>`;
        frag.appendChild(row);
      });
      return frag;
    }

    if (item.type === "window-files") {
      const files = ctx.windowFiles || [];
      const frag = document.createDocumentFragment();
      if (!files.length) {
        const row = document.createElement("div");
        row.className = "menu-item disabled";
        row.textContent = "(ウィンドウなし)";
        frag.appendChild(row);
        return frag;
      }
      files.forEach((entry, index) => {
        const row = document.createElement("button");
        row.type = "button";
        row.className = "menu-item";
        row.dataset.action = "window.open-file";
        row.dataset.path = entry.path;
        const checked = entry.path === ctx.activeWindow;
        row.innerHTML =
          `<span class="menu-check">${checked ? "✓" : ""}</span>` +
          `<span class="menu-label">${index + 1} ${entry.label}</span>`;
        frag.appendChild(row);
      });
      return frag;
    }

    const disabled = isItemDisabled(item, ctx);
    const row = document.createElement("button");
    row.type = "button";
    row.className = "menu-item" + (disabled ? " disabled" : "");
    row.dataset.action = item.id;
    row.disabled = disabled;

    const checked = item.checkKey && ctx.checked?.[item.checkKey];
    const hint = item.hintKey ? ctx.hints?.[item.hintKey] : "";

    row.innerHTML =
      `<span class="menu-check">${checked ? "✓" : ""}</span>` +
      `<span class="menu-label">${item.label}</span>` +
      (hint ? `<span class="menu-hint">${hint}</span>` : "") +
      (item.shortcut ? `<span class="menu-shortcut">${item.shortcut}</span>` : "");
    return row;
  }

  function renderDropdown(menuId, anchor) {
    const def = MENU_DEFS[menuId];
    if (!def || !dropdownEl) return;

    const ctx = getMenuContext();
    dropdownEl.innerHTML = "";
    const items = def.items || [];

    items.forEach((item) => {
      dropdownEl.appendChild(renderMenuRow(item, ctx));
    });

    const rect = anchor.getBoundingClientRect();
    const padL = parseFloat(getComputedStyle(anchor).paddingLeft) || 0;
    dropdownEl.style.left = `${rect.left + padL}px`;
    dropdownEl.style.top = `${rect.bottom}px`;
    dropdownEl.hidden = false;
    openMenuId = menuId;
    barEl?.classList.add("menu-open");
    document.querySelectorAll(".menubar-btn").forEach((btn) => {
      btn.classList.toggle("active", btn === anchor);
    });
  }

  function openMenu(menuId, anchor) {
    renderDropdown(menuId, anchor);
  }

  function runAction(actionId, el) {
    if (actionId === "file.recent" || actionId === "project.recent") {
      const filename = el?.dataset?.filename;
      const key = actionId === "project.recent" ? "project.recent" : "file.recent";
      if (filename && actions[key]) actions[key](filename);
      closeMenu();
      return;
    }
    if (actionId === "window.open-file") {
      const path = el?.dataset?.path;
      if (path && actions["window.open-file"]) actions["window.open-file"](path);
      closeMenu();
      return;
    }
    const fn = actions[actionId];
    closeMenu();
    if (typeof fn === "function") fn();
  }

  function bindMenuBar() {
    barEl = $("menubar");
    dropdownEl = $("menu-dropdown");
    if (!barEl || !dropdownEl) return;

    barEl.querySelectorAll(".menubar-btn").forEach((btn) => {
      const menuId = btn.dataset.menu;
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        if (openMenuId === menuId && !dropdownEl.hidden) {
          closeMenu();
        } else {
          openMenu(menuId, btn);
        }
      });
      btn.addEventListener("mouseenter", () => {
        if (openMenuId && openMenuId !== menuId) {
          openMenu(menuId, btn);
        }
      });
    });

    dropdownEl.addEventListener("click", (e) => {
      const item = e.target.closest(".menu-item");
      if (!item || item.disabled) return;
      runAction(item.dataset.action, item);
    });

    document.addEventListener("mousedown", (e) => {
      if (e.target.closest("#menubar") || e.target.closest("#menu-dropdown")) return;
      closeMenu();
    });

    window.addEventListener("resize", closeMenu);
    window.addEventListener("blur", closeMenu);
  }

  function init(config = {}) {
    actions = config.actions || {};
    getMenuContext = config.getMenuContext || (() => ({}));
    bindMenuBar();
  }

  function refresh() {
    if (openMenuId) {
      const btn = barEl?.querySelector(`.menubar-btn[data-menu="${openMenuId}"]`);
      if (btn) renderDropdown(openMenuId, btn);
    }
  }

  global.HDLSimMenuBar = { init, close: closeMenu, refresh };
})(typeof window !== "undefined" ? window : globalThis);
