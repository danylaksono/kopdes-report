/**
 * ruler.js — click-to-measure on the /periksa/ map.
 *
 * Why this is hand-written rather than a plugin: `maplibre-gl-measures` ships
 * no ES module build (it would need a UMD script tag plus turf), and
 * `@watergis/maplibre-gl-terradraw` is a full drawing toolkit carrying
 * terra-draw for what is, here, one ruler. Both are heavier than the thing they
 * would replace. The distance function is already imported for the analysis,
 * and this file is the rest of it.
 *
 * The measurement is great-circle, the same function the minimarket and
 * nearest-cooperative distances use, so a length read off the ruler and a
 * number in the table mean the same thing.
 *
 * Constraint inherited from the basemap: the satellite style is raster, so it
 * has no glyphs and a `symbol` layer would render nothing. The running total
 * lives in a DOM marker at the last vertex.
 */

import { greatCircleDistance } from "https://cdn.jsdelivr.net/npm/h3-js@4.5.0/+esm";

const LINE_SRC = "ruler-line-src";
const PT_SRC = "ruler-pt-src";
const EMPTY = { type: "FeatureCollection", features: [] };

function format(m) {
  return m < 1000
    ? `${Math.round(m).toLocaleString("id-ID")} m`
    : `${(m / 1000).toLocaleString("id-ID", { maximumFractionDigits: 2 })} km`;
}

/**
 * Attach the ruler to a loaded map.
 *
 * Returns `{ toggle, isActive, clear, onChange }`. The caller must consult
 * `isActive()` in its own map-click handler: while the ruler is on, a click
 * measures instead of moving the reported pin, and letting both fire would
 * silently rewrite the analysis every time someone measured something.
 */
export function createRuler(map) {
  let active = false;
  let points = [];
  let label = null;
  const listeners = new Set();

  map.addSource(LINE_SRC, { type: "geojson", data: EMPTY });
  map.addSource(PT_SRC, { type: "geojson", data: EMPTY });

  map.addLayer({
    id: "ruler-line-casing",
    type: "line",
    source: LINE_SRC,
    paint: { "line-color": "#000000", "line-width": 4, "line-opacity": 0.45 },
  });
  map.addLayer({
    id: "ruler-line",
    type: "line",
    source: LINE_SRC,
    paint: {
      "line-color": "#ffffff",
      "line-width": 2,
      "line-dasharray": [2, 1.5],
    },
  });
  map.addLayer({
    id: "ruler-pt",
    type: "circle",
    source: PT_SRC,
    paint: {
      "circle-radius": 4.5,
      "circle-color": "#ffffff",
      "circle-stroke-color": "#111111",
      "circle-stroke-width": 1.5,
    },
  });

  function total() {
    let m = 0;
    for (let i = 1; i < points.length; i++) {
      m += greatCircleDistance(
        [points[i - 1].lat, points[i - 1].lon],
        [points[i].lat, points[i].lon],
        "m",
      );
    }
    return m;
  }

  function redraw() {
    map.getSource(LINE_SRC)?.setData(
      points.length >= 2
        ? {
            type: "Feature",
            properties: {},
            geometry: {
              type: "LineString",
              coordinates: points.map((p) => [p.lon, p.lat]),
            },
          }
        : EMPTY,
    );
    map.getSource(PT_SRC)?.setData({
      type: "FeatureCollection",
      features: points.map((p) => ({
        type: "Feature",
        properties: {},
        geometry: { type: "Point", coordinates: [p.lon, p.lat] },
      })),
    });

    const m = total();
    if (points.length >= 2) {
      const last = points[points.length - 1];
      if (!label) {
        const node = document.createElement("div");
        node.className = "ruler-label";
        label = new maplibregl.Marker({ element: node, anchor: "bottom-left", offset: [8, -8] });
      }
      label.getElement().textContent = format(m);
      label.setLngLat([last.lon, last.lat]).addTo(map);
    } else if (label) {
      label.remove();
    }
    notify();
  }

  function notify() {
    for (const fn of listeners) {
      fn({ metres: total(), vertices: points.length, active });
    }
  }

  /** Stop taking points but leave the line drawn, so the result can be read. */
  function finish() {
    if (!active) return;
    active = false;
    map.getCanvas().style.cursor = "";
    map.doubleClickZoom.enable();
    notify();
  }

  function clear() {
    points = [];
    label?.remove();
    label = null;
    redraw();
  }

  map.on("click", (e) => {
    if (!active) return;
    points.push({ lat: e.lngLat.lat, lon: e.lngLat.lng });
    redraw();
  });

  // Double-click ends the line rather than zooming: the convention every
  // desktop GIS uses and the one people try first. A browser fires two `click`
  // events before `dblclick`, so the last point is a duplicate of the one
  // before it and would add a zero-length segment. It is dropped only when it
  // really is a duplicate — popping unconditionally would delete a genuine
  // vertex on any other event ordering.
  map.on("dblclick", (e) => {
    if (!active) return;
    e.preventDefault();
    const n = points.length;
    if (n > 1) {
      const a = points[n - 1];
      const b = points[n - 2];
      if (Math.abs(a.lat - b.lat) < 1e-9 && Math.abs(a.lon - b.lon) < 1e-9) {
        points.pop();
      }
    }
    redraw();
    finish();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && active) finish();
  });

  /**
   * Turn measuring on or off.
   *
   * Turning it ON clears the previous line: a ruler that silently appended to
   * an old measurement would report a total spanning two unrelated things.
   * Turning it off keeps the line, which is what `finish` is for.
   */
  function toggle(on) {
    const next = on ?? !active;
    if (next === active) return active;
    if (next) {
      clear();
      active = true;
      map.getCanvas().style.cursor = "crosshair";
      map.doubleClickZoom.disable();
      notify();
    } else {
      finish();
    }
    return active;
  }

  return {
    toggle,
    clear,
    isActive: () => active,
    onChange(fn) {
      listeners.add(fn);
    },
  };
}
