/**
 * analysis.js — the measurement engine behind /periksa/.
 *
 * This module answers, for one arbitrary coordinate, the same five questions
 * the reports answer for all 83.379 cooperatives at once. It is the whole
 * reason the page can exist without a backend.
 *
 * ## The method is copied, not reinvented
 *
 * Every measure here mirrors a specific report, at the same resolution, with
 * the same ring-to-distance conversion:
 *
 *   population   reports/03  H3 r8 disks, k = 0 / 3 / 11 (0,2 / 1,4 / 5,1 km)
 *   road         reports/05  H3 r10 outward rings, km = k x 0.132, cap k = 38
 *   building     reports/17  H3 r10 outward rings, same k's as roads
 *   minimarket   reports/06  exact great-circle to tier-1 POIs
 *   nearest KDMP reports/10  exact great-circle to the other cooperatives
 *
 * Roads and buildings stay banded because that is what the cell index can
 * honestly support: an r10 cell is ~132 m across, so "k x 132 m" is a band, not
 * a metric, and rounding it to a precise-looking number would misstate the
 * resolution. Minimarkets and cooperatives are point sets, so the exact
 * distance is available and is what the mart's `m_to_minimarket_exact` and
 * `m_to_nearest_other` already hold.
 *
 * ## Why both coordinates are recomputed here
 *
 * The page could read the SIMKOPDES-coordinate figures straight out of
 * `kopdes_points.parquet` and only compute the reported one. It deliberately
 * does not. If the two sides came from different code, any difference in
 * method would surface as a difference in the answer, and the delta — which is
 * the entire output of this page — would be measuring our own inconsistency.
 * Both points go through the identical function.
 *
 * ## Ids stay hex, never BigInt
 *
 * `rows()` casts wide integers to plain JS numbers, which is lossy above 2^53,
 * and every H3 id is far above it. So the queries return `lower(to_hex(h3))`
 * and the join happens on the hex string, which is h3-js's own native
 * representation. Nothing here ever converts a cell id to a Number.
 *
 * ## Query shape
 *
 * `data/web/cells/*.parquet` are sorted by `h3` and carry a coarse parent `p`
 * (r7 for the r10 indexes, r5 for population). Asking for the ~21 parents that
 * cover a 5 km disk prunes to a couple of row groups: measured at 59 KB median,
 * 1 MB worst case, out of a 13 MB file. See scripts/build_cell_indexes.py.
 */

import {
  cellToParent,
  greatCircleDistance,
  gridDiskDistances,
  latLngToCell,
} from "https://cdn.jsdelivr.net/npm/h3-js@4.5.0/+esm";
import { rows } from "../explore/data.js";

const CELLS = new URL("../../data/web/cells/", import.meta.url).href;
const url = (n) => new URL(n, CELLS).href;

// ---------------------------------------------------------------------------
// Constants, all inherited from the reports
// ---------------------------------------------------------------------------

/** Adjacent r10 cell centres, approximately. reports/05 and /17. */
export const KM_PER_RING = 0.132;

/** Ring cap: 38 x 132 m is about 5 km, past which the reports stop looking. */
export const MAX_K = 38;

const RES_FINE = 10;
const RES_POP = 8;
const PARENT_FINE = 7;
const PARENT_POP = 5;

/** reports/03's k-ring radii: k -> the approximate ground distance it means. */
export const POP_RINGS = [
  { k: 0, km: 0.2, key: "own_cell" },
  { k: 3, km: 1.4, key: "within_1_4km" },
  { k: 11, km: 5.1, key: "within_5_1km" },
];

/** The road/building bands, nearest first, exactly as reports/05 and /17 name them. */
export const BANDS = [
  { k: 0, id: "on_cell" },
  { k: 2, id: "under_260m" },
  { k: 4, id: "under_530m" },
  { k: 8, id: "under_1km" },
  { k: 15, id: "under_2km" },
  { k: 38, id: "under_5km" },
];

/**
 * Band id for a ring index, or null when nothing was found inside the cap.
 *
 * A threshold walk, not a lookup table keyed on the band's own k. Report 17
 * used the lookup and it silently dropped every cooperative whose nearest
 * building sat on an off-key ring (1, 3, 5, 6, 7, 9-14, 16-37) into the
 * "nothing within 5 km" bucket, which is how 14,88% was published as 62,6%.
 * Recomputing this measure here is what surfaced the discrepancy.
 */
export function bandFor(k) {
  if (k == null) return null;
  for (const b of BANDS) if (k <= b.k) return b.id;
  return null;
}

// ---------------------------------------------------------------------------
// H3 helpers
// ---------------------------------------------------------------------------

/**
 * The disk of cells within `maxK` rings, as a Map from cell id to ring index.
 *
 * `gridDiskDistances` returns the disk already grouped by ring, so this is one
 * call and one pass. Growing the disk ring by ring with repeated `gridDisk`
 * calls would regenerate the whole interior 38 times over.
 */
function diskWithRings(origin, maxK) {
  const ringOf = new Map();
  const byRing = gridDiskDistances(origin, maxK);
  for (let k = 0; k < byRing.length; k++) {
    for (const cell of byRing[k]) ringOf.set(cell, k);
  }
  return ringOf;
}

/** Distinct coarse parents covering a cell collection, as SQL string literals. */
function parentList(cells, parentRes) {
  const out = new Set();
  for (const c of cells) out.add(`'${cellToParent(c, parentRes)}'`);
  return [...out];
}

/**
 * Fetch the cells of `file` whose coarse parent covers the disk, and return the
 * smallest ring index among them.
 *
 * One query, not 39. Expanding rings with a query per ring would be the direct
 * translation of the reports' loop and would put up to 38 network round trips
 * inside a single click; instead the whole 5 km neighbourhood arrives in one
 * request and the minimum is taken here.
 */
async function ringSearch(ringOf, file, extraWhere = "") {
  const parents = parentList(ringOf.keys(), PARENT_FINE);
  const hits = await rows(`
    SELECT lower(to_hex(h3)) AS cell
    FROM read_parquet('${url(file)}')
    WHERE lower(to_hex(p)) IN (${parents.join(",")}) ${extraWhere}
  `);
  let best = null;
  for (const row of hits) {
    const k = ringOf.get(row.cell);
    if (k != null && (best == null || k < best)) best = k;
  }
  return best;
}

// ---------------------------------------------------------------------------
// The measures
// ---------------------------------------------------------------------------

/** reports/05: distance to the nearest mapped road, and to a non-track road. */
export async function roadDistance(lat, lon) {
  const ringOf = diskWithRings(latLngToCell(lat, lon, RES_FINE), MAX_K);
  const [anyK, nonTrackK] = await Promise.all([
    ringSearch(ringOf, "road_r10.parquet"),
    ringSearch(ringOf, "road_r10.parquet", "AND non_track"),
  ]);
  return {
    k_any: anyK,
    k_non_track: nonTrackK,
    km_any: anyK == null ? null : anyK * KM_PER_RING,
    km_non_track: nonTrackK == null ? null : nonTrackK * KM_PER_RING,
    band: bandFor(nonTrackK),
  };
}

/** reports/17: distance to the nearest mapped building. */
export async function buildingDistance(lat, lon) {
  const ringOf = diskWithRings(latLngToCell(lat, lon, RES_FINE), MAX_K);
  const k = await ringSearch(ringOf, "building_r10.parquet");
  return { k, km: k == null ? null : k * KM_PER_RING, band: bandFor(k) };
}

/**
 * reports/03: population inside the 0,2 / 1,4 / 5,1 km catchments.
 *
 * Kontur's grid is natively H3 r8, which is why this is a hash join and not a
 * raster sample. A cell with no row is genuinely empty rather than unknown, so
 * it contributes zero and not a null.
 */
export async function population(lat, lon) {
  const maxK = Math.max(...POP_RINGS.map((r) => r.k));
  const ringOf = diskWithRings(latLngToCell(lat, lon, RES_POP), maxK);
  const parents = parentList(ringOf.keys(), PARENT_POP);

  const hits = await rows(`
    SELECT lower(to_hex(h3)) AS cell, population
    FROM read_parquet('${url("pop_r8.parquet")}')
    WHERE lower(to_hex(p)) IN (${parents.join(",")})
  `);

  const out = {};
  for (const ring of POP_RINGS) out[ring.key] = 0;
  for (const row of hits) {
    const k = ringOf.get(row.cell);
    if (k == null) continue;
    for (const ring of POP_RINGS) {
      if (k <= ring.k) out[ring.key] += row.population ?? 0;
    }
  }
  for (const key in out) out[key] = Math.round(out[key]);
  return out;
}

// ---------------------------------------------------------------------------
// Point sets
// ---------------------------------------------------------------------------

let minimarketsPromise = null;

/**
 * Tier-1 convenience/minimarket POIs, loaded whole and kept.
 *
 * 7.617 points is 0,11 MB — smaller than one basemap tile — so a linear scan
 * per query beats any index, and shipping the coordinates means the exact
 * distance is available rather than a ring band.
 */
function loadMinimarkets() {
  minimarketsPromise ??= rows(
    `SELECT lon, lat, brand FROM read_parquet('${url("minimarket.parquet")}')`,
  );
  return minimarketsPromise;
}

/** Nearest point in `pts` to (lat, lon), by great-circle distance in metres. */
function nearestPoint(lat, lon, pts, skip) {
  let best = null;
  for (const p of pts) {
    if (skip && skip(p)) continue;
    const m = greatCircleDistance([lat, lon], [p.lat, p.lon], "m");
    if (best === null || m < best.m) best = { m, point: p };
  }
  return best;
}

/** reports/06: exact distance to the nearest tier-1 minimarket. */
export async function minimarketDistance(lat, lon) {
  const pts = await loadMinimarkets();
  const hit = nearestPoint(lat, lon, pts);
  return hit ? { m: hit.m, brand: hit.point.brand } : { m: null, brand: null };
}

/**
 * reports/10: exact distance to the nearest other cooperative.
 *
 * `excludeId` matters: when the point being tested is a correction to
 * cooperative X's own coordinate, X is not its own neighbour.
 */
export function nearestCooperative(lat, lon, points, excludeId) {
  const hit = nearestPoint(
    lat,
    lon,
    points,
    (p) => p.cooperative_id === excludeId,
  );
  return hit
    ? { m: hit.m, cooperative: hit.point.cooperative, village: hit.point.village }
    : { m: null, cooperative: null, village: null };
}

// ---------------------------------------------------------------------------
// The whole analysis at one point
// ---------------------------------------------------------------------------

/**
 * Every measure at one coordinate.
 *
 * Runs the independent lookups concurrently — they hit different files and
 * DuckDB is happy to have several range requests in flight, so the wall time is
 * roughly the slowest one rather than the sum.
 */
export async function analysePoint(lat, lon, { points, excludeId } = {}) {
  const [pop, road, building, minimarket] = await Promise.all([
    population(lat, lon),
    roadDistance(lat, lon),
    buildingDistance(lat, lon),
    minimarketDistance(lat, lon),
  ]);
  return {
    lat,
    lon,
    population: pop,
    road,
    building,
    minimarket,
    nearest: points ? nearestCooperative(lat, lon, points, excludeId) : null,
  };
}

/** Metres between two coordinates — how far the correction moved the point. */
export function moveDistance(a, b) {
  return greatCircleDistance([a.lat, a.lon], [b.lat, b.lon], "m");
}
