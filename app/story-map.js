/** story-map.js — the "Momen peta" interlude on the home page.
 *
 * A MapLibre map over a compact, committed point layer derived from the mart
 * (`data/web/kopdes_story_points.json`, built by `scripts/build_story_points.py`).
 * The explorer reads the full mart through duckdb-wasm; this page deliberately
 * does NOT — a national overview map is not worth a ~30 MB wasm download on the
 * narrative page. A 2 MB JSON with canvas-drawn circle layers loads instantly
 * and needs no database.
 *
 * Every cooperative is a canvas circle. Three data-grounded filter layers — the
 * truly isolated (report 03), the roadless (05/08), and the impossible
 * coordinates (08) — toggle as a chip radio group, and the chip counts are
 * recomputed from the flags in the data, so they cannot drift from what is drawn.
 *
 * Deliberately a lighter instrument than the explorer: scroll zoom is off (so
 * the page keeps scrolling), and everything here is a gateway to /explore/.
 */

import { BASEMAP_BY_ID, tintBasemap } from "./explore/basemaps.js";

const DATA_ROOT = new URL("../data/web/", import.meta.url).href;
const url = (name) => new URL(name, DATA_ROOT).href;

const INDONESIA = {
  center: [119.3, -2.1],
  zoom: 4.15,
};

/** The archipelago's bounding box, generous enough not to clip the edges.
 *  Used as the map's maxBounds (the camera can never leave Indonesia) and to
 *  clamp filter fitBounds — several flagged points carry bad coordinates
 *  (report 08), and an unclamped fitBounds would zoom out to the whole world. */
const INDONESIA_BOUNDS = [
  [94.0, -11.8],
  [141.8, 7.2],
];

/** Last-resort basemap: a plain warm background, so the dots render even when
 *  the hosted basemap CDN is slow or blocked. setStyle() wipes sources/layers,
 *  so apply() re-runs on the fallback style. */
const FALLBACK_STYLE = {
  version: 8,
  sources: {},
  layers: [
    { id: "bg", type: "background", paint: { "background-color": "#f5f2ea" } },
  ],
};

const FILTERS = [
  { id: "all", label: "Semua", layer: "pts-all", color: "#b3a896", fit: true },
  {
    id: "isolated",
    label: "Terpencil",
    layer: "pts-isolated",
    color: "#d62828",
    prop: "i",
    fit: true,
  },
  {
    id: "roadless",
    label: "Tanpa jalan",
    layer: "pts-roadless",
    color: "#e8801f",
    prop: "r",
    fit: true,
  },
  {
    id: "impossible",
    label: "Di luar Indonesia",
    layer: "pts-impossible",
    color: "#7c3aed",
    prop: "x",
    fit: false, // their coordinates are literally wrong; flying to them is nonsense
  },
];

/**
 * Decode the compact layer into a MapLibre FeatureCollection.
 *
 * `pts` is [[lon, lat, flags], ...] with flags a bitmask (1 isolated, 2
 * roadless, 4 impossible); `meta` carries name + province for exactly the
 * flagged points — those are the only ones a popup is useful for.
 */
function decode(data) {
  const features = new Array(data.pts.length);
  for (let i = 0; i < data.pts.length; i++) {
    const [lon, lat, f] = data.pts[i];
    features[i] = {
      type: "Feature",
      geometry: { type: "Point", coordinates: [lon, lat] },
      properties: {
        i: f & 1 ? 1 : 0,
        r: f & 2 ? 1 : 0,
        x: f & 4 ? 1 : 0,
        n: null,
        p: null,
      },
    };
  }
  for (const [idx, name, province] of data.meta) {
    features[idx].properties.n = name;
    features[idx].properties.p = province;
  }
  return { type: "FeatureCollection", features };
}

/** Counts recomputed from the flags, so the chips always match the dots. */
function countFlags(features) {
  const counts = {
    all: features.length,
    isolated: 0,
    roadless: 0,
    impossible: 0,
  };
  for (const f of features) {
    if (f.properties.i) counts.isolated++;
    if (f.properties.r) counts.roadless++;
    if (f.properties.x) counts.impossible++;
  }
  return counts;
}

async function loadStoryPoints() {
  const res = await fetch(url("kopdes_story_points.json"));
  if (!res.ok) throw new Error(`kopdes_story_points.json -> ${res.status}`);
  const data = await res.json();
  const collection = decode(data);
  return { collection, counts: countFlags(collection.features) };
}

function boundsFor(features) {
  const b = { n: -90, s: 90, e: -180, w: 180 };
  for (const f of features) {
    const [lon, lat] = f.geometry.coordinates;
    if (lat > b.n) b.n = lat;
    if (lat < b.s) b.s = lat;
    if (lon > b.e) b.e = lon;
    if (lon < b.w) b.w = lon;
  }
  return [
    [b.w, b.s],
    [b.e, b.n],
  ];
}

/** Intersect a [[w, s], [e, n]] box with Indonesia, so a filter whose points
 *  include bad coordinates can never fitBounds to the whole world. */
function clampToIndonesia(bounds) {
  const [[w, s], [e, n]] = bounds;
  return [
    [Math.max(w, INDONESIA_BOUNDS[0][0]), Math.max(s, INDONESIA_BOUNDS[0][1])],
    [Math.min(e, INDONESIA_BOUNDS[1][0]), Math.min(n, INDONESIA_BOUNDS[1][1])],
  ];
}

function renderChips(container, counts, onPick) {
  for (const f of FILTERS) {
    const el = document.createElement("button");
    el.type = "button";
    el.className = "map-chip";
    el.dataset.filter = f.id;
    el.innerHTML = `${f.label} <span class="chip-count">${counts[f.id].toLocaleString("id-ID")}</span>`;
    el.addEventListener("click", () => onPick(f.id));
    container.appendChild(el);
  }
}

export async function initStoryMap() {
  const container = document.getElementById("story-map");
  const tools = document.getElementById("story-map-tools");
  const loading = document.getElementById("story-map-loading");
  const attrib = document.getElementById("story-map-attrib");

  if (!container || !window.maplibregl) {
    if (loading) loading.textContent = "Peta tidak dapat dimuat.";
    return;
  }

  const map = new window.maplibregl.Map({
    container,
    style: BASEMAP_BY_ID.terang.style,
    center: INDONESIA.center,
    zoom: INDONESIA.zoom,
    // Wheel zoom works, but only when the pointer is over the map — MapLibre's
    // scroll handler fires on the canvas alone, so the page keeps scrolling
    // everywhere else.
    scrollZoom: true,
    // The camera stays inside Indonesia no matter what a filter does.
    maxBounds: INDONESIA_BOUNDS,
    dragRotate: false,
    pitchWithRotate: false,
    attributionControl: {
      compact: true,
      customAttribution:
        "Data: SIMKOPDES 13-08-2026 · Koperasi Desa Merah Putih",
    },
  });
  map.addControl(
    new window.maplibregl.NavigationControl({ showCompass: false }),
    "top-right",
  );

  if (attrib) {
    attrib.textContent =
      "Basemap: © OpenFreeMap · OpenStreetMap contributors. Titik: SIMKOPDES 13-08-2026.";
  }

  // The compact layer is tiny; start fetching it in parallel with the basemap.
  // Data is applied on "style.load" (style JSON applied, before any tiles) as
  // well as "load", so the dots appear even if the basemap tiles are slow or
  // blocked — the data never waits on the tiles.
  const dataPromise = loadStoryPoints();
  let applied = false;

  const apply = async () => {
    if (applied || !map.isStyleLoaded()) return; // load / style.load will re-fire
    applied = true;
    try {
      tintBasemap(map);
      const { collection, counts } = await dataPromise;

      map.addSource("points", { type: "geojson", data: collection });

      const layers = [
        // "Semua" in a warm brown — the report's palette, not a dead grey.
        ["pts-all", "#6b4a34", 1.6, 0.72, null],
        ["pts-isolated", "#d62828", 3.2, 1, ["==", "i", 1]],
        ["pts-roadless", "#e8801f", 2.6, 0.95, ["==", "r", 1]],
        ["pts-impossible", "#7c3aed", 3.6, 1, ["==", "x", 1]],
      ];
      for (const [id, color, radius, opacity, filter] of layers) {
        map.addLayer({
          id,
          type: "circle",
          source: "points",
          filter: filter || ["all"],
          paint: {
            "circle-color": color,
            "circle-radius": radius,
            "circle-opacity": opacity,
            "circle-stroke-width": 0.6,
            "circle-stroke-color": "rgba(255,255,255,0.9)",
            "circle-stroke-opacity": opacity,
          },
        });
      }

      // Tooltip only where the data actually names a place (the flagged tail).
      const popup = new window.maplibregl.Popup({
        closeButton: false,
        closeOnClick: false,
        offset: 10,
        maxWidth: "260px",
      });
      map.on("mousemove", "pts-all", (e) => {
        const f = e.features.find((ft) => ft.properties.n);
        if (f) {
          map.getCanvas().style.cursor = "default";
          popup
            .setLngLat(f.geometry.coordinates)
            .setHTML(
              `<strong>${f.properties.n}</strong><br/><span style="color:#666;font-size:12px">${f.properties.p ?? ""}</span>`,
            )
            .addTo(map);
        }
      });
      map.on("mouseleave", "pts-all", () => {
        map.getCanvas().style.cursor = "";
        popup.remove();
      });

      // Filter chips, driven by the live counts.
      const byFilter = Object.fromEntries(FILTERS.map((f) => [f.id, f]));
      const showFilter = (id) => {
        for (const f of FILTERS) {
          const vis = f.id === id ? "visible" : "none";
          if (map.getLayer(f.layer))
            map.setLayoutProperty(f.layer, "visibility", vis);
        }
        tools
          .querySelectorAll(".map-chip")
          .forEach((c) =>
            c.classList.toggle("is-active", c.dataset.filter === id),
          );
        const active = byFilter[id];
        if (active.fit && counts[id] > 0) {
          const feats = collection.features.filter(
            (f) => !active.prop || f.properties[active.prop],
          );
          if (feats.length) {
            map.fitBounds(clampToIndonesia(boundsFor(feats)), {
              padding: { top: 70, bottom: 70, left: 60, right: 60 },
              maxZoom: 9,
              duration: 900,
            });
          }
        } else if (id === "all") {
          map.flyTo({ ...INDONESIA, duration: 900 });
        }
      };

      renderChips(tools, counts, showFilter);
      // Default: "Semua" active, the rest hidden.
      for (const f of FILTERS) {
        if (f.id !== "all")
          map.setLayoutProperty(f.layer, "visibility", "none");
      }
      const firstChip = tools.querySelector('.map-chip[data-filter="all"]');
      if (firstChip) firstChip.classList.add("is-active");

      if (loading) loading.classList.add("is-done");
    } catch (err) {
      console.error("story map data failed:", err);
      applied = false; // allow the timeout below to retry once
      if (loading) loading.textContent = "Data peta gagal dimuat.";
    }
  };

  map.on("load", apply);
  map.on("style.load", apply);
  // Safety net: if neither event fired (e.g. a blocked basemap CDN), try anyway.
  setTimeout(apply, 8000);

  // If the hosted basemap hasn't loaded within 6s, fall back to a plain
  // background so the map never sits blank — the data story is the point, the
  // tiles are decoration. setStyle() fires style.load, so apply() re-runs.
  setTimeout(() => {
    if (!map.isStyleLoaded()) {
      console.warn(
        "[story-map] basemap not loaded after 6s; using plain background",
      );
      applied = false;
      try {
        map.setStyle(FALLBACK_STYLE);
      } catch (_) {
        /* ignore */
      }
    }
  }, 6000);
}
