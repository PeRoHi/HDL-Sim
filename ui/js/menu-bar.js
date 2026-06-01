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
        { id: "file.print", label: "Print...", shortcut: "Ctrl+P", disabled: true },
        { id: "file.print-preview", label: "Print Preview", disabled: true },
        { id: "file.print-setup", label: "Print Setup...", disabled: true },
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
        { id: "view.main-toolbar", label: "Main Toolbar", checkKey: "view.main-toolbar" },
        { id: "view.analyzer-toolbar", label: "Analyzer Toolbar", checkKey: "view.analyzer-toolbar" },
        { id: "view.fsm-toolbar", label: "FSM Toolbar", checkKey: "view.fsm-toolbar" },
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
        { id: "project.save-state", label: "Save Project State", disabled: true },
        { id: "project.restore-state", label: "Restore Project State" },
        { type: "sep" },
        { id: "project.reload-files", label: "Load/Reload Input Files", shortcut: "Ctrl+L" },
        { id: "project.reload-go", label: "Reload and Go", shortcut: "Alt+F5", disabled: true },
        { type: "sep" },
        { id: "project.settings", label: "Project Settings..." },
        { id: "project.filters", label: "Filters..." },
        { id: "project.list-size", label: "Project List Size..." },
        { type: "sep" },
        { type: "recent", recentKey: "projectRecent" },
      ],
    },
    "code-coverage": { label: "Code Coverage", items: [] },
    debug: { label: "Debug", items: [] },
    "state-machine": { label: "State Machine", items: [] },
    explorer: { label: "Explorer", items: [] },
    reports: { label: "Reports", items: [] },
    options: { label: "Options", items: [] },
    window: { label: "Window", items: [] },
    help: { label: "Help", items: [] },
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

    if (!items.length) {
      const empty = document.createElement("div");
      empty.className = "menu-item disabled";
      empty.textContent = "(準備中)";
      dropdownEl.appendChild(empty);
    } else {
      items.forEach((item) => {
        dropdownEl.appendChild(renderMenuRow(item, ctx));
      });
    }

    const rect = anchor.getBoundingClientRect();
    const padL = parseFloat(getComputedStyle(anchor).paddingLeft) || 0;
    dropdownEl.style.left = `${rect.left + padL}px`;
    dropdownEl.style.top = `${rect.bottom}px`;
    dropdownEl.hidden = false;
    openMenuId = menuId;
    anchor.classList.add("active");
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
