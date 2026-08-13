/** story-map.js — the "Momen peta" interlude on the home page.
 *
 * A MapLibre map over the SAME committed parquet the explorer uses (one shared
 * data layer): every cooperative as a point, plus three data-grounded filter
 * layers — the truly isolated (report 03), the roadless (05/08), and the
 * impossible coordinates (08). The counts on the chips come from the query, so
 * they can never drift from the mart.
 *
 * Deliberately a lighter instrument than the explorer: scroll zoom is off (so
 * the page keeps scrolling), the chips are a radio group, and everything here
 * is a gateway to /explore/.
 */

import * as duckdb from "@duckdb/duckdb-wasm"; // resolved via the import map
import { BASEMAP_BY_ID, tintBasemap } from "./explore/basemaps.js";

const DATA_ROOT = new URL("../data/web/", import.meta.url).href;
const url = (name) => new URL(name, DATA_ROOT).href;

const INDONESIA = {
  center: [119.3, -2.1],
  zoom: 4.15,
};

const FILTERS = [
  {
    id: "all",
    label: "Semua",
    layer: "pts-all",
    color: "#b3a896",
    fit: true,
  },
  {
    id: "isolated",
    label: "Terpencil",
    layer: "pts-isolated",
    color: "#d62828",
    prop: "isolated",
    fit: true,
  },
  {
    id: "roadless",
    label: "Tanpa jalan",
    layer: "pts-roadless",
    color: "#e8801f",
    prop: "roadless",
    fit: true,
  },
  {
    id: "impossible",
    label: "Di luar Indonesia",
    layer: "pts-impossible",
    color: "#7c3aed",
    prop: "impossible",
    fit: false, // their coordinates are literally wrong; flying to them is nonsense
  },
];

let connection = null;

/** Boot DuckDB-wasm (same shim as the explorer) and hold the connection. */
async function connect() {
  if (connection) return connection;
  const selected = await duckdb.selectBundle(duckdb.getJsDelivrBundles());
  const workerUrl = URL.createObjectURL(
    new Blob([`importScripts("${selected.mainWorker}");`], {
      type: "text/javascript",
    }),
  );
  const worker = new Worker(workerUrl);
  const db = new duckdb.AsyncDuckDB(new duckdb.VoidLogger(), worker);
  await db.instantiate(selected.mainModule, selected.pthreadWorker);
  URL.revokeObjectURL(workerUrl);
  connection = await db.connect();
  return connection;
}

async function loadPoints() {
  const con = await connect();
  const table = await con.query(`
    SELECT
      cooperative_id::INTEGER AS id,
      cooperative,
      province,
      longitude, latitude,
      (remoteness_band = 'nobody within 5km') AS isolated,
      (km_non_track IS NULL)                      AS roadless,
      coordinate_suspect                          AS impossible
    FROM read_parquet('${url("kopdes_points.parquet")}')
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
  `);
  const rows = table.toArray().map((r) => r.toJSON());
  const features = rows.map((r) => ({
    type: "Feature",
    geometry: { type: "Point", coordinates: [r.longitude, r.latitude] },
    properties: {
      id: r.id,
      name: r.cooperative,
      province: r.province,
      isolated: r.isolated ? 1 : 0,
      roadless: r.roadless ? 1 : 0,
      impossible: r.impossible ? 1 : 0,
    },
  }));
  return {
    type: "FeatureCollection",
    features,
    counts: {
      all: rows.length,
      isolated: rows.reduce((n, r) => n + (r.isolated ? 1 : 0), 0),
      roadless: rows.reduce((n, r) => n + (r.roadless ? 1 : 0), 0),
      impossible: rows.reduce((n, r) => n + (r.impossible ? 1 : 0), 0),
    },
  };
}

function boundsFor(features) {
  const b = {
    n: -90,
    s: 90,
    e: -180,
    w: 180,
  };
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

function renderChips(container, counts, onPick) {
  const chips = FILTERS.map((f) => {
    const el = document.createElement("button");
    el.type = "button";
    el.className = "map-chip";
    el.dataset.filter = f.id;
    el.innerHTML = `${f.label} <span class="chip-count">${counts[f.id].toLocaleString("id-ID")}</span>`;
    el.addEventListener("click", () => onPick(f.id));
    container.appendChild(el);
    return el;
  });
  return chips;
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
    // The page scrolls; the map must not eat the wheel.
    scrollZoom: false,
    dragRotate: false,
    pitchWithRotate: false,
    attributionControl: {
      compact: true,
      customAttribution:
        "Data: SIMKOPDES 2026-08-05 · Kooperasi Koperasi Desa Merah Putih",
    },
  });
  map.addControl(
    new window.maplibregl.NavigationControl({ showCompass: false }),
    "top-right",
  );

  if (attrib) {
    attrib.textContent =
      "Basemap: © OpenFreeMap · OpenStreetMap contributors. Titik: SIMKOPDES 2026-08-05.";
  }

  // Start the DuckDB download immediately, in parallel with the basemap —
  // gating it behind map "load" would put the wasm fetch after the tiles.
  const dataPromise = loadPoints();

  map.on("load", async () => {
    try {
      tintBasemap(map);
      const data = await dataPromise;
      data.features.forEach((f) => {
        f.properties.name = f.properties.name || "Koperasi tanpa nama";
      });

      map.addSource("points", { type: "geojson", data });

      const layers = [
        ["pts-all", "#b3a896", 1.5, 0.62, null],
        ["pts-isolated", "#d62828", 3.2, 1, ["==", "isolated", 1]],
        ["pts-roadless", "#e8801f", 2.6, 0.95, ["==", "roadless", 1]],
        ["pts-impossible", "#7c3aed", 3.6, 1, ["==", "impossible", 1]],
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

      // Tooltip with the cooperative's name + province on hover.
      const popup = new window.maplibregl.Popup({
        closeButton: false,
        closeOnClick: false,
        offset: 10,
        maxWidth: "260px",
      });
      map.on("mousemove", "pts-all", (e) => {
        if (e.features.length) {
          const f = e.features[0];
          map.getCanvas().style.cursor = "default";
          popup
            .setLngLat(f.geometry.coordinates)
            .setHTML(
              `<strong>${f.properties.name}</strong><br/><span style="color:#666;font-size:12px">${f.properties.province ?? ""}</span>`,
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
        if (active.fit && data.counts[id] > 0) {
          const feats = data.features.filter(
            (f) => !active.prop || f.properties[active.prop],
          );
          if (feats.length) {
            map.fitBounds(boundsFor(feats), {
              padding: { top: 70, bottom: 70, left: 60, right: 60 },
              maxZoom: 9,
              duration: 900,
            });
          }
        } else if (id === "all") {
          map.flyTo({ ...INDONESIA, duration: 900 });
        }
      };

      renderChips(tools, data.counts, showFilter);
      // Default: "Semua" active, others hidden.
      for (const f of FILTERS) {
        if (f.id !== "all") {
          map.setLayoutProperty(f.layer, "visibility", "none");
        }
      }
      const firstChip = tools.querySelector('.map-chip[data-filter="all"]');
      if (firstChip) firstChip.classList.add("is-active");

      if (loading) loading.classList.add("is-done");
    } catch (err) {
      console.error("story map data failed:", err);
      if (loading) loading.textContent = "Data peta gagal dimuat.";
    }
  });
}
