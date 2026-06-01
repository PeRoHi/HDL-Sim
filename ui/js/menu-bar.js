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
        { type: "recent" },
        { type: "sep" },
        { id: "file.exit", label: "Exit" },
      ],
    },
    edit: { label: "Edit", items: [] },
    view: { label: "View", items: [] },
    project: { label: "Project", items: [] },
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
  let getRecentFiles = () => [];
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

  function renderDropdown(menuId, anchor) {
    const def = MENU_DEFS[menuId];
    if (!def || !dropdownEl) return;

    dropdownEl.innerHTML = "";
    const items = def.items || [];

    if (!items.length) {
      const empty = document.createElement("div");
      empty.className = "menu-item disabled";
      empty.textContent = "(準備中)";
      dropdownEl.appendChild(empty);
    } else {
      items.forEach((item) => {
        if (item.type === "sep") {
          const sep = document.createElement("div");
          sep.className = "menu-sep";
          sep.setAttribute("role", "separator");
          dropdownEl.appendChild(sep);
          return;
        }
        if (item.type === "recent") {
          const recent = getRecentFiles();
          if (!recent.length) {
            const row = document.createElement("div");
            row.className = "menu-item disabled";
            row.textContent = "(最近のファイルなし)";
            dropdownEl.appendChild(row);
            return;
          }
          recent.forEach((name, index) => {
            const row = document.createElement("button");
            row.type = "button";
            row.className = "menu-item";
            row.dataset.action = "file.recent";
            row.dataset.filename = name;
            row.innerHTML = `<span class="menu-label">${index + 1} ${name}</span>`;
            dropdownEl.appendChild(row);
          });
          return;
        }

        const row = document.createElement("button");
        row.type = "button";
        row.className = "menu-item" + (item.disabled ? " disabled" : "");
        row.dataset.action = item.id;
        row.disabled = !!item.disabled;
        row.innerHTML =
          `<span class="menu-label">${item.label}</span>` +
          (item.shortcut ? `<span class="menu-shortcut">${item.shortcut}</span>` : "");
        dropdownEl.appendChild(row);
      });
    }

    const rect = anchor.getBoundingClientRect();
    dropdownEl.style.left = `${rect.left}px`;
    dropdownEl.style.top = `${rect.bottom}px`;
    dropdownEl.hidden = false;
    openMenuId = menuId;
    anchor.classList.add("active");
  }

  function openMenu(menuId, anchor) {
    renderDropdown(menuId, anchor);
  }

  function runAction(actionId, el) {
    if (!actionId || actionId === "file.recent") {
      const filename = el?.dataset?.filename;
      if (filename && actions["file.recent"]) actions["file.recent"](filename);
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
    getRecentFiles = config.getRecentFiles || (() => []);
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
