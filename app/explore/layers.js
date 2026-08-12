/**
 * layers.js — every map layer the explorer can show, and nothing about the UI.
 *
 * Three layer kinds, stacked bottom to top:
 *
 *   boundaries  faint admin polygons, context only (MapLibre fill + line)
 *   points      one dot per cooperative, the raw coordinates (MapLibre circle)
 *   glyphs      the screengrid layer, either a screen grid or admin anchors
 *
 * The glyph layer is always last so the canvas draws over both, and points sit
 * above boundaries so a dot is never lost inside a fill.
 */

import { ScreenGridLayerGL } from "https://unpkg.com/screengrid@3.1.1/dist/screengrid.mjs";
import {
  drawGlyph,
  sizeFor,
  sizeReference,
  summarizeAnchor,
  summarizeCell,
  valueExtent,
} from "./glyph.js";

const FULL_SCALE = [0, 100];

/** The ramp bounds for the current mode: absolute unless stretching is asked for. */
function measureDomain(spec, values) {
  if (spec.mode !== "measure" || !spec.stretch) return FULL_SCALE;
  return valueExtent(values);
}

export const GLYPH_LAYER = "kopdes-glyphs";
export const POINTS_LAYER = "kopdes-points";
export const BOUNDARY_FILL = "kopdes-boundary-fill";
export const BOUNDARY_LINE = "kopdes-boundary-line";
const BOUNDARY_SOURCE = "kopdes-boundaries";
const POINTS_SOURCE = "kopdes-points-src";

// ---------------------------------------------------------------------------
// Boundaries
// ---------------------------------------------------------------------------

/**
 * Context polygons under the glyphs.
 *
 * Deliberately almost invisible. These exist so a reader can tell which
 * kabupaten a symbol belongs to and see how far its territory reaches; the
 * moment they carry a fill strong enough to compare, the map has two competing
 * encodings of the same data and the larger polygons win on area alone — which
 * is exactly the distortion anchor glyphs avoid.
 */
export function setBoundaries(map, geojson, { selectedId = null } = {}) {
  if (!map.getSource(BOUNDARY_SOURCE)) {
    map.addSource(BOUNDARY_SOURCE, { type: "geojson", data: geojson, promoteId: "id" });
    map.addLayer({
      id: BOUNDARY_FILL,
      type: "fill",
      source: BOUNDARY_SOURCE,
      paint: {
        "fill-color": [
          "case",
          ["boolean", ["feature-state", "selected"], false],
          "#a00000",
          "#6b6255",
        ],
        "fill-opacity": [
          "case",
          ["boolean", ["feature-state", "selected"], false],
          0.15,
          0.05,
        ],
      },
    });
    map.addLayer({
      id: BOUNDARY_LINE,
      type: "line",
      source: BOUNDARY_SOURCE,
      paint: {
        "line-color": [
          "case",
          ["boolean", ["feature-state", "selected"], false],
          "#a00000",
          "#8f8674",
        ],
        "line-width": [
          "case",
          ["boolean", ["feature-state", "selected"], false],
          1.8,
          0.8,
        ],
        "line-opacity": 0.75,
      },
    });
  } else {
    map.getSource(BOUNDARY_SOURCE).setData(geojson);
  }
  if (selectedId != null) setBoundarySelection(map, selectedId);
}

export function removeBoundaries(map) {
  for (const id of [BOUNDARY_FILL, BOUNDARY_LINE]) {
    if (map.getLayer(id)) map.removeLayer(id);
  }
  if (map.getSource(BOUNDARY_SOURCE)) map.removeSource(BOUNDARY_SOURCE);
}

let selectedBoundary = null;

/** Outline one admin area, clearing whichever was outlined before. */
export function setBoundarySelection(map, id) {
  if (!map.getSource(BOUNDARY_SOURCE)) return;
  if (selectedBoundary != null) {
    map.setFeatureState(
      { source: BOUNDARY_SOURCE, id: selectedBoundary },
      { selected: false },
    );
  }
  selectedBoundary = id;
  if (id != null) {
    map.setFeatureState({ source: BOUNDARY_SOURCE, id }, { selected: true });
  }
}

// ---------------------------------------------------------------------------
// Points
// ---------------------------------------------------------------------------

/**
 * Every cooperative at its recorded coordinate.
 *
 * Unclustered on purpose. Clustering answers "how many are near here", which is
 * the glyph layer's job and which the glyph layer does at a resolution the
 * reader controls; a cluster bubble on top of a grid cell is the same number
 * drawn twice. What this layer is for is the opposite question — where exactly
 * is this one, and does the dot land somewhere plausible.
 */
export function setPoints(map, rows) {
  const geojson = {
    type: "FeatureCollection",
    features: rows.map((r) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [r.longitude, r.latitude] },
      properties: { cooperative_id: r.cooperative_id },
    })),
  };

  if (!map.getSource(POINTS_SOURCE)) {
    map.addSource(POINTS_SOURCE, { type: "geojson", data: geojson });
    map.addLayer({
      id: POINTS_LAYER,
      type: "circle",
      source: POINTS_SOURCE,
      paint: {
        // At national zoom 83.000 dots are a smear, so they stay small and
        // translucent and only resolve into individual marks as you go in.
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 1.1, 8, 2.4, 12, 4.5, 16, 7],
        "circle-color": "#1a1a1a",
        "circle-opacity": ["interpolate", ["linear"], ["zoom"], 4, 0.28, 9, 0.55, 13, 0.8],
        "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 9, 0, 12, 1],
        "circle-stroke-color": "#fff",
      },
    });
  } else {
    map.getSource(POINTS_SOURCE).setData(geojson);
  }
}

export function removePoints(map) {
  if (map.getLayer(POINTS_LAYER)) map.removeLayer(POINTS_LAYER);
  if (map.getSource(POINTS_SOURCE)) map.removeSource(POINTS_SOURCE);
}

// ---------------------------------------------------------------------------
// Glyphs
// ---------------------------------------------------------------------------

/**
 * The screen-space grid: cells are fixed in pixels, so panning and zooming
 * re-bins the same cooperatives at whatever resolution is on screen.
 *
 * `maxCount` is captured from each aggregation and read back during the draw
 * that immediately follows it — screengrid runs `_aggregate()` then `_draw()`
 * inside one `render()` call, so the value a glyph sizes against is always the
 * one from its own frame.
 */
export function createGridLayer({ rows, spec, cellSizePixels, onStats, onHover, onClick }) {
  let reference = 1;
  let domain = FULL_SCALE;
  const counts = [];

  return ScreenGridLayerGL.glyphMap({
    id: GLYPH_LAYER,
    data: rows,
    getPosition: (r) => [r.longitude, r.latitude],
    getWeight: () => 1,
    aggregationFunction: "sum", // cell value is a plain count of cooperatives
    cellSizePixels,
    enableGlyphs: true,

    onAfterAggregate: (cellData) => summarizeCell(cellData, spec),

    onAggregate: (gridData) => {
      counts.length = 0;
      const values = [];
      const measureId = spec.measures[0]?.id;
      let max = 1;
      let total = 0;
      for (let i = 0; i < gridData.grid.length; i++) {
        const n = gridData.cellData?.[i]?.length ?? 0;
        if (!n) continue;
        counts.push(n);
        total += n;
        if (n > max) max = n;
        if (measureId) values.push(gridData.customData?.[i]?.values?.[measureId]);
      }
      reference = sizeReference(counts);
      domain = measureDomain(spec, values);
      onStats?.({ cells: counts.length, max, total, domain, kind: "grid" });
    },

    onDrawCell: (ctx, x, y, _norm, cell) => {
      const summary = cell.customData;
      if (!summary) return;
      // In profile mode the uniform box is the cell itself, which is already
      // constant across the grid — so the lattice reads as one comparable
      // small-multiple per cell.
      const box = cell.cellSize * 0.92;
      drawGlyph(ctx, x, y, summary, {
        spec,
        domain,
        size: sizeFor(spec, summary.count, reference, box, box),
        hovered: cell.isHovered === true,
      });
    },

    onHover: ({ cell, event }) => onHover?.(toGridPayload(cell), event),
    onClick: ({ cell, event }) => onClick?.(toGridPayload(cell), event),
  });
}

/**
 * Administrative anchors: one glyph per kecamatan / kabupaten / provinsi, at
 * the median position of its member cooperatives.
 *
 * The anchor is not the polygon's centroid and is not meant to be. A centroid
 * can sit in the sea off a coastal kabupaten or in empty forest; the median
 * cooperative sits where the cooperatives actually are, which is the thing
 * being summarised.
 */
export function createAnchorLayer({
  collection,
  spec,
  maxPx,
  uniformPx,
  onStats,
  onHover,
  onClick,
}) {
  const counts = collection.features.map((f) => f.properties.cooperatives || 0);
  const reference = sizeReference(counts);
  const measure = spec.measures[0];
  const domain = measureDomain(
    spec,
    measure ? collection.features.map((f) => measure.agg(f.properties)) : [],
  );
  onStats?.({
    cells: collection.features.length,
    max: counts.reduce((a, b) => (b > a ? b : a), 0),
    total: counts.reduce((a, b) => a + b, 0),
    domain,
    kind: "admin",
  });

  return ScreenGridLayerGL.featureGlyphs({
    id: GLYPH_LAYER,
    source: collection,
    placement: { strategy: "point" },
    // Uniform envelope; the per-glyph size comes from the count inside
    // onDrawCell, because feature-anchors draws every anchor at one size.
    anchorSizePixels: maxPx,
    enableGlyphs: true,

    onDrawCell: (ctx, x, y, _norm, cell) => {
      const props = cell.props;
      if (!props) return;
      drawGlyph(ctx, x, y, summarizeAnchor(props, spec), {
        spec,
        domain,
        size: sizeFor(spec, props.cooperatives, reference, maxPx, uniformPx),
        hovered: cell.isHovered === true,
      });
    },

    onHover: ({ cell, event }) => onHover?.(toAnchorPayload(cell), event),
    onClick: ({ cell, event }) => onClick?.(toAnchorPayload(cell), event),
  });
}

export function removeGlyphs(map, layer) {
  if (map.getLayer(GLYPH_LAYER)) map.removeLayer(GLYPH_LAYER);
  else layer?.onRemove?.();
}

/**
 * Normalise the two cell shapes into one payload for the tooltip and inspector,
 * so neither has to branch on which layer produced the hit.
 */
function toGridPayload(cell) {
  if (!cell?.cellData?.length) return null;
  return {
    kind: "grid",
    count: cell.cellData.length,
    rows: cell.cellData.map((d) => d.data),
    summary: cell.customData ?? null,
    props: null,
  };
}

function toAnchorPayload(cell) {
  if (!cell?.props) return null;
  return {
    kind: "admin",
    count: cell.props.cooperatives ?? 0,
    rows: null,
    summary: null,
    props: cell.props,
  };
}
