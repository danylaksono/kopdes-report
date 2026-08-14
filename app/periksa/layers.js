/**
 * layers.js — the map overlays that show /periksa/ its own working.
 *
 * The table says "nearest mapped building: ±264 m". These layers show the cells
 * that sentence came from: the search disk, every road cell and building cell
 * inside it, the population hexes that were summed, and the neighbouring
 * cooperatives. A reader who does not believe a number can look at what
 * produced it.
 *
 * ## They cost one extra pass, not one extra request
 *
 * Every polygon here is drawn from rows the analysis already fetched.
 * `analysis.js` used to discard the cells after taking the minimum ring; it now
 * returns them, and this module turns cell ids into boundaries with
 * `cellToBoundary`. No new query, no new download.
 *
 * ## Constraints worth knowing before editing
 *
 * - **The basemap is a raster style, so there are no glyphs and no sprite.**
 *   A `symbol` layer would need a font stack the style cannot provide and would
 *   silently render nothing. Fills, lines and circles only; text goes in DOM
 *   markers or the panel.
 * - **Only cells inside the disk are drawn.** The query fetches whole r7
 *   parents, so it returns a ragged surplus around the edge; `analysis.js`
 *   filters to the disk before handing anything over. Drawing the surplus would
 *   show a search area we did not actually use.
 * - Colours are picked to survive satellite imagery, which is dark, green and
 *   busy. Saturated hues at low fill opacity with a brighter line on top read;
 *   pastels do not.
 */

import { cellToBoundary, cellsToMultiPolygon } from "https://cdn.jsdelivr.net/npm/h3-js@4.5.0/+esm";

/**
 * The toggles, in the order the analysis uses them.
 *
 * `id` doubles as the source id prefix and the checkbox value. All default to
 * off: the reader's first job on this page is to look at a rooftop and click
 * it, and four overlays over the imagery would defeat that. They are for
 * afterwards, when the question is "why that number".
 */
export const OVERLAYS = [
  {
    id: "search",
    label: "Area pencarian 5 km",
    hint: "Batas terluar pencarian: 38 cincin petak H3, sekitar 5 km",
    color: "#ffffff",
  },
  {
    id: "road",
    label: "Petak berisi jalan",
    hint: "Setiap petak 132 m yang dilewati jalan terpetakan",
    color: "#f5b301",
  },
  {
    id: "building",
    label: "Petak berisi bangunan",
    hint: "Setiap petak 132 m yang berisi minimal satu bangunan terpetakan",
    color: "#ff5fa2",
  },
  {
    id: "pop",
    label: "Petak penduduk",
    hint: "Petak 400 m Kontur, makin terang makin padat",
    color: "#4cc9f0",
  },
  {
    id: "coops",
    label: "Koperasi lain (5 km)",
    hint: "KDMP lain di sekitar titik ini",
    color: "#ffffff",
  },
];

const SRC = (id) => `ov-${id}-src`;

/** H3 cells as a GeoJSON FeatureCollection of polygons. */
function cellsToFeatures(cells, props = () => ({})) {
  return {
    type: "FeatureCollection",
    features: cells.map((c) => {
      const cell = typeof c === "string" ? c : c.cell;
      return {
        type: "Feature",
        properties: props(c),
        geometry: {
          // true = GeoJSON winding and [lng, lat] order. Without it the ring
          // comes back [lat, lng] and every hexagon lands in the wrong ocean.
          type: "Polygon",
          coordinates: [cellToBoundary(cell, true)],
        },
      };
    }),
  };
}

const EMPTY = { type: "FeatureCollection", features: [] };

/**
 * Attach the overlay sources and layers to a loaded map.
 *
 * Returns `{ update, setVisible }`. Layers start hidden; `update` swaps the
 * data without touching visibility, so a reader who has turned roads on keeps
 * them on when they drag the pin.
 */
export function createOverlays(map) {
  for (const o of OVERLAYS) {
    map.addSource(SRC(o.id), { type: "geojson", data: EMPTY });
  }

  const hidden = { visibility: "none" };

  // Search area: outline only. A filled disk would hide the imagery the reader
  // is here to look at.
  map.addLayer({
    id: "ov-search-line",
    type: "line",
    source: SRC("search"),
    layout: { ...hidden },
    paint: {
      "line-color": "#ffffff",
      "line-width": 1.5,
      "line-dasharray": [3, 2],
      "line-opacity": 0.85,
    },
  });

  // Population sits under the two cell layers: it is r8 (400 m), so its hexes
  // are ~9x the area of an r10 cell and would bury them.
  map.addLayer({
    id: "ov-pop-fill",
    type: "fill",
    source: SRC("pop"),
    layout: { ...hidden },
    paint: {
      "fill-color": [
        "interpolate",
        ["linear"],
        ["get", "population"],
        0, "#1f6f9c",
        50, "#3aa0cc",
        250, "#4cc9f0",
        1000, "#c9f4ff",
      ],
      // Opacity carries the value as well as hue. An empty cell is information
      // too, but painting it at full strength turns every uninhabited hex into
      // a dark blot over the imagery the reader is trying to read.
      "fill-opacity": [
        "interpolate",
        ["linear"],
        ["get", "population"],
        0, 0.1,
        50, 0.26,
        1000, 0.42,
      ],
      "fill-outline-color": "rgba(255,255,255,0.22)",
    },
  });

  // Fill opacities are deliberately low and differ between the two: road cells
  // blanket a village almost completely, so a fill heavy enough to see one cell
  // makes a solid sheet of the whole neighbourhood. Buildings are sparser and
  // can carry more. In both cases the outline does the work.
  for (const [id, color, fill] of [
    ["road", "#f5b301", 0.1],
    ["building", "#ff5fa2", 0.2],
  ]) {
    map.addLayer({
      id: `ov-${id}-fill`,
      type: "fill",
      source: SRC(id),
      layout: { ...hidden },
      paint: { "fill-color": color, "fill-opacity": fill },
    });
    map.addLayer({
      id: `ov-${id}-line`,
      type: "line",
      source: SRC(id),
      layout: { ...hidden },
      paint: { "line-color": color, "line-width": 0.7, "line-opacity": 0.85 },
    });
  }

  map.addLayer({
    id: "ov-coops-circle",
    type: "circle",
    source: SRC("coops"),
    layout: { ...hidden },
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 3, 16, 6],
      "circle-color": "#ffd166",
      "circle-stroke-color": "#3a2a00",
      "circle-stroke-width": 1.2,
      "circle-opacity": 0.95,
    },
  });

  const LAYERS_OF = {
    search: ["ov-search-line"],
    pop: ["ov-pop-fill"],
    road: ["ov-road-fill", "ov-road-line"],
    building: ["ov-building-fill", "ov-building-line"],
    coops: ["ov-coops-circle"],
  };

  return {
    setVisible(id, on) {
      for (const layer of LAYERS_OF[id] ?? []) {
        if (map.getLayer(layer)) {
          map.setLayoutProperty(layer, "visibility", on ? "visible" : "none");
        }
      }
    },

    /**
     * Swap in the neighbourhood of one analysed point.
     *
     * `result` is an `analysePoint` return value; `coops` is the neighbour list
     * from `cooperativesWithin`.
     */
    update(result, coops) {
      if (!result) {
        for (const o of OVERLAYS) map.getSource(SRC(o.id))?.setData(EMPTY);
        return;
      }

      map.getSource(SRC("road"))?.setData(cellsToFeatures(result.road.cells));
      map
        .getSource(SRC("building"))
        ?.setData(cellsToFeatures(result.building.cells));
      map
        .getSource(SRC("pop"))
        ?.setData(
          cellsToFeatures(result.population.cells, (c) => ({
            population: Math.round(c.population),
          })),
        );

      map.getSource(SRC("coops"))?.setData({
        type: "FeatureCollection",
        features: (coops ?? []).map((c) => ({
          type: "Feature",
          properties: { name: c.cooperative, m: Math.round(c.m) },
          geometry: { type: "Point", coordinates: [c.lon, c.lat] },
        })),
      });

      // The disk outline is one union of ~4.400 hexagons. It is the only
      // expensive call here, and a failure in it must not take the other
      // overlays down with it.
      try {
        const rings = cellsToMultiPolygon([...result.disk.keys()], true);
        map.getSource(SRC("search"))?.setData({
          type: "Feature",
          properties: {},
          geometry: { type: "MultiPolygon", coordinates: rings },
        });
      } catch (err) {
        console.warn("search-area outline failed", err);
        map.getSource(SRC("search"))?.setData(EMPTY);
      }
    },
  };
}
