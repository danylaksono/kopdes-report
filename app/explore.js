/** explore.js — the interactive map (/explore/).
 *
 * One shared data layer with the rest of the site: the committed analysis
 * mart parquet (data/web/kopdes_points.parquet) read through DuckDB-wasm, and
 * the same screengrid component as the old three-view map — configured here
 * for the report, not reimplemented.
 *
 * No build step: maplibre, screengrid and duckdb-wasm are CDN ES modules.
 */

import {
  addPointsLayer,
  removePointsLayer,
  VERIFIED_COLORS,
} from "./points-layer.js";
import {
  createGridLayer,
  gridColorRampCss,
  LAYER_ID as GRID_LAYER_ID,
} from "./grid-layer.js";
import * as duckdb from "@duckdb/duckdb-wasm"; // resolved via the import map in explore/index.html

const PARQUET_URL = new URL("../data/web/kopdes_points.parquet", location.href)
  .href;
const NEEDED_COLUMNS = [
  "cooperative_id",
  "latitude",
  "longitude",
  "own_cell_pop",
  "km_non_track",
  "m_to_minimarket_exact",
  "land_verified",
  "has_reported_transaction",
  "coordinate_suspect",
  "cluster_size",
];

const els = {
  legend: document.getElementById("explore-legend"),
  tip: document.getElementById("explore-tip"),
  cellSize: document.getElementById("cell-size"),
  cellSizeVal: document.getElementById("cell-size-val"),
  cellSizeField: document.getElementById("cell-size-field"),
  loading: document.getElementById("explore-loading"),
};

// --- filter definitions (Bahasa Indonesia labels live in the HTML) ----------

const FILTERS = {
  population: {
    all: () => true,
    zero_cell: (p) => p.own_cell_pop === 0,
    populated: (p) => p.own_cell_pop > 0,
  },
  road: {
    all: () => true,
    no_road: (p) => p.km_non_track == null || p.km_non_track > 5,
    has_road: (p) => p.km_non_track != null && p.km_non_track <= 5,
  },
  minimarket: {
    all: () => true,
    far: (p) =>
      p.m_to_minimarket_exact == null || p.m_to_minimarket_exact > 5000,
    near: (p) =>
      p.m_to_minimarket_exact != null && p.m_to_minimarket_exact <= 5000,
  },
  land: {
    all: () => true,
    verified: (p) => p.land_verified === true,
    not_verified: (p) => p.land_verified !== true,
  },
  transaction: {
    all: () => true,
    reporting: (p) => p.has_reported_transaction === true,
    silent: (p) => p.has_reported_transaction === false,
  },
  cluster: {
    all: () => true,
    clustered: (p) => p.cluster_size != null,
    isolated: (p) => p.cluster_size == null,
  },
};

const state = {
  view: "grid",
  cellSizePixels: 48,
  rows: [], // raw rows from the parquet
  features: [], // GeoJSON features (all rows)
  filtered: [], // features after current filters
  gridLayer: null,
  gridStats: null,
};

const map = new maplibregl.Map({
  container: "explore-map",
  style: "https://tiles.openfreemap.org/styles/positron",
  center: [117.5, -2.5],
  zoom: 4.2,
});

map.addControl(new maplibregl.NavigationControl(), "top-right");

// --- data load --------------------------------------------------------------

async function loadRows() {
  const bundle = duckdb.getJsDelivrBundles();
  const selected = await duckdb.selectBundle(bundle);
  const workerUrl = URL.createObjectURL(
    new Blob([`importScripts("${selected.mainWorker}");`], {
      type: "text/javascript",
    }),
  );
  const worker = new Worker(workerUrl);
  const db = new duckdb.AsyncDuckDB(new duckdb.ConsoleLogger(), worker);
  await db.instantiate(selected.mainModule, selected.pthreadWorker);
  const con = await db.connect();
  const cols = NEEDED_COLUMNS.join(", ");
  const tbl = await con.query(
    `SELECT ${cols} FROM read_parquet('${PARQUET_URL}')`,
  );
  return tbl.toArray().map((row) => row.toJSON());
}

function toFeatures(rows) {
  return rows.map((r) => ({
    type: "Feature",
    geometry: { type: "Point", coordinates: [r.longitude, r.latitude] },
    properties: r,
  }));
}

// --- view / filter wiring ---------------------------------------------------

function currentFilters() {
  const out = [];
  for (const key of Object.keys(FILTERS)) {
    const sel = document.getElementById(`f-${key}`);
    out.push(FILTERS[key][sel?.value ?? "all"]);
  }
  return out;
}

function applyFilters() {
  const preds = currentFilters();
  state.filtered = state.features.filter((f) =>
    preds.every((pred) => pred(f.properties)),
  );
  // Rebuild the layer: the screengrid layer's data is set at construction, so
  // a filter change is a rebuild, not a setData.
  applyView();
  renderLegend();
}

function applyView() {
  removePointsLayer(map);
  if (state.gridLayer) {
    if (map.getLayer(GRID_LAYER_ID)) map.removeLayer(GRID_LAYER_ID);
    state.gridLayer = null;
    state.gridStats = null;
  }
  hideTip();

  if (state.view === "points") {
    addPointsLayer(map, {
      type: "FeatureCollection",
      features: state.filtered,
    });
  } else {
    state.gridLayer = createGridLayer(state.filtered, {
      mode: state.view === "hex" ? "screen-hex" : "screen-grid",
      cellSizePixels: state.cellSizePixels,
      onStats: (stats) => {
        state.gridStats = stats;
        renderLegend();
      },
      onHover: showTip,
    });
    map.addLayer(state.gridLayer);
  }
  els.cellSizeField.hidden = state.view === "points";
  renderLegend();
}

function wireControls() {
  for (const input of document.querySelectorAll('input[name="view"]')) {
    input.checked = input.value === state.view;
    input.addEventListener("change", () => {
      state.view = input.value;
      applyView();
    });
  }
  for (const key of Object.keys(FILTERS)) {
    document
      .getElementById(`f-${key}`)
      .addEventListener("change", applyFilters);
  }
  els.cellSize.value = String(state.cellSizePixels);
  els.cellSizeVal.textContent = `${state.cellSizePixels} px`;
  els.cellSize.addEventListener("input", () => {
    state.cellSizePixels = Number(els.cellSize.value);
    els.cellSizeVal.textContent = `${state.cellSizePixels} px`;
    state.gridLayer?.setConfig({ cellSizePixels: state.cellSizePixels });
    map.triggerRepaint();
  });
}

// --- legend + tooltip -------------------------------------------------------

function renderLegend() {
  if (state.view === "points") {
    els.legend.innerHTML = `
      <h2>Legenda</h2>
      <div class="row"><span class="dot" style="background:${VERIFIED_COLORS.verified}"></span> Terverifikasi</div>
      <div class="row"><span class="dot" style="background:${VERIFIED_COLORS.not_verified}"></span> Belum terverifikasi</div>
      <div class="row"><span class="dot" style="background:${VERIFIED_COLORS.no_record}"></span> Tanpa catatan aset</div>`;
    return;
  }
  const max = state.gridStats?.max ?? 0;
  const filled = state.gridStats?.cellsWithData ?? 0;
  els.legend.innerHTML = `
    <h2>Legenda</h2>
    <div class="row"><b>Koperasi per sel</b></div>
    <div class="ramp" style="background:${gridColorRampCss()}"></div>
    <div class="scale"><span>${max ? 1 : 0}</span><span>${max.toLocaleString("id-ID")}</span></div>
    <div class="hint">${filled.toLocaleString("id-ID")} sel terisi · ${state.filtered.length.toLocaleString("id-ID")} koperasi.</div>`;
}

function showTip(cell, event) {
  if (!cell || !event) return hideTip();
  const count = cell.records?.count ?? cell.cellData?.length ?? 0;
  if (!count) return hideTip();
  els.tip.textContent = `${count.toLocaleString("id-ID")} koperasi`;
  els.tip.style.display = "block";
  els.tip.style.left = `${event.point.x + 14}px`;
  els.tip.style.top = `${event.point.y + 14}px`;
}

function hideTip() {
  els.tip.style.display = "none";
}

// --- boot -------------------------------------------------------------------

map.on("load", async () => {
  try {
    state.rows = await loadRows();
    state.features = toFeatures(state.rows);
  } catch (err) {
    els.loading.textContent = `Gagal memuat data: ${err.message}`;
    els.loading.style.display = "block";
    return;
  }
  els.loading.remove();
  applyFilters();
  wireControls();
});

map.getCanvasContainer().addEventListener("mouseleave", hideTip);
