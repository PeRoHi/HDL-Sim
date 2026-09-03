/**
 * Per-project waveform selection and display order persistence.
 */

const WAVE_PREFS_LS_KEY = "hdl-sim-wave-prefs-v1";
const WAVE_VIEW_LS_KEY = "hdl-sim-wave-view-v1";

/** @typedef {{ selection: string[], order: string[], filePaths?: string[], analogSignals?: string[] }} WavePrefs */

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

  const analogSignals = Array.isArray(saved?.analogSignals)
    ? saved.analogSignals.filter((name) => avail.has(name))
    : [];
  return { selection, order, analogSignals };
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
    analogSignals: Array.isArray(entry.analogSignals) ? entry.analogSignals.slice() : [],
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
    analogSignals: prefs.analogSignals ? prefs.analogSignals.slice() : undefined,
  };
  writeWavePrefsStore(store);
}

/**
 * @param {object} wave from project meta or .spj
 * @returns {WavePrefs | null}
 */
/** @typedef {{ tickStep: number }} WaveViewSettings */

/** @returns {WaveViewSettings} */
export function loadWaveViewSettings() {
  try {
    const raw = localStorage.getItem(WAVE_VIEW_LS_KEY);
    if (!raw) return { tickStep: 0 };
    const data = JSON.parse(raw);
    const step = Number(data?.tickStep);
    return { tickStep: Number.isFinite(step) && step > 0 ? step : 0 };
  } catch {
    return { tickStep: 0 };
  }
}

/** @param {WaveViewSettings} settings */
export function saveWaveViewSettings(settings) {
  const step = Number(settings?.tickStep);
  localStorage.setItem(
    WAVE_VIEW_LS_KEY,
    JSON.stringify({ tickStep: Number.isFinite(step) && step > 0 ? step : 0 }),
  );
}

export function wavePrefsFromProjectPayload(wave) {
  if (!wave || typeof wave !== "object") return null;
  return {
    selection: Array.isArray(wave.selection) ? wave.selection.slice() : [],
    order: Array.isArray(wave.order) ? wave.order.slice() : [],
    filePaths: Array.isArray(wave.filePaths) ? wave.filePaths.slice() : undefined,
    analogSignals: Array.isArray(wave.analogSignals) ? wave.analogSignals.slice() : [],
  };
}
