/**
 * data.js — the explorer's data layer.
 *
 * One DuckDB-wasm session over the committed parquet mart, plus the simplified
 * boundary GeoJSON. Nothing here knows how anything is drawn.
 *
 * Two properties worth keeping when this changes:
 *
 * - **Columns are pulled, not shipped.** DuckDB reads the parquet over HTTP
 *   range requests, so a `SELECT` of eleven columns transfers roughly eleven
 *   columns' worth of bytes out of the points file's sixty-odd. Adding a
 *   measure costs what that measure's columns cost, not a new download.
 * - **Wide integers are cast in SQL.** DuckDB hands HUGEINT and BIGINT back as
 *   BigInt, which throws the moment it meets a float in arithmetic or
 *   `JSON.stringify`. Casting to DOUBLE at the query boundary keeps every
 *   number that reaches the rest of the app a plain JS number.
 */

import * as duckdb from "@duckdb/duckdb-wasm"; // resolved via the import map
import {
  FAMILIES,
  LEVEL_BY_ID,
  MEASURES,
  classCodeSql,
  familyShareCols,
} from "./measures.js";

const DATA_ROOT = new URL("../../data/web/", import.meta.url).href;
const url = (name) => new URL(name, DATA_ROOT).href;

let connection = null;

/** Boot DuckDB-wasm and hold the connection for the page's lifetime. */
async function connect() {
  if (connection) return connection;
  const selected = await duckdb.selectBundle(duckdb.getJsDelivrBundles());
  // The worker script lives on a CDN, so it cannot be loaded as a same-origin
  // worker directly; the usual shim is a blob that importScripts() it.
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

/** Turn every wide integer that reaches the app into a plain JS number. */
function toPlain(v) {
  if (typeof v === "bigint") return Number(v);
  if (v && typeof v === "object") {
    if (Array.isArray(v)) return v.map(toPlain);
    const out = {};
    for (const k in v) out[k] = toPlain(v[k]);
    return out;
  }
  return v;
}

export async function rows(sql) {
  const con = await connect();
  const table = await con.query(sql);
  return table.toArray().map((r) => toPlain(r.toJSON()));
}

// ---------------------------------------------------------------------------
// Points
// ---------------------------------------------------------------------------

/** Point columns every measure and filter needs, deduplicated. */
function pointColumns() {
  const wanted = new Set();
  for (const m of MEASURES) for (const c of m.cols.point) wanted.add(c);
  // Class codes are computed, not stored; drop them from the plain column list
  // and let `classCodeSql` emit them instead.
  for (const f of FAMILIES) wanted.delete(`${f.id}_k`);
  return [...wanted];
}

/**
 * Every cooperative, as flat rows ready to hand straight to screengrid.
 *
 * Deliberately not GeoJSON: the layer only ever reads `longitude`/`latitude`
 * through `getPosition`, and wrapping 83.379 rows in Feature objects with
 * nested coordinate arrays triples the allocation for nothing.
 */
export async function loadPoints() {
  const classCodes = FAMILIES.map((f) => classCodeSql(f)).join(",\n    ");
  return rows(`
    SELECT
      -- BIGINT reaches JS as a BigInt, which MapLibre cannot serialise into a
      -- GeoJSON source ("Do not know how to serialize a BigInt") and which
      -- throws the moment it meets a float. Ids here top out around 94.000, so
      -- an INTEGER is exact and safe.
      cooperative_id::INTEGER AS cooperative_id,
      cooperative,
      province, district, subdistrict, village,
      -- Admin ids let a search hit on an area name resolve to the exact
      -- aggregate row, rather than flying to a name and hoping.
      province_id::INTEGER AS province_id,
      district_id::INTEGER AS district_id,
      subdistrict_id::INTEGER AS subdistrict_id,
      longitude, latitude,
      coordinate_suspect,
      ${classCodes},
      ${pointColumns().join(", ")},
      -- Inspector-only continuous columns. They ride along because they are
      -- cheap next to the class codes and because fetching them on click would
      -- put a network round trip inside a hover-to-click gesture.
      pop_within_1_4km,
      km_non_track,
      m_to_nearest_other,
      transaction_value::DOUBLE AS transaction_value,
      imagery_url
    FROM read_parquet('${url("kopdes_points.parquet")}')
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
  `);
}

// ---------------------------------------------------------------------------
// Administrative aggregates
// ---------------------------------------------------------------------------

/** Aggregate columns the glyphs, legend and inspector read, deduplicated. */
function aggColumns() {
  const wanted = new Set();
  for (const m of MEASURES) for (const c of m.cols.agg) wanted.add(c);
  for (const f of FAMILIES) for (const c of familyShareCols(f)) wanted.add(c);
  for (const c of [
    "median_pop_within_1_4km",
    "median_km_to_road",
    "median_km_to_minimarket",
    "median_m_to_nearest_other",
    "pct_zero_population_cell",
    "pct_no_road_within_5km",
    "pct_sibling_within_1km",
  ])
    wanted.add(c);
  return [...wanted];
}

/** Aggregate columns the SELECT already names explicitly (and casts to a
 *  JS-safe type). `aggColumns()` must not re-emit these: a duplicate column
 *  name makes DuckDB keep the LAST occurrence in the result, which silently
 *  defeats the ::DOUBLE cast and hands the app a BigInt — the `cooperatives`
 *  collision with the farmland measure is exactly how that happened. */
const EXPLICIT_AGG_COLS = new Set([
  "cooperatives",
  "coordinate_suspect",
  "villages",
  "villages_reporting",
  "transaction_value",
]);

/**
 * One admin level as a FeatureCollection of anchor points, which is what
 * screengrid's `feature-anchors` render mode consumes.
 *
 * `weight` is set to the cooperative count because the layer derives its
 * normalised value as `weight / maxWeight` — putting the count there means the
 * glyph gets a sensible size envelope for free.
 *
 * Rows without an anchor are dropped. A handful of subdistricts have no usable
 * coordinate at all (every member cooperative is one of report 08's impossible
 * points), and there is nowhere honest to put them on a map.
 */
export async function loadLevel(levelId) {
  const level = LEVEL_BY_ID[levelId];
  const labels = [level.nameCol, ...level.parentCols];
  const aggCols = aggColumns().filter((c) => !EXPLICIT_AGG_COLS.has(c));
  const data = await rows(`
    SELECT
      -- INTEGER, not the native BIGINT: this id is compared against the ids in
      -- the search index and used as a MapLibre feature-state key, and a BigInt
      -- is never === a plain number.
      ${level.key}::INTEGER AS admin_id,
      ${labels.join(", ")},
      cooperatives::DOUBLE AS cooperatives,
      coordinate_suspect::DOUBLE AS coordinate_suspect,
      villages::DOUBLE AS villages,
      villages_reporting::DOUBLE AS villages_reporting,
      transaction_value::DOUBLE AS transaction_value,
      anchor_lat, anchor_lon,
      ${aggCols.join(", ")}
    FROM read_parquet('${url(level.table + ".parquet")}')
    WHERE anchor_lat IS NOT NULL AND anchor_lon IS NOT NULL
    -- Smallest first. feature-anchors draws in source order with no depth
    -- sorting, so whatever comes last wins the overlap. Around Java the
    -- anchors are closer together than the glyphs are wide. Ascending order
    -- puts the largest areas on top, which is the standard rule for
    -- proportional symbols and the only order in which the big ones stay
    -- visible at all.
    ORDER BY cooperatives ASC
  `);

  return {
    type: "FeatureCollection",
    features: data.map((r) => ({
      type: "Feature",
      id: r.admin_id,
      geometry: { type: "Point", coordinates: [r.anchor_lon, r.anchor_lat] },
      properties: { ...r, name: r[level.nameCol], weight: r.cooperatives },
    })),
  };
}

// ---------------------------------------------------------------------------
// Boundaries
// ---------------------------------------------------------------------------

const boundaryCache = new Map();

/**
 * Simplified admin polygons from `scripts/build_boundaries.py`.
 *
 * Fetched lazily and cached: kecamatan is 8 MB and most readers never open
 * that level, so loading all three up front would be most of the page weight
 * spent on a layer nobody asked for.
 *
 * Not every aggregate row has a polygon — 25 kabupaten and 42 kecamatan in the
 * SIMKOPDES export carry names that match no boundary, which `geo/README.md`
 * traces to bad data in the export rather than to the name matching. Those
 * areas still get an anchor glyph; they just have no fill behind it.
 */
export async function loadBoundaries(levelId) {
  const level = LEVEL_BY_ID[levelId];
  if (!level?.boundaries) return null;
  const name = level.boundaries;
  if (boundaryCache.has(name)) return boundaryCache.get(name);

  const promise = fetch(url(`boundaries/${name}.geojson`))
    .then((res) => {
      if (!res.ok)
        throw new Error(`boundaries/${name}.geojson -> ${res.status}`);
      return res.json();
    })
    .catch((err) => {
      // A missing boundary file degrades the map to anchor glyphs, which is
      // still a working map. Drop the rejected promise so a later switch back
      // to this level retries instead of replaying the failure.
      boundaryCache.delete(name);
      throw err;
    });

  boundaryCache.set(name, promise);
  return promise;
}

/** Snapshot metadata for the provenance line in the rail. */
export async function loadManifest() {
  const res = await fetch(url("mart_manifest.json"));
  if (!res.ok) throw new Error(`mart_manifest.json -> ${res.status}`);
  return res.json();
}

/**
 * The Kisi Provinsi cartogram grid, keyed by SIMKOPDES province_id.
 *
 * Built by scripts/build_province_cartogram.py from the geo-morpher example
 * layout; the regular side of the morph is the same provinsi boundary the
 * plain Provinsi scale already draws.
 */
export async function loadProvinceCartogram() {
  const res = await fetch(url("cartogram/provinsi_grid.csv"));
  if (!res.ok) throw new Error(`cartogram/provinsi_grid.csv -> ${res.status}`);
  return res.text();
}
