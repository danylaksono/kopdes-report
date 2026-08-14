/**
 * index.js — controller for /periksa/ ("Periksa mandiri").
 *
 * The problem this page addresses is stated on the front page of the report:
 * every coordinate we analyse comes from SIMKOPDES, and SIMKOPDES says its own
 * map positions are representative visualisations per area, not precise
 * locations. Every proximity finding in the investigation inherits that
 * uncertainty, and until a verified coordinate set exists there is no way to
 * remove it.
 *
 * What this page can do in the meantime is *measure* it. A reader who knows
 * where a cooperative actually stands drops a pin, and the same five analyses
 * the report runs nationally are re-run at that point, in the browser, against
 * the same data. The output is the difference between the two readings — how
 * much the verdict depends on the coordinate being right.
 *
 * ## Interim by design
 *
 * There is no backend and nothing is submitted. This is the honest version of
 * a crowdsourced correction tool that has not been built yet: it gives a reader
 * the same instrument we used, applied to the point they care about, without
 * pretending a report has been filed or received. The reader's own URL is the
 * only record, which is why the coordinate round-trips through the hash.
 *
 * ## Structure
 *
 *   analysis.js  the five measures at one coordinate (the engine)
 *   ui.js        two-column comparison, verdict, provenance
 *   index.js     this file: state, map, picker, orchestration
 *
 * The map, basemaps and DuckDB session are all reused from the explorer rather
 * than re-implemented, so a change to the retint or the parquet session reaches
 * this page too.
 */

import { BASEMAP_BY_ID, tintBasemap } from "../explore/basemaps.js";
import { rows } from "../explore/data.js";
import { analysePoint, cooperativesWithin, moveDistance } from "./analysis.js";
import { createOverlays, OVERLAYS } from "./layers.js";
import { createRuler } from "./ruler.js";
import {
  renderComparison,
  renderProvenance,
  renderReportLink,
  renderResults,
  renderVerdict,
} from "./ui.js";

const POINTS = new URL("../../data/web/kopdes_points.parquet", import.meta.url)
  .href;
const MANIFEST = new URL(
  "../../data/web/cells/cells_manifest.json",
  import.meta.url,
).href;

const el = (id) => document.getElementById(id);

const state = {
  points: [],
  selected: null,
  official: null,
  reported: null,
  marker: null,
  map: null,
  overlays: null,
  ruler: null,
  /** Which overlays the reader has switched on, kept across re-analyses. */
  overlayOn: new Set(),
  /** Guards against a slow analysis landing after the reader has moved on. */
  generation: 0,
};

// ---------------------------------------------------------------------------
// Data
// ---------------------------------------------------------------------------

/**
 * The cooperative list, lean.
 *
 * Only what the picker, the map and the nearest-neighbour scan need. The mart's
 * own measure columns are deliberately NOT loaded: this page recomputes both
 * sides itself so the comparison cannot be contaminated by a difference in
 * method (see analysis.js).
 */
async function loadPoints() {
  return rows(`
    SELECT
      cooperative_id::INTEGER AS cooperative_id,
      cooperative, province, district, subdistrict, village,
      longitude AS lon, latitude AS lat,
      coordinate_suspect
    FROM read_parquet('${POINTS}')
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
  `);
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

/** Fold to a comparable key: SIMKOPDES names are shouty and inconsistent. */
const norm = (s) => (s ?? "").toLowerCase().replace(/\s+/g, " ").trim();

function search(query, limit = 8) {
  const q = norm(query);
  if (q.length < 3) return [];
  const out = [];
  for (const p of state.points) {
    if (
      norm(p.cooperative).includes(q) ||
      norm(p.village).includes(q) ||
      norm(p.subdistrict).includes(q)
    ) {
      out.push(p);
      if (out.length >= limit) break;
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Map
// ---------------------------------------------------------------------------

function initMap() {
  const base = BASEMAP_BY_ID.satelit; // imagery is the point: you look, then you place
  const map = new maplibregl.Map({
    container: "map",
    style: base.style,
    center: [117.5, -2.2],
    zoom: 4,
    attributionControl: { compact: true },
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }));
  map.on("style.load", () => {
    if (base.tint) tintBasemap(map);
  });
  // Clicking the imagery is the primary way to place a correction; dragging the
  // marker is the refinement. Both funnel through the same setter.
  map.on("click", (e) => {
    // While the ruler is on, a click measures. Letting both handlers fire would
    // silently rewrite the analysis every time someone measured something.
    if (state.ruler?.isActive()) return;
    setReported(e.lngLat.lat, e.lngLat.lng);
  });
  return map;
}

/** Overlay checkboxes and the ruler button, once the map can take layers. */
function initMapTools() {
  state.overlays = createOverlays(state.map);
  state.ruler = createRuler(state.map);

  const box = el("overlay-toggles");
  for (const o of OVERLAYS) {
    const row = document.createElement("label");
    row.className = "tool-toggle";
    row.innerHTML = `
      <input type="checkbox" value="${o.id}" />
      <span class="swatch" style="--sw:${o.color}"></span>
      <span class="tool-label">${o.label}<span class="tool-hint">${o.hint}</span></span>`;
    const input = row.querySelector("input");
    input.addEventListener("change", () => {
      if (input.checked) state.overlayOn.add(o.id);
      else state.overlayOn.delete(o.id);
      state.overlays.setVisible(o.id, input.checked);
    });
    box.append(row);
  }

  const btn = el("ruler-btn");
  const readout = el("ruler-readout");
  btn.addEventListener("click", () => state.ruler.toggle());
  // The button reflects state rather than setting it, because the ruler can
  // also end itself on a double-click or Escape and a button that only updated
  // on its own click would then be lying.
  state.ruler.onChange(({ metres, vertices, active }) => {
    btn.setAttribute("aria-pressed", String(active));
    btn.textContent = active ? "Selesai mengukur" : "Ukur jarak";
    el("map-tools").classList.toggle("ruler-on", active);
    const km = (metres / 1000).toLocaleString("id-ID", {
      maximumFractionDigits: 2,
    });
    const shown =
      metres < 1000 ? `${Math.round(metres).toLocaleString("id-ID")} m` : `${km} km`;
    readout.textContent =
      vertices >= 2
        ? `${vertices} titik · ${shown}`
        : active
          ? "Klik pada peta untuk menambah titik. Klik ganda atau Esc untuk selesai."
          : "Ukur jarak bebas di atas citra.";
  });

  el("map-tools").hidden = false;
}

/** Redraw the overlays for whichever point the reader is currently looking at. */
function refreshOverlays(result) {
  if (!state.overlays || !result) return;
  const coops = state.selected
    ? cooperativesWithin(
        result.lat,
        result.lon,
        state.points,
        state.selected.cooperative_id,
      )
    : [];
  state.overlays.update(result, coops);
  for (const o of OVERLAYS) {
    state.overlays.setVisible(o.id, state.overlayOn.has(o.id));
  }
}

/** The official coordinate: a fixed reference dot, never draggable. */
function showOfficialMarker(p) {
  if (state.officialMarker) state.officialMarker.remove();
  const node = document.createElement("div");
  node.className = "pin pin-official";
  node.title = "Koordinat SIMKOPDES";
  state.officialMarker = new maplibregl.Marker({ element: node })
    .setLngLat([p.lon, p.lat])
    .addTo(state.map);
}

function setReported(lat, lon) {
  if (!state.selected) return;
  state.reported = { lat, lon };
  if (!state.marker) {
    const node = document.createElement("div");
    node.className = "pin pin-reported";
    node.title = "Titik yang Anda tandai";
    state.marker = new maplibregl.Marker({ element: node, draggable: true })
      .setLngLat([lon, lat])
      .addTo(state.map);
    state.marker.on("dragend", () => {
      const { lat: y, lng: x } = state.marker.getLngLat();
      state.reported = { lat: y, lon: x };
      runAnalysis();
    });
  } else {
    state.marker.setLngLat([lon, lat]);
  }
  runAnalysis();
}

// ---------------------------------------------------------------------------
// Flow
// ---------------------------------------------------------------------------

function selectCooperative(p, { fly = true } = {}) {
  state.selected = p;
  state.reported = null;
  if (state.marker) {
    state.marker.remove();
    state.marker = null;
  }
  el("results").innerHTML = "";
  el("search").value = p.cooperative;

  el("chosen").hidden = false;
  el("chosen").innerHTML = `
    <h2>${p.cooperative}</h2>
    <p class="chosen-where">${p.village ?? "—"}, Kec. ${p.subdistrict ?? "—"},
      ${p.district ?? "—"}, ${p.province ?? "—"}</p>
    <p class="chosen-coord">Koordinat SIMKOPDES:
      <code>${p.lat.toFixed(6)}, ${p.lon.toFixed(6)}</code>
      ${
        p.coordinate_suspect
          ? `<span class="flag">Koordinat ini sudah ditandai janggal dalam
             <a href="../methods/08-exact-geometry/">pemeriksaan geometri</a>
             kami.</span>`
          : ""
      }
    </p>
    <p class="chosen-hint">Klik pada citra satelit di titik gedung koperasi yang
      sebenarnya, lalu geser penanda merah bila perlu.</p>`;

  showOfficialMarker(p);
  if (fly) state.map.flyTo({ center: [p.lon, p.lat], zoom: 16, duration: 900 });
  runAnalysis();
  writeHash();
}

/**
 * Recompute both sides and render.
 *
 * The official side is recomputed on every run rather than cached with the
 * cooperative: it costs one extra set of range requests, all of which the
 * browser has already cached by the second run, and it keeps a single code path
 * for both columns.
 */
/**
 * Show or hide the busy veil over the comparison.
 *
 * The veil covers the table rather than sitting beside it, and dims what is
 * underneath, because the failure mode it exists to prevent is a reader taking
 * the previous point's numbers for the current point's. A status line below the
 * table would not stop that; an obscured table does.
 */
function setBusy(on, text) {
  const panel = el("comparison-panel");
  const busy = el("busy");
  panel.classList.toggle("is-busy", on);
  el("comparison").classList.toggle("is-stale", on);
  busy.hidden = !on;
  if (text) el("busy-text").textContent = text;
}

async function runAnalysis() {
  if (!state.selected) return;
  const token = ++state.generation;
  const status = el("analysis-status");
  status.hidden = true;
  setBusy(
    true,
    state.reported
      ? "Menghitung ulang di kedua titik…"
      : "Menghitung pada koordinat resmi…",
  );

  const opts = { points: state.points, excludeId: state.selected.cooperative_id };
  try {
    const official = await analysePoint(
      state.selected.lat,
      state.selected.lon,
      opts,
    );
    const reported = state.reported
      ? await analysePoint(state.reported.lat, state.reported.lon, opts)
      : null;
    if (token !== state.generation) return; // a newer run has taken over

    state.official = official;
    const moved = reported ? moveDistance(official, reported) : null;
    el("comparison").hidden = false;
    renderComparison(el("comparison"), { official, reported, moved });
    renderVerdict(el("verdict"), { official, reported, moved });
    renderReportLink(el("report"), {
      coop: state.selected,
      official,
      reported: state.reported,
      moved,
    });
    // The overlays describe the point the reader is asking about, which is the
    // marked one once there is one.
    refreshOverlays(reported ?? official);
    setBusy(false);
    writeHash();
  } catch (err) {
    if (token !== state.generation) return;
    setBusy(false);
    status.hidden = false;
    status.textContent = `Analisis gagal: ${err.message}`;
    console.error(err);
  }
}

// ---------------------------------------------------------------------------
// Shareable state
// ---------------------------------------------------------------------------

/**
 * The URL is the only place a result is kept.
 *
 * Nothing is submitted anywhere, so a reader who wants to pass a correction on
 * copies the link. Six decimals is ~0,1 m, well past the precision anyone can
 * claim from imagery, and keeps the hash short.
 */
function writeHash() {
  if (!state.selected) return;
  const parts = [`k=${state.selected.cooperative_id}`];
  if (state.reported) {
    parts.push(
      `p=${state.reported.lat.toFixed(6)},${state.reported.lon.toFixed(6)}`,
    );
  }
  history.replaceState(null, "", `#${parts.join("&")}`);
}

function readHash() {
  const raw = location.hash.replace(/^#/, "");
  if (!raw) return null;
  const out = {};
  for (const part of raw.split("&")) {
    const [k, v] = part.split("=");
    out[k] = v;
  }
  const coopId = Number(out.k);
  if (!Number.isFinite(coopId)) return null;
  const p = out.p?.split(",").map(Number);
  return {
    cooperativeId: coopId,
    reported: p && p.length === 2 && p.every(Number.isFinite)
      ? { lat: p[0], lon: p[1] }
      : null,
  };
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

async function boot() {
  const status = el("status");
  state.map = initMap();
  // Sources and layers can only be added once the style is in place, and
  // `load` is the event that guarantees both style and first render.
  const mapReady = new Promise((resolve) => state.map.on("load", resolve));

  try {
    const [points, manifest] = await Promise.all([
      loadPoints(),
      fetch(MANIFEST)
        .then((r) => (r.ok ? r.json() : null))
        .catch(() => null),
    ]);
    state.points = points;
    renderProvenance(el("provenance"), manifest);
    status.hidden = true;
    el("picker").hidden = false;
    await mapReady;
    initMapTools();
  } catch (err) {
    status.textContent = `Gagal memuat data: ${err.message}`;
    console.error(err);
    return;
  }

  const searchBox = el("search");
  searchBox.addEventListener("input", () => {
    renderResults(el("results"), search(searchBox.value), (p) =>
      selectCooperative(p),
    );
  });

  // A shared link restores both the cooperative and the marked point.
  const restored = readHash();
  if (restored) {
    const p = state.points.find(
      (x) => x.cooperative_id === restored.cooperativeId,
    );
    if (p) {
      selectCooperative(p, { fly: false });
      if (restored.reported) {
        setReported(restored.reported.lat, restored.reported.lon);
        // Frame BOTH points. A shared link is someone showing you a
        // disagreement about where a cooperative is, so opening it centred on
        // one pin with the other off-screen hides the entire subject. Padded
        // and zoom-capped so a correction of a few metres does not open at
        // street level with two dots on top of each other.
        state.map.fitBounds(
          [
            [Math.min(p.lon, restored.reported.lon), Math.min(p.lat, restored.reported.lat)],
            [Math.max(p.lon, restored.reported.lon), Math.max(p.lat, restored.reported.lat)],
          ],
          { padding: 90, maxZoom: 17, duration: 0 },
        );
      } else {
        state.map.jumpTo({ center: [p.lon, p.lat], zoom: 16 });
      }
    }
  }
}

boot();
