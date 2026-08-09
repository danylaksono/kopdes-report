/**
 * main.js
 *
 * Boots the map, loads the generated point file once, and switches between the
 * two views over the same data:
 *   - "points": clustered per-cooperative circles (points-layer.js)
 *   - "grid" / "hex": screen-space density aggregation (grid-layer.js)
 */

import { addPointsLayer, removePointsLayer, VERIFIED_COLORS } from "./points-layer.js";
import { createGridLayer, gridColorRampCss, LAYER_ID as GRID_LAYER_ID } from "./grid-layer.js";

const DATA_URL = "data/web/points.geojson";

const els = {
  info: document.getElementById("info-text"),
  count: document.getElementById("info-count"),
  legend: document.getElementById("legend"),
  tip: document.getElementById("cell-tip"),
  cellSize: document.getElementById("cell-size"),
  cellSizeVal: document.getElementById("cell-size-val"),
  cellSizeField: document.getElementById("cell-size-field"),
};

const state = {
  view: "grid",
  cellSizePixels: 48,
  features: [],
  gridLayer: null,
  gridStats: null,
};

const map = new maplibregl.Map({
  container: "map",
  style: "https://tiles.openfreemap.org/styles/positron",
  center: [117.5, -2.5], // roughly the middle of Indonesia
  zoom: 4.2,
});

map.addControl(new maplibregl.NavigationControl(), "top-right");
map.addControl(new maplibregl.ScaleControl({ maxWidth: 100 }), "bottom-right");

map.on("load", async () => {
  const res = await fetch(DATA_URL);
  if (!res.ok) {
    els.info.textContent = `Could not load ${DATA_URL} — run \`node scripts/build_points.mjs\` first.`;
    return;
  }
  const data = await res.json();
  state.features = data.features;

  els.info.textContent = "Kopdes Merah Putih cooperatives";
  els.count.textContent = `${state.features.length.toLocaleString()} locations`;

  applyView();
  wireControls();
});

// --- view switching ---------------------------------------------------------

function applyView() {
  removePointsLayer(map);
  if (state.gridLayer) {
    if (map.getLayer(GRID_LAYER_ID)) map.removeLayer(GRID_LAYER_ID);
    state.gridLayer = null;
    state.gridStats = null;
  }
  hideTip();

  if (state.view === "points") {
    addPointsLayer(map, { type: "FeatureCollection", features: state.features });
  } else {
    state.gridLayer = createGridLayer(state.features, {
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

  els.cellSize.value = String(state.cellSizePixels);
  els.cellSizeVal.textContent = `${state.cellSizePixels} px`;
  els.cellSize.addEventListener("input", () => {
    state.cellSizePixels = Number(els.cellSize.value);
    els.cellSizeVal.textContent = `${state.cellSizePixels} px`;
    // hexSize falls back to cellSizePixels, so this drives both tessellations.
    state.gridLayer?.setConfig({ cellSizePixels: state.cellSizePixels });
    map.triggerRepaint();
  });
}

// --- legend -----------------------------------------------------------------

function renderLegend() {
  if (state.view === "points") {
    els.legend.innerHTML = `
      <div class="row"><span class="dot" style="background:${VERIFIED_COLORS.verified}"></span> Verified</div>
      <div class="row"><span class="dot" style="background:${VERIFIED_COLORS.not_verified}"></span> Not verified</div>
      <div class="row"><span class="dot" style="background:${VERIFIED_COLORS.no_record}"></span> No asset record</div>
      <div class="note">Land-asset verification status.</div>`;
    return;
  }

  const stats = state.gridStats;
  const max = stats?.max ?? 0;
  els.legend.innerHTML = `
    <div><b>Cooperatives per cell</b></div>
    <div class="ramp" style="background:${gridColorRampCss()}"></div>
    <div class="scale"><span>${max ? 1 : 0}</span><span>${max.toLocaleString()}</span></div>
    <div class="note">
      ${(stats?.cellsWithData ?? 0).toLocaleString()} filled cells.
      Colour is √-scaled and rescales to the current view.
    </div>`;
}

// --- grid hover readout -----------------------------------------------------

function showTip(cell, event) {
  if (!cell || !event) return hideTip();
  const count = cell.records?.count ?? cell.cellData?.length ?? 0;
  if (!count) return hideTip();

  els.tip.textContent = `${count.toLocaleString()} ${count === 1 ? "cooperative" : "cooperatives"}`;
  els.tip.style.display = "block";
  els.tip.style.left = `${event.point.x + 14}px`;
  els.tip.style.top = `${event.point.y + 14}px`;
}

function hideTip() {
  els.tip.style.display = "none";
}

map.getCanvasContainer().addEventListener("mouseleave", hideTip);
