/**
 * grid-layer.js
 *
 * Screen-space aggregation of the kopdes points using the screengrid library
 * (https://github.com/danylaksono/screengrid), loaded as an ES module from a
 * CDN so the site keeps its no-build-step property.
 *
 * Right now every cooperative counts as 1 and only its position is used, so a
 * cell's value is simply "how many cooperatives fall in this cell on screen".
 * The per-cell attribute encoding (glyphs) comes later; when it does, it hangs
 * off `getWeight` / `onDrawCell` here rather than off the point layer.
 *
 * Screen-space (rather than geographic) binning means cell size is constant in
 * pixels at any zoom: the grid re-aggregates as you pan/zoom, which is the
 * point - it always shows density at the resolution you're actually looking at.
 */

import { ScreenGridLayerGL } from "https://unpkg.com/screengrid@3.1.1/dist/screengrid.mjs";

export const LAYER_ID = "kopdes-grid";

/**
 * Sequential ramp (YlOrRd-ish), chosen to sit on the light Positron basemap.
 * Alpha ramps up with value so sparse cells stay translucent and you can still
 * read coastlines underneath them.
 */
const STOPS = [
  [255, 255, 178],
  [254, 217, 118],
  [254, 178, 76],
  [253, 141, 60],
  [240, 59, 32],
  [189, 0, 38],
];

/**
 * Counts per cell are extremely skewed (Java vs. Papua), so a linear ramp
 * paints almost everything in the lightest bin. Square-rooting the normalized
 * value spreads the low end out without a log's zero-handling awkwardness.
 */
export function gridColor(v) {
  const t = Math.sqrt(Math.min(Math.max(v, 0), 1));
  const pos = t * (STOPS.length - 1);
  const i = Math.min(Math.floor(pos), STOPS.length - 2);
  const f = pos - i;
  const [r0, g0, b0] = STOPS[i];
  const [r1, g1, b1] = STOPS[i + 1];
  return [
    Math.round(r0 + (r1 - r0) * f),
    Math.round(g0 + (g1 - g0) * f),
    Math.round(b0 + (b1 - b0) * f),
    Math.round(140 + 100 * t),
  ];
}

/** CSS gradient matching `gridColor`, for the legend ramp. */
export function gridColorRampCss(steps = 24) {
  const parts = [];
  for (let i = 0; i < steps; i++) {
    const [r, g, b] = gridColor(i / (steps - 1));
    parts.push(`rgb(${r},${g},${b}) ${((i / (steps - 1)) * 100).toFixed(1)}%`);
  }
  return `linear-gradient(to right, ${parts.join(", ")})`;
}

/**
 * @param {Array} features  GeoJSON point features from data/web/points.geojson
 * @param {Object} opts
 * @param {'screen-grid'|'screen-hex'} opts.mode
 * @param {number} opts.cellSizePixels
 * @param {(stats: Object|null) => void} opts.onStats  called after each aggregation
 * @param {(cell: Object|null, event: Object|null) => void} opts.onHover
 */
export function createGridLayer(features, { mode, cellSizePixels, onStats, onHover }) {
  return ScreenGridLayerGL.density({
    id: LAYER_ID,
    data: features,
    getPosition: (f) => f.geometry.coordinates,
    getWeight: () => 1, // one cooperative = one unit; attributes come later
    aggregationFunction: "sum", // ...so the cell value is a plain count
    aggregationMode: mode,
    // ScreenHexMode falls back to cellSizePixels when hexSize is unset, so a
    // single slider drives both tessellations.
    cellSizePixels,
    colorScale: gridColor,
    onAggregate: (gridData) => onStats?.(summarize(gridData)),
    onHover: ({ cell, event }) => onHover?.(cell ?? null, event ?? null),
  });
}

/**
 * Reduce a raw aggregation result to what the legend needs. A cell counts as
 * populated when it actually holds points, not when its value is > 0 - the two
 * only coincide because the current weighting is 1-per-cooperative.
 */
function summarize(gridData) {
  let cellsWithData = 0;
  let max = 0;
  let min = Infinity;
  for (let i = 0; i < gridData.grid.length; i++) {
    if (!gridData.cellData?.[i]?.length) continue;
    cellsWithData++;
    const v = gridData.grid[i];
    if (v > max) max = v;
    if (v < min) min = v;
  }
  return {
    cellsWithData,
    max,
    min: cellsWithData ? min : 0,
    cols: gridData.cols,
    rows: gridData.rows,
  };
}
