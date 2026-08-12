/**
 * index.js — the explorer's controller.
 *
 * Owns the map and the state; everything else is a pure-ish module it calls.
 * The state is small enough to keep in one object and rebuild the view from,
 * which is worth more here than incremental updates: screengrid takes its data
 * at construction, so most changes are a layer rebuild anyway.
 */

import { LEVELS, LEVEL_BY_ID, FILTERS, FILTER_DEFAULTS, MEASURES, PROFILE } from "./measures.js";
import { loadBoundaries, loadLevel, loadManifest, loadPoints } from "./data.js";
import { identity, makeSpec, summarizeCell } from "./glyph.js";
import {
  BOUNDARY_FILL,
  BOUNDARY_LINE,
  GLYPH_LAYER,
  POINTS_LAYER,
  createAnchorLayer,
  createGridLayer,
  removeBoundaries,
  removeGlyphs,
  removePoints,
  setBoundaries,
  setBoundarySelection,
  setPoints,
} from "./layers.js";
import * as ui from "./ui.js";

const els = {
  map: document.getElementById("map"),
  rail: document.getElementById("rail"),
  tip: document.getElementById("tip"),
  inspector: document.getElementById("inspector"),
  status: document.getElementById("status"),
};

const state = {
  level: "grid",
  mode: "profile",
  measure: "road_far",
  family: "road",
  stretch: false,
  cellSizePixels: 52,
  showPoints: false,
  showBoundaries: true,
  filters: { ...FILTER_DEFAULTS },

  rows: [],
  filtered: [],
  levels: new Map(), // levelId -> FeatureCollection of anchors
  counts: {},
  national: null,
  stats: null,
  glyphLayer: null,
  selection: null,
};

const map = new maplibregl.Map({
  container: "map",
  style: "https://tiles.openfreemap.org/styles/positron",
  center: [117.5, -2.2],
  zoom: 4.3,
  minZoom: 3.4,
  attributionControl: { compact: true },
});
// Both bottom: the top-right corner belongs to the inspector, which is the one
// panel that appears without being asked for and must not land on the zoom
// buttons when it does.
map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
map.addControl(new maplibregl.ScaleControl({ maxWidth: 110, unit: "metric" }), "bottom-left");

/**
 * Bring Positron into the report's palette.
 *
 * Positron's cool greys are a fine general-purpose basemap and a poor backdrop
 * for this one: the glyphs are warm ochres and reds on cream chrome, and a
 * blue-grey sea makes the page look like two publications stapled together.
 * Retinting land and water to the paper family costs three paint properties and
 * makes the map belong to the article around it.
 *
 * Contrast between land and water is kept wide enough to read a coastline
 * without the sea competing with the data — which is the one thing a basemap
 * under 83.000 glyphs must not do.
 */
function tintBasemap() {
  const tints = [
    ["background", "background-color", "#f7f4ed"],
    ["water", "fill-color", "#dfd9cc"],
    ["waterway", "line-color", "#cfc8b9"],
    ["park", "fill-color", "#eeeee2"],
    ["landcover_wood", "fill-color", "#e9e9dc"],
    ["landuse_residential", "fill-color", "#efece3"],
  ];
  for (const [layer, prop, value] of tints) {
    // Styles change upstream; a missing layer should tint what it can and move
    // on rather than take the map down.
    if (map.getLayer(layer)) map.setPaintProperty(layer, prop, value);
  }
}

// ---------------------------------------------------------------------------
// Derived state
// ---------------------------------------------------------------------------

/** Which measures and families the current glyph mode needs computed. */
function currentSpec() {
  if (state.mode === "composition") return makeSpec("composition", [], state.family);
  if (state.mode === "measure")
    return makeSpec("measure", [state.measure], null, state.stretch);
  return makeSpec("profile", PROFILE, null);
}

function activeFilters() {
  const preds = [];
  for (const f of FILTERS) {
    const opt = f.options.find((o) => o.value === state.filters[f.id]);
    if (opt?.test) preds.push(opt.test);
  }
  return preds;
}

/** Filters that differ from their default, for the badge on the disclosure. */
function changedFilterCount() {
  return FILTERS.reduce(
    (n, f) => n + (state.filters[f.id] === FILTER_DEFAULTS[f.id] ? 0 : 1),
    0,
  );
}

function applyFilters() {
  const preds = activeFilters();
  state.filtered = preds.length
    ? state.rows.filter((r) => preds.every((p) => p(r)))
    : state.rows;
  state.counts.grid = state.filtered.length;
}

// ---------------------------------------------------------------------------
// View
// ---------------------------------------------------------------------------

/** Keep the painting order: boundaries, then points, then glyphs on top. */
function restack() {
  for (const id of [BOUNDARY_FILL, BOUNDARY_LINE, POINTS_LAYER, GLYPH_LAYER]) {
    if (map.getLayer(id)) map.moveLayer(id);
  }
}

async function rebuildGlyphs() {
  removeGlyphs(map, state.glyphLayer);
  state.glyphLayer = null;

  const level = LEVEL_BY_ID[state.level];
  const spec = currentSpec();

  if (level.kind === "grid") {
    state.glyphLayer = createGridLayer({
      rows: state.filtered,
      spec,
      cellSizePixels: state.cellSizePixels,
      onStats: onStats,
      onHover: onHover,
      onClick: onClick,
    });
  } else {
    const collection = await ensureLevel(state.level);
    state.glyphLayer = createAnchorLayer({
      collection,
      spec,
      // Provinsi has 38 glyphs over the whole country and can afford to be
      // large; kecamatan has 7.235 and would turn into a solid sheet at that
      // size, so the envelope shrinks as the unit gets finer. These are sized
      // against Java, where the anchors are closest together — anywhere else
      // has room to spare.
      maxPx: level.id === "provinsi" ? 70 : level.id === "kabupaten" ? 42 : 30,
      // Profile mode draws every glyph at this one size. Smaller than the
      // envelope above, because nothing shrinks any more: what was the size of
      // the largest few areas would now be the size of all of them.
      uniformPx: level.id === "provinsi" ? 52 : level.id === "kabupaten" ? 32 : 22,
      onStats: onStats,
      onHover: onHover,
      onClick: onClick,
    });
  }

  map.addLayer(state.glyphLayer);
  restack();
}

async function ensureLevel(levelId) {
  if (!state.levels.has(levelId)) {
    state.levels.set(levelId, await loadLevel(levelId));
  }
  return state.levels.get(levelId);
}

async function syncBoundaries() {
  const level = LEVEL_BY_ID[state.level];
  const wanted = state.showBoundaries && level.kind === "admin";
  if (!wanted) {
    removeBoundaries(map);
    ui.setBoundaryNote(
      els.rail,
      level.kind === "grid"
        ? "Batas wilayah muncul saat skala kecamatan ke atas dipilih."
        : "",
    );
    return;
  }
  try {
    ui.setBoundaryNote(els.rail, "Memuat batas wilayah…");
    const geo = await loadBoundaries(state.level);
    // The level can change while an 8 MB fetch is in flight; dropping a stale
    // response is cheaper than cancelling and keeps the map consistent.
    if (state.level !== level.id || !state.showBoundaries) return;
    setBoundaries(map, geo, { selectedId: state.selection });
    restack();
    const missing = (state.counts[level.id] ?? 0) - geo.features.length;
    ui.setBoundaryNote(
      els.rail,
      missing > 0
        ? `${missing} wilayah tidak punya poligon yang cocok — gliph-nya tetap tampil.`
        : "",
    );
  } catch (err) {
    removeBoundaries(map);
    ui.setBoundaryNote(els.rail, `Batas wilayah gagal dimuat: ${err.message}`);
  }
}

function syncPoints() {
  if (!state.showPoints) return removePoints(map);
  setPoints(map, state.filtered);
  restack();
}

async function render() {
  ui.updateLadder(els.rail, state.level, state.counts);
  ui.updateModes(els.rail, state.mode);
  ui.setCellSizeVisible(els.rail, LEVEL_BY_ID[state.level].kind === "grid");
  ui.updateFilterBadge(els.rail, changedFilterCount(), LEVEL_BY_ID[state.level].kind === "grid");
  ui.updateCount(els.rail, state.filtered.length);
  await rebuildGlyphs();
  await syncBoundaries();
  syncPoints();
  refreshLegend();
}

function onStats(stats) {
  state.stats = stats;
  refreshLegend();
}

/**
 * Whether the current scale's glyphs are packed tighter than they can be read.
 *
 * `minzoom` on a level is not a hard cut-off — the national kecamatan view is a
 * legitimate thing to look at, and its east-west gradient is one of the clearer
 * pictures the map produces. It just cannot be read glyph by glyph, so the
 * legend says so instead of the map pretending otherwise.
 */
function refreshLegend() {
  const level = LEVEL_BY_ID[state.level];
  ui.renderLegend(
    els.rail,
    {
      ...state,
      levelLabel: level.label,
      tooDense: level.minzoom != null && map.getZoom() < level.minzoom,
    },
    state.stats,
    state.national,
  );
}

// ---------------------------------------------------------------------------
// Interaction
// ---------------------------------------------------------------------------

function onHover(payload, event) {
  if (!payload) return ui.hideTip(els.tip);
  ui.showTip(els.tip, payload, event, state);
  map.getCanvas().style.cursor = "pointer";
}

function onClick(payload) {
  ui.hideTip(els.tip);
  if (!payload) return closeInspector();

  state.selection = payload.kind === "admin" ? payload.props.admin_id : null;
  setBoundarySelection(map, state.selection);

  ui.renderInspector(
    els.inspector,
    payload,
    { ...state, levelLabel: LEVEL_BY_ID[state.level].label },
    state.national,
    closeInspector,
    payload.kind === "admin" ? () => drillInto(payload.props) : null,
  );
}

function closeInspector() {
  ui.hideInspector(els.inspector);
  state.selection = null;
  setBoundarySelection(map, null);
}

/**
 * Step one rung down the ladder, centred on the area just inspected. This is
 * what makes the scale switch feel like navigation rather than a mode toggle:
 * you pick a province off the national view, and the map hands you its
 * kabupaten.
 */
function drillInto(props) {
  const order = LEVELS.filter((l) => l.kind === "admin").map((l) => l.id);
  const i = order.indexOf(state.level);
  const next = i > 0 ? order[i - 1] : "grid";
  const zoom = next === "kabupaten" ? 7.2 : next === "kecamatan" ? 9 : 10.5;
  map.easeTo({ center: [props.anchor_lon, props.anchor_lat], zoom, duration: 700 });
  closeInspector();
  setLevel(next);
}

function setLevel(levelId) {
  if (state.level === levelId) return;
  state.level = levelId;
  closeInspector();
  render();
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

function status(message, isError = false) {
  if (!message) {
    els.status.hidden = true;
    return;
  }
  els.status.hidden = false;
  els.status.textContent = message;
  els.status.classList.toggle("is-error", isError);
}

/** One handler table, shared by the rail and by the mode-detail sub-control. */
const handlers = {
  level: setLevel,
  mode: (mode) => {
    state.mode = mode;
    ui.renderModeDetail(els.rail, state, handlers);
    render();
  },
  measure: (measure) => {
    state.measure = measure;
    ui.renderModeDetail(els.rail, state, handlers);
    render();
  },
  family: (family) => {
    state.family = family;
    ui.renderModeDetail(els.rail, state, handlers);
    render();
  },
  stretch: (on) => {
    state.stretch = on;
    render();
  },
};

async function boot() {
  tintBasemap();
  ui.renderRail(els.rail, {
    ...handlers,
    cellSize: (px) => {
      state.cellSizePixels = px;
      // A slider drag is the one interaction fast enough to need the in-place
      // update rather than a rebuild.
      state.glyphLayer?.setConfig?.({ cellSizePixels: px });
      map.triggerRepaint();
    },
    points: (on) => {
      state.showPoints = on;
      syncPoints();
    },
    boundaries: (on) => {
      state.showBoundaries = on;
      syncBoundaries();
    },
    filters: (filters) => {
      state.filters = filters;
      applyFilters();
      render();
    },
  });
  ui.renderModeDetail(els.rail, state, handlers);

  try {
    status("Memuat data koperasi…");
    const [manifest, rows] = await Promise.all([loadManifest(), loadPoints()]);
    state.rows = rows;
    ui.renderFoot(els.rail, manifest);

    // Scale cardinalities come from the manifest, which the mart builder writes
    // — one source of truth for "how many kecamatan are there", and it moves
    // when the data does.
    for (const level of LEVELS) {
      if (level.kind === "grid") continue;
      const schema = manifest.schema?.[level.table];
      state.counts[level.id] = (schema?.rows ?? 0) - (schema?.rows_without_anchor ?? 0);
    }

    applyFilters();

    // National baselines for the legend and inspector, over every cooperative
    // and through the same summariser the glyphs use.
    state.national = summarizeCell(
      state.rows,
      makeSpec("profile", MEASURES.map((m) => m.id), null),
      identity,
    );
    for (const fam of ["road", "pop", "nn"]) {
      const s = summarizeCell(state.rows, makeSpec("composition", [], fam), identity);
      Object.assign(state.national.shares, s.shares);
    }

    status(null);
    await render();
  } catch (err) {
    status(`Gagal memuat data: ${err.message}`, true);
    throw err;
  }
}

map.on("load", boot);
// The density warning depends on zoom, and the grid layer reports its own stats
// on every aggregation — so only the admin layers need this.
map.on("zoomend", () => {
  if (LEVEL_BY_ID[state.level].kind === "admin") refreshLegend();
});
map.getCanvasContainer().addEventListener("mouseleave", () => {
  ui.hideTip(els.tip);
  map.getCanvas().style.cursor = "";
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeInspector();
});
