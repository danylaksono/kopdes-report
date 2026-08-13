/**
 * index.js — the explorer's controller.
 *
 * Owns the map and the state; everything else is a pure-ish module it calls.
 * The state is small enough to keep in one object and rebuild the view from,
 * which is worth more here than incremental updates: screengrid takes its data
 * at construction, so most changes are a layer rebuild anyway.
 */

import {
  LEVELS,
  LEVEL_BY_ID,
  FILTERS,
  FILTER_DEFAULTS,
  MEASURES,
  PROFILE,
} from "./measures.js";
import { BASEMAPS, BASEMAP_BY_ID, tintBasemap } from "./basemaps.js";
import { loadBoundaries, loadLevel, loadManifest, loadPoints } from "./data.js";
import { identity, makeSpec, summarizeCell } from "./glyph.js";
import { buildIndex, search } from "./search.js";
import {
  BOUNDARY_FILL,
  BOUNDARY_LINE,
  GLYPH_LAYER,
  POINTS_LAYER,
  clearBoundaryState,
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
  search: document.getElementById("search"),
  basemaps: document.getElementById("basemaps"),
};

const state = {
  level: "grid",
  mode: "profile",
  measure: "road_far",
  family: "road",
  stretch: false,
  basemap: "terang",
  showGlyphs: true,
  showPoints: false,
  showBoundaries: true,
  filters: { ...FILTER_DEFAULTS },

  // One size per scale, so switching away and back does not lose the
  // adjustment. Seeded from each level's own `sizing.default`.
  sizePx: Object.fromEntries(LEVELS.map((l) => [l.id, l.sizing.default])),
  // Mutated in place and read on every draw, so dragging the slider on an
  // administrative scale does not rebuild the layer.
  sizing: { maxPx: 70, uniformPx: 52 },

  rows: [],
  filtered: [],
  index: [],
  levels: new Map(), // levelId -> FeatureCollection of anchors
  counts: {},
  national: null,
  stats: null,
  glyphLayer: null,
  selection: null,
};

const isDark = () => BASEMAP_BY_ID[state.basemap].dark === true;

/** Keep `state.sizing` in step with the slider value for the current scale. */
function syncSizing() {
  const level = LEVEL_BY_ID[state.level];
  const px = state.sizePx[level.id];
  state.sizing.maxPx = px;
  state.sizing.uniformPx = Math.round(px * level.sizing.ratio);
  return px;
}

const map = new maplibregl.Map({
  container: "map",
  style: BASEMAP_BY_ID[state.basemap].style,
  center: [117.5, -2.2],
  zoom: 4.3,
  minZoom: 3.4,
  attributionControl: { compact: true },
});
// Both bottom: the top-right corner belongs to the inspector, which is the one
// panel that appears without being asked for and must not land on the zoom
// buttons when it does.
map.addControl(
  new maplibregl.NavigationControl({ showCompass: false }),
  "bottom-right",
);
map.addControl(
  new maplibregl.ScaleControl({ maxWidth: 110, unit: "metric" }),
  "bottom-left",
);

/**
 * Swap the backdrop.
 *
 * `setStyle` discards every layer and source on the map, the custom screengrid
 * layer included, so this is a teardown and a full rebuild rather than a paint
 * change. All the bookkeeping that points at destroyed objects has to be reset
 * before `render()` runs, or the rebuild will try to update sources that are no
 * longer there.
 */
async function setBasemap(id) {
  if (state.basemap === id) return;
  state.basemap = id;
  const def = BASEMAP_BY_ID[id];
  const token = ++generation;

  state.glyphLayer = null;
  clearBoundaryState();
  closePointPopup();
  ui.updateBasemaps(els.basemaps, id);

  map.setStyle(def.style);
  await new Promise((resolve) => map.once("styledata", resolve));
  if (token !== generation) return;
  if (def.tint) tintBasemap(map);
  await render(token);
}

// ---------------------------------------------------------------------------
// Derived state
// ---------------------------------------------------------------------------

/** Which measures and families the current glyph mode needs computed. */
function currentSpec() {
  if (state.mode === "composition")
    return makeSpec("composition", [], state.family);
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

async function rebuildGlyphs(token) {
  removeGlyphs(map, state.glyphLayer);
  state.glyphLayer = null;

  if (!state.showGlyphs) return;

  const level = LEVEL_BY_ID[state.level];
  const spec = currentSpec();
  const px = syncSizing();

  if (level.kind === "grid") {
    state.glyphLayer = createGridLayer({
      rows: state.filtered,
      spec,
      cellSizePixels: px,
      onStats: onStats,
      onHover: onHover,
      onClick: onClick,
    });
  } else {
    const collection = await ensureLevel(state.level);
    if (token !== generation) return;
    state.glyphLayer = createAnchorLayer({
      collection,
      spec,
      sizing: state.sizing,
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

async function syncBoundaries(token = generation) {
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
    // The level or the basemap can change while an 8 MB fetch is in flight;
    // dropping a stale response is cheaper than cancelling and keeps the map
    // consistent.
    if (
      token !== generation ||
      state.level !== level.id ||
      !state.showBoundaries
    )
      return;
    setBoundaries(map, geo, { selectedId: state.selection, dark: isDark() });
    restack();
    const missing = (state.counts[level.id] ?? 0) - geo.features.length;
    ui.setBoundaryNote(
      els.rail,
      missing > 0
        ? `${missing} wilayah tidak punya poligon yang cocok; grafik-nya tetap tampil.`
        : "",
    );
  } catch (err) {
    removeBoundaries(map);
    ui.setBoundaryNote(els.rail, `Batas wilayah gagal dimuat: ${err.message}`);
  }
}

function syncPoints() {
  if (!state.showPoints) return removePoints(map);
  setPoints(map, state.filtered, { dark: isDark() });
  restack();
}

/**
 * Rebuild everything on the map from `state`.
 *
 * Async in three places — the level query, the boundary fetch, the style swap —
 * so two renders can be in flight at once if someone clicks quickly. `generation`
 * is the guard: a render that has been superseded stops rather than adding its
 * layers on top of the newer one's, which otherwise throws on the duplicate
 * layer id or, worse, silently leaves the map showing a mixture of two states.
 */
let generation = 0;

async function render(token = ++generation) {
  const level = LEVEL_BY_ID[state.level];
  ui.updateLadder(els.rail, state.level, state.counts);
  ui.updateModes(els.rail, state.mode);
  ui.setSizeControl(els.rail, level.sizing, state.sizePx[level.id]);
  ui.updateFilterBadge(els.rail, changedFilterCount(), level.kind === "grid");
  ui.updateCount(els.rail, state.filtered.length);

  await rebuildGlyphs(token);
  if (token !== generation) return;
  await syncBoundaries(token);
  if (token !== generation) return;
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
  closePointPopup();

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

// ---------------------------------------------------------------------------
// Cooperative point popup
// ---------------------------------------------------------------------------

let pointPopup = null;

function closePointPopup() {
  pointPopup?.remove();
  pointPopup = null;
}

/** Whether a screengrid glyph is under the pointer. If so the glyph layer
 *  owns the interaction (tooltip / inspector) and the point beneath it stays
 *  quiet — this is the same hit test screengrid uses, so the two cannot
 *  disagree about what is under the cursor. */
function overGlyph(point) {
  const gl = state.glyphLayer;
  return Boolean(
    state.showGlyphs && gl?.getCellAt?.({ x: point.x, y: point.y }),
  );
}

/** Clicking a cooperative dot opens a popup at the point itself. */
function onPointClick(e) {
  if (overGlyph(e.point)) return; // the glyph layer handles this click
  const f = e.features?.[0];
  if (!f) return;
  closeInspector();
  closePointPopup();
  pointPopup = new maplibregl.Popup({
    closeButton: true,
    closeOnClick: true,
    offset: 10,
    maxWidth: "300px",
  })
    .setLngLat(e.lngLat)
    .setHTML(ui.pointPopupHtml(f.properties))
    .addTo(map);
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
  map.easeTo({
    center: [props.anchor_lon, props.anchor_lat],
    zoom,
    duration: 700,
  });
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
// Search
// ---------------------------------------------------------------------------

/**
 * Go to whatever was picked.
 *
 * A cooperative is a place: fly to it, turn the point layer on so there is
 * something to see when you arrive, and mark it. An area is a scale: switch the
 * ladder to that scale, fly to it, and open its inspector — which is the same
 * thing clicking its glyph would have done.
 */
async function gotoResult(entry) {
  if (entry.kind === "koperasi") {
    if (!state.showPoints) {
      state.showPoints = true;
      els.rail.querySelector("#toggle-points").checked = true;
      syncPoints();
    }
    map.easeTo({ center: [entry.lon, entry.lat], zoom: 16, duration: 900 });
    closeInspector();
    showFoundPoint(entry);
    return;
  }

  const wasLevel = state.level;
  state.level = entry.kind;
  closeInspector();
  if (wasLevel !== entry.kind) await render();

  const collection = await ensureLevel(entry.kind);
  const feature = collection.features.find(
    (f) => f.properties.admin_id === entry.id,
  );
  const target = feature
    ? feature.geometry.coordinates
    : [entry.lon, entry.lat];
  map.easeTo({
    center: target,
    zoom:
      entry.kind === "provinsi" ? 6.4 : entry.kind === "kabupaten" ? 8.4 : 10.4,
    duration: 900,
  });
  if (feature) {
    onClick({
      kind: "admin",
      count: feature.properties.cooperatives ?? 0,
      rows: null,
      summary: null,
      props: feature.properties,
    });
  }
}

let foundMarker = null;

/** Mark the searched cooperative, since one dot among 83.000 is easy to lose. */
function showFoundPoint(entry) {
  foundMarker?.remove();
  const r = entry.row ?? {};
  foundMarker = new maplibregl.Popup({ closeOnClick: false, offset: 12 })
    .setLngLat([entry.lon, entry.lat])
    .setHTML(
      `<div class="found">
         <b>${ui.escapeHtml(entry.name)}</b>
         <span>${ui.escapeHtml([r.subdistrict, r.district, r.province].filter(Boolean).join(", "))}</span>
         ${
           r.imagery_url
             ? `<a href="${ui.escapeHtml(r.imagery_url)}" target="_blank" rel="noopener">Lihat citra satelit ↗</a>`
             : ""
         }
       </div>`,
    )
    .addTo(map);
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
  if (BASEMAP_BY_ID[state.basemap].tint) tintBasemap(map);

  ui.renderBasemaps(els.basemaps, BASEMAPS, state.basemap, setBasemap);
  ui.renderSearch(els.search, {
    onQuery: (q) => search(state.index, q),
    onPick: gotoResult,
  });

  ui.renderRail(els.rail, {
    ...handlers,
    size: (px) => {
      const level = LEVEL_BY_ID[state.level];
      state.sizePx[level.id] = px;
      syncSizing();
      // A slider drag is the one interaction that has to stay in-place rather
      // than rebuild. On the grid that means the cell size; on an anchor layer
      // the draw already reads `state.sizing` every frame, and only the hit
      // radius — which derives from anchorSizePixels — needs telling.
      state.glyphLayer?.setConfig?.(
        level.kind === "grid"
          ? { cellSizePixels: px }
          : { anchorSizePixels: state.sizing.maxPx },
      );
      map.triggerRepaint();
    },
    points: (on) => {
      state.showPoints = on;
      if (!on) closePointPopup();
      syncPoints();
    },
    boundaries: (on) => {
      state.showBoundaries = on;
      syncBoundaries();
    },
    glyphs: (on) => {
      state.showGlyphs = on;
      render();
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
    state.index = buildIndex(rows);
    ui.renderFoot(els.rail, manifest);

    // Scale cardinalities come from the manifest, which the mart builder writes
    // — one source of truth for "how many kecamatan are there", and it moves
    // when the data does.
    for (const level of LEVELS) {
      if (level.kind === "grid") continue;
      const schema = manifest.schema?.[level.table];
      state.counts[level.id] =
        (schema?.rows ?? 0) - (schema?.rows_without_anchor ?? 0);
    }

    applyFilters();

    // National baselines for the legend and inspector, over every cooperative
    // and through the same summariser the glyphs use.
    state.national = summarizeCell(
      state.rows,
      makeSpec(
        "profile",
        MEASURES.map((m) => m.id),
        null,
      ),
      identity,
    );
    for (const fam of ["road", "pop", "nn"]) {
      const s = summarizeCell(
        state.rows,
        makeSpec("composition", [], fam),
        identity,
      );
      Object.assign(state.national.shares, s.shares);
    }

    status(null);
    await render();

    // The admin parquets are tiny (≤0.5 MB) and live on the same shared data
    // layer as the grid, so warm them in the background while the reader looks
    // at the national view. The first click on Kecamatan / Kabupaten / Provinsi
    // then finds its anchors already cached and only waits on the (lazy)
    // boundary fill. Errors are ignored — a failed prefetch is retried on the
    // real switch.
    for (const level of LEVELS) {
      if (level.kind === "admin") ensureLevel(level.id).catch(() => {});
    }
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
// A cooperative dot is clickable unless a screengrid glyph owns that spot —
// there the glyph layer opens its own inspector and the dot stays quiet.
map.on("click", POINTS_LAYER, onPointClick);
map.on("mousemove", POINTS_LAYER, (e) => {
  if (!e.features?.length) return;
  map.getCanvas().style.cursor = overGlyph(e.point) ? "" : "pointer";
});
map.on("mouseleave", POINTS_LAYER, () => {
  map.getCanvas().style.cursor = "";
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    closeInspector();
    closePointPopup();
  }
});
