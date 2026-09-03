/**
 * FILES pane: tree view, drag-and-drop, context menu.
 */

const MODULE_RE = /\bmodule\s+([A-Za-z_]\w*)\s*(?:#\s*\(|;|\()/g;

export function scanModulesInWorkspace(fileStore, saveActiveEditor) {
  if (typeof saveActiveEditor === "function") saveActiveEditor();
  /** @type {{ name: string, path: string }[]} */
  const modules = [];
  const seen = new Set();
  for (const [path, entry] of fileStore) {
    const content = entry.model ? entry.model.getValue() : entry.content;
    MODULE_RE.lastIndex = 0;
    let match;
    while ((match = MODULE_RE.exec(content)) !== null) {
      const key = `${match[1]}@${path}`;
      if (!seen.has(key)) {
        seen.add(key);
        modules.push({ name: match[1], path });
      }
    }
  }
  modules.sort((a, b) => a.name.localeCompare(b.name) || a.path.localeCompare(b.path));
  return modules;
}

export function createWorkspaceTree(hooks) {
  const virtualFolders = new Set();
  let contextFolder = "";
  let contextTarget = null;
  let dragPath = null;
  let menuEl = null;

  function normalizeFolder(path) {
    return String(path || "")
      .trim()
      .replace(/\\/g, "/")
      .replace(/^\/+|\/+$/g, "");
  }

  function ensureVirtualFoldersFromPaths(fileStore) {
    for (const path of fileStore.keys()) {
      const parts = path.split("/");
      if (parts.length <= 1) continue;
      let acc = "";
      for (let i = 0; i < parts.length - 1; i++) {
        acc = acc ? `${acc}/${parts[i]}` : parts[i];
        virtualFolders.add(acc);
      }
    }
  }

  function buildFileTree(fileStore) {
    ensureVirtualFoldersFromPaths(fileStore);
    const root = { dirs: new Map(), files: [] };

    virtualFolders.forEach((folder) => {
      const parts = folder.split("/");
      let node = root;
      for (const part of parts) {
        if (!node.dirs.has(part)) node.dirs.set(part, { dirs: new Map(), files: [], path: "" });
        node = node.dirs.get(part);
        node.path = node.path ? `${node.path}/${part}` : part;
      }
    });

    for (const path of fileStore.keys()) {
      const parts = path.split("/");
      let node = root;
      for (let i = 0; i < parts.length - 1; i++) {
        const dir = parts[i];
        if (!node.dirs.has(dir)) node.dirs.set(dir, { dirs: new Map(), files: [], path: "" });
        node = node.dirs.get(dir);
        node.path = node.path ? `${node.path}/${dir}` : dir;
      }
      node.files.push(path);
    }
    return root;
  }

  function hideMenu() {
    if (menuEl) menuEl.hidden = true;
  }

  function showMenu(x, y, items) {
    if (!menuEl) {
      menuEl = document.createElement("div");
      menuEl.id = "file-tree-menu";
      menuEl.className = "tree-context-menu";
      menuEl.hidden = true;
      document.body.appendChild(menuEl);
      document.addEventListener("click", hideMenu);
      document.addEventListener("contextmenu", (e) => {
        if (!menuEl.contains(e.target)) hideMenu();
      });
    }
    menuEl.innerHTML = "";
    items.forEach((item) => {
      if (item.sep) {
        const sep = document.createElement("div");
        sep.className = "tree-menu-sep";
        menuEl.appendChild(sep);
        return;
      }
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "tree-menu-item" + (item.disabled ? " disabled" : "");
      btn.textContent = item.label;
      btn.disabled = !!item.disabled;
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        hideMenu();
        if (!item.disabled && item.action) item.action();
      });
      menuEl.appendChild(btn);
    });
    menuEl.style.left = `${x}px`;
    menuEl.style.top = `${y}px`;
    menuEl.hidden = false;
  }

  function openContextMenu(e, target) {
    e.preventDefault();
    e.stopPropagation();
    contextTarget = target;
    if (target.type === "folder") contextFolder = target.path;

    const items = [];
    const folder = target.type === "folder" ? target.path : contextFolder;

    items.push({
      label: "新規ファイル",
      action: () => hooks.onNewFile(folder),
    });
    items.push({
      label: "新規フォルダ",
      action: () => hooks.onNewFolder(folder),
    });
    items.push({ sep: true });

    if (target.type === "file") {
      items.push({
        label: "名前の変更",
        action: () => hooks.onRenameFile(target.path),
      });
      items.push({
        label: "削除",
        disabled: hooks.fileStore.size <= 1,
        action: () => hooks.onDeleteFile(target.path),
      });
    } else if (target.type === "folder" && target.path) {
      items.push({
        label: "フォルダ名の変更",
        action: () => hooks.onRenameFolder(target.path),
      });
      items.push({
        label: "フォルダを削除",
        action: () => hooks.onDeleteFolder(target.path),
      });
    }

    items.push({ sep: true });
    items.push({
      label: "更新",
      action: () => render(),
    });

    showMenu(e.clientX, e.clientY, items);
  }

  function setupDropTarget(row, folderPath) {
    row.addEventListener("dragover", (e) => {
      if (!dragPath) return;
      e.preventDefault();
      row.classList.add("drop-target");
    });
    row.addEventListener("dragleave", () => {
      row.classList.remove("drop-target");
    });
    row.addEventListener("drop", (e) => {
      e.preventDefault();
      row.classList.remove("drop-target");
      if (!dragPath) return;
      const name = dragPath.includes("/") ? dragPath.split("/").pop() : dragPath;
      const dest = folderPath ? `${folderPath}/${name}` : name;
      if (dest !== dragPath) hooks.onMovePath(dragPath, dest);
      dragPath = null;
    });
  }

  function renderFileTreeNode(parentEl, node, depth, fileStore) {
    const sortedDirs = [...node.dirs.keys()].sort();
    sortedDirs.forEach((dirName) => {
      const dirNode = node.dirs.get(dirName);
      const folderPath = dirNode.path || dirName;
      const row = document.createElement("div");
      row.className = "tree-node tree-folder" + (contextFolder === folderPath ? " selected" : "");
      row.style.paddingLeft = `${depth * 12 + 4}px`;
      row.dataset.folder = folderPath;
      row.innerHTML = `<span class="twist">▼</span><span class="icon">📁</span><span class="label">${dirName}</span>`;
      row.addEventListener("click", (e) => {
        if (e.target.classList.contains("twist")) return;
        contextFolder = folderPath;
        render();
      });
      row.addEventListener("contextmenu", (e) => {
        openContextMenu(e, { type: "folder", path: folderPath });
      });
      setupDropTarget(row, folderPath);
      parentEl.appendChild(row);

      const childWrap = document.createElement("div");
      childWrap.className = "tree-children";
      renderFileTreeNode(childWrap, dirNode, depth + 1, fileStore);
      parentEl.appendChild(childWrap);

      const twist = row.querySelector(".twist");
      twist.addEventListener("click", (e) => {
        e.stopPropagation();
        const collapsed = childWrap.classList.toggle("collapsed");
        twist.textContent = collapsed ? "▶" : "▼";
      });
    });

    node.files.sort().forEach((path) => {
      const isHidden = typeof hooks.isFileHidden === "function" && hooks.isFileHidden(path);
      const row = document.createElement("div");
      row.className = "tree-node tree-file"
        + (path === hooks.getActiveFile() ? " selected" : "")
        + (isHidden ? " file-hidden" : "");
      row.style.paddingLeft = `${depth * 12 + 4}px`;
      row.draggable = true;
      row.dataset.path = path;
      const name = path.includes("/") ? path.split("/").pop() : path;

      const twistSpan = document.createElement("span");
      twistSpan.className = "twist empty";
      row.appendChild(twistSpan);

      const iconSpan = document.createElement("span");
      iconSpan.className = "icon";
      iconSpan.textContent = "📄";
      row.appendChild(iconSpan);

      const labelSpan = document.createElement("span");
      labelSpan.className = "label";
      labelSpan.textContent = name;
      row.appendChild(labelSpan);

      // Visibility toggle icon
      if (typeof hooks.onToggleVisibility === "function") {
        const visBtn = document.createElement("span");
        visBtn.className = "file-vis-toggle";
        visBtn.textContent = isHidden ? "🙈" : "👁";
        visBtn.title = isHidden ? "ウィンドウを表示" : "ウィンドウを非表示";
        visBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          hooks.onToggleVisibility(path);
        });
        row.appendChild(visBtn);
      }

      row.title = path;
      row.addEventListener("click", () => {
        contextFolder = path.includes("/") ? path.split("/").slice(0, -1).join("/") : "";
        hooks.onOpenFile(path);
      });
      row.addEventListener("contextmenu", (e) => {
        openContextMenu(e, { type: "file", path });
      });
      row.addEventListener("dragstart", (e) => {
        dragPath = path;
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", path);
        row.classList.add("dragging");
      });
      row.addEventListener("dragend", () => {
        dragPath = null;
        row.classList.remove("dragging");
        document.querySelectorAll(".drop-target").forEach((el) => el.classList.remove("drop-target"));
      });
      parentEl.appendChild(row);
    });
  }

  function render() {
    const rootEl = hooks.getRootElement();
    if (!rootEl) return;
    rootEl.innerHTML = "";

    const header = document.createElement("div");
    header.className = "tree-node tree-folder" + (contextFolder === "" ? " selected" : "");
    header.innerHTML = `<span class="twist">▼</span><span class="icon">📁</span><span class="label">WORKSPACE</span>`;
    header.addEventListener("click", () => {
      contextFolder = "";
      render();
    });
    header.addEventListener("contextmenu", (e) => {
      openContextMenu(e, { type: "folder", path: "" });
    });
    setupDropTarget(header, "");
    rootEl.appendChild(header);

    const body = document.createElement("div");
    body.className = "tree-children";
    renderFileTreeNode(body, buildFileTree(hooks.fileStore), 0, hooks.fileStore);
    rootEl.appendChild(body);

    if (typeof hooks.onAfterRender === "function") hooks.onAfterRender();
  }

  function addVirtualFolder(folderPath) {
    const normalized = normalizeFolder(folderPath);
    if (!normalized) return false;
    virtualFolders.add(normalized);
    return true;
  }

  function removeVirtualFolderPrefix(prefix) {
    const normalized = normalizeFolder(prefix);
    if (!normalized) return;
    [...virtualFolders].forEach((f) => {
      if (f === normalized || f.startsWith(`${normalized}/`)) virtualFolders.delete(f);
    });
  }

  function getContextFolder() {
    return contextFolder;
  }

  function setContextFolder(folder) {
    contextFolder = normalizeFolder(folder);
  }

  return {
    render,
    addVirtualFolder,
    removeVirtualFolderPrefix,
    getContextFolder,
    setContextFolder,
    hideMenu,
  };
}
