/**
 * Per-project waveform selection and display order persistence.
 */

const WAVE_PREFS_LS_KEY = "hdl-sim-wave-prefs-v1";

/** @typedef {{ selection: string[], order: string[], filePaths?: string[] }} WavePrefs */

/**
 * @param {string[]} available
 * @param {WavePrefs | null | undefined} saved
 * @returns {WavePrefs}
 */
export function mergeWavePrefsWithSignals(available, saved) {
  const list = available.slice();
  if (!saved) {
    return { selection: list.slice(), order: list.slice() };
  }

  const avail = new Set(list);
  const order = [];
  for (const name of saved.order || []) {
    if (avail.has(name)) order.push(name);
  }
  for (const name of list) {
    if (!order.includes(name)) order.push(name);
  }

  let selection;
  if (Array.isArray(saved.selection)) {
    selection = order.filter((name) => saved.selection.includes(name));
  } else {
    selection = list.slice();
  }

  return { selection, order };
}

export function readWavePrefsStore() {
  try {
    const raw = localStorage.getItem(WAVE_PREFS_LS_KEY);
    if (!raw) return {};
    const data = JSON.parse(raw);
    return data && typeof data === "object" ? data : {};
  } catch {
    return {};
  }
}

export function writeWavePrefsStore(store) {
  localStorage.setItem(WAVE_PREFS_LS_KEY, JSON.stringify(store));
}

/**
 * @param {string} key
 * @returns {WavePrefs | null}
 */
export function loadWavePrefsForKey(key) {
  if (!key) return null;
  const store = readWavePrefsStore();
  const entry = store[key];
  if (!entry || typeof entry !== "object") return null;
  return {
    selection: Array.isArray(entry.selection) ? entry.selection.slice() : [],
    order: Array.isArray(entry.order) ? entry.order.slice() : [],
    filePaths: Array.isArray(entry.filePaths) ? entry.filePaths.slice() : undefined,
  };
}

/**
 * @param {string} key
 * @param {WavePrefs} prefs
 */
export function saveWavePrefsForKey(key, prefs) {
  if (!key) return;
  const store = readWavePrefsStore();
  store[key] = {
    selection: prefs.selection.slice(),
    order: prefs.order.slice(),
    filePaths: prefs.filePaths ? prefs.filePaths.slice() : undefined,
  };
  writeWavePrefsStore(store);
}

/**
 * @param {object} wave from project meta or .spj
 * @returns {WavePrefs | null}
 */
export function wavePrefsFromProjectPayload(wave) {
  if (!wave || typeof wave !== "object") return null;
  return {
    selection: Array.isArray(wave.selection) ? wave.selection.slice() : [],
    order: Array.isArray(wave.order) ? wave.order.slice() : [],
    filePaths: Array.isArray(wave.filePaths) ? wave.filePaths.slice() : undefined,
  };
}
