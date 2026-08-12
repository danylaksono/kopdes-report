/**
 * measures.js — what the explorer can draw, and where each number comes from.
 *
 * This module is the explorer's contract with the analysis mart. Every scale
 * (dynamic grid, kecamatan, kabupaten, provinsi) reads the same measures, and
 * each measure knows two things: how to test a single cooperative, and which
 * pre-aggregated column holds the same figure at admin level.
 *
 * ## Why every measure is a share
 *
 * Medians are the natural summary for most of these columns and the mart has
 * them — `median_km_to_road` and friends. The glyph does not use them, for two
 * reasons that turned out to be the same reason:
 *
 * 1. screengrid re-aggregates on every frame (`ScreenGridLayerGL.render()`
 *    calls `_aggregate()` unconditionally), so a grid cell's summary has to be
 *    computable in one pass with no sorting and no allocation. A median is
 *    neither.
 * 2. If the grid drew a mean and the kecamatan layer drew a median, switching
 *    scale would silently change what the bar means. The whole point of this
 *    map is that the four scales are comparable.
 *
 * A share — "x% of cooperatives here are further than 500 m from a road" — is
 * a single counter at grid level, is exactly what the mart's `pct_*` and
 * `*_share_*` columns already hold at admin level, and is identical in
 * definition at both. It also fixes the legend: shares are 0–100 everywhere,
 * so nothing rescales as you pan and the ramp never lies about what dark means.
 *
 * Medians still matter, so they live in the inspector, which runs once per
 * click and can afford them.
 *
 * ## Denominators
 *
 * Every measure declares `known` alongside `test`. Nulls in this dataset carry
 * meaning and the meanings differ per column (see `mart_manifest.json`), so a
 * cooperative that was never measured is excluded from the denominator rather
 * than counted as passing. `share` returns null when nothing in the cell is
 * measurable, and the glyph draws that as a gap, not a zero.
 */

// ---------------------------------------------------------------------------
// Scales
// ---------------------------------------------------------------------------

/**
 * The four scales, coarsest last. Cardinalities are filled in at load from the
 * manifest — hardcoding 83.342 here would be a second source of truth that goes
 * stale the next time SIMKOPDES is re-scraped.
 *
 * `sizing` drives the one slider in the rail, whose meaning changes with the
 * scale: on the grid it sets the aggregation cell, on an administrative scale
 * there is no cell to set, only the glyph itself. `ratio` is the fraction of
 * the maximum envelope that profile mode's uniform box occupies — profile draws
 * everything at one size, so it has to sit below the size the largest few areas
 * would otherwise take.
 */
export const LEVELS = [
  {
    id: "grid",
    label: "Kisi dinamis",
    note: "Sel layar, dihitung ulang tiap kali peta digeser",
    kind: "grid",
    table: "kopdes_points",
    sizing: { label: "Ukuran sel", min: 24, max: 120, step: 4, default: 52, ratio: 0.92 },
  },
  {
    id: "kecamatan",
    label: "Kecamatan",
    note: "Agregat per kecamatan",
    kind: "admin",
    table: "kopdes_kecamatan",
    key: "subdistrict_id",
    nameCol: "subdistrict",
    parentCols: ["district", "province"],
    boundaries: "kecamatan",
    minzoom: 6,
    sizing: { label: "Ukuran grafik", min: 12, max: 64, step: 2, default: 30, ratio: 0.74 },
  },
  {
    id: "kabupaten",
    label: "Kabupaten / kota",
    note: "Agregat per kabupaten dan kota",
    kind: "admin",
    table: "kopdes_kabupaten",
    key: "district_id",
    nameCol: "district",
    parentCols: ["province"],
    boundaries: "kabupaten",
    sizing: { label: "Ukuran grafik", min: 16, max: 90, step: 2, default: 42, ratio: 0.76 },
    // Profile glyphs are a fixed size, so dense areas no longer thin themselves
    // out the way proportional symbols did. 514 anchors at a legible size
    // overlap across Java below about this zoom — the legend says so rather
    // than the map shrinking the glyphs back under the size where four bars
    // stop reading as four bars.
    minzoom: 5.5,
  },
  {
    id: "provinsi",
    label: "Provinsi",
    note: "Agregat per provinsi",
    kind: "admin",
    table: "kopdes_provinsi",
    key: "province_id",
    nameCol: "province",
    parentCols: [],
    boundaries: "provinsi",
    sizing: { label: "Ukuran grafik", min: 24, max: 140, step: 4, default: 70, ratio: 0.74 },
  },
];

export const LEVEL_BY_ID = Object.fromEntries(LEVELS.map((l) => [l.id, l]));

// ---------------------------------------------------------------------------
// Class families — the categorical collapses built in build_analysis_mart.py
// ---------------------------------------------------------------------------

/**
 * Ordered worst -> best, matching `CLASS_COLUMNS` in the mart builder. The
 * point column holds a 1-based index into `classes` (see `classCodeSql`), which
 * keeps the per-frame counters integer comparisons instead of string equality.
 *
 * Ramps run dark (worst) to pale (best) so a troubled area reads as heavier ink
 * — the same direction as the density ramp the rest of the report uses.
 */
export const FAMILIES = [
  {
    id: "road",
    label: "Jarak ke jalan",
    col: "road_class",
    source: "reports/05 + 08 (OSM)",
    classes: [
      { key: "over_5km", label: "> ±5 km / tidak ada", color: "#7c2d12" },
      { key: "under_5km", label: "±500 m – 5 km", color: "#c2610a" },
      { key: "under_500m", label: "< ±500 m", color: "#e9a23b" },
      { key: "on_road", label: "Di atas jalan (< 70 m)", color: "#f4e0bd" },
    ],
  },
  {
    id: "pop",
    label: "Penduduk di sekitar",
    col: "pop_class",
    source: "reports/03 (Kontur 400 m)",
    classes: [
      { key: "empty", label: "Nihil dalam 5 km", color: "#5b1d1d" },
      { key: "under_500", label: "< 500 orang", color: "#a13a2a" },
      { key: "under_10k", label: "500 – 10.000", color: "#d98b5f" },
      { key: "over_10k", label: "> 10.000", color: "#f2ddcc" },
    ],
  },
  {
    id: "nn",
    label: "Jarak ke koperasi terdekat",
    col: "nn_class",
    // Proximity, not quality: a teal ramp so it does not read as a severity
    // scale like the two above. Report 10 found no measurable penalty from
    // being close, and the colour should not imply one.
    source: "reports/10",
    classes: [
      { key: "under_1km", label: "< 1 km", color: "#1f5f5b" },
      { key: "1_2km", label: "1 – 2 km", color: "#4d9a94" },
      { key: "2_5km", label: "2 – 5 km", color: "#9ec8c4" },
      { key: "over_5km", label: "> 5 km", color: "#dcebe9" },
    ],
  },
];

export const FAMILY_BY_ID = Object.fromEntries(FAMILIES.map((f) => [f.id, f]));

/**
 * SQL that turns a `<family>_class` string into its 1-based position in
 * `classes`, so the browser never carries 83.342 copies of the same few
 * strings. NULL stays NULL — unmeasured is not a class.
 */
export function classCodeSql(family) {
  const list = family.classes.map((c) => `'${c.key}'`).join(", ");
  return `list_position([${list}], ${family.col})::TINYINT as ${family.id}_k`;
}

/** Percent share of `classes[i]` at admin level, e.g. `road_share_on_road`. */
const shareCol = (family, i) =>
  `${family.id}_share_${family.classes[i].key}`;

/** Every aggregate column a family needs, in class order. */
export function familyShareCols(family) {
  return family.classes.map((_, i) => shareCol(family, i));
}

// ---------------------------------------------------------------------------
// Measures — one selectable number, defined identically at all four scales
// ---------------------------------------------------------------------------

const pct = (v) => (v == null ? null : Number(v));

/**
 * `test`/`known` take a point row; `agg` takes an aggregate row. Both return
 * the same quantity: percent of measurable cooperatives meeting the condition.
 *
 * `chapter` ties the measure to the report act it came from, which is what the
 * profile glyph's colours encode.
 */
export const MEASURES = [
  {
    id: "pop_sparse",
    label: "Sekitarnya sepi",
    short: "Sepi",
    detail: "Kurang dari 500 orang dalam radius 5 km",
    chapter: "akses",
    color: "#a13a2a",
    known: (r) => r.pop_k != null,
    test: (r) => r.pop_k <= 2, // empty | under_500
    agg: (p) => sum2(p.pop_share_empty, p.pop_share_under_500),
    cols: { point: ["pop_k"], agg: ["pop_share_empty", "pop_share_under_500"] },
    source: "reports/03",
  },
  {
    id: "road_far",
    label: "Jauh dari jalan",
    short: "Jalan",
    detail: "Lebih dari ±500 m dari jalan beraspal terdekat",
    chapter: "akses",
    color: "#c2610a",
    known: (r) => r.road_k != null,
    test: (r) => r.road_k <= 2, // over_5km | under_5km
    agg: (p) => sum2(p.road_share_over_5km, p.road_share_under_5km),
    cols: {
      point: ["road_k"],
      agg: ["road_share_over_5km", "road_share_under_5km"],
    },
    source: "reports/05 + 08",
  },
  {
    id: "nn_close",
    label: "Berdempetan",
    short: "Dempet",
    detail: "Koperasi lain berjarak kurang dari 1 km",
    chapter: "kompetisi",
    color: "#2f7d7a",
    known: (r) => r.nn_k != null,
    test: (r) => r.nn_k === 1, // under_1km
    agg: (p) => pct(p.nn_share_under_1km),
    cols: { point: ["nn_k"], agg: ["nn_share_under_1km"] },
    source: "reports/10",
  },
  {
    id: "silent",
    label: "Tidak melaporkan transaksi",
    short: "Senyap",
    detail: "Belum pernah mencatat satu pun transaksi",
    chapter: "uang",
    color: "#a00000",
    known: (r) => r.has_reported_transaction != null,
    test: (r) => r.has_reported_transaction === false,
    agg: (p) => (p.pct_reported_transaction == null ? null : 100 - p.pct_reported_transaction),
    cols: { point: ["has_reported_transaction"], agg: ["pct_reported_transaction"] },
    source: "reports/01 + 02",
    // The one measure whose denominator genuinely differs by scale, and the
    // difference is documented in mart_manifest.json: at grid level it counts
    // the 79% of cooperatives whose village link resolved, at admin level it
    // counts every village in the complete export. Summing point economics to
    // get a regional figure is the mistake the mart exists to prevent, so the
    // aggregate column stays authoritative and the UI says which is on screen.
    denominatorNote:
      "Di kisi dinamis, penyebutnya adalah koperasi yang tertaut ke data desa (79%); di tingkat administratif, seluruh desa dalam ekspor.",
  },
  {
    id: "minimarket_near",
    label: "Minimarket dalam 500 m",
    short: "Minimarket",
    detail: "Ada minimarket berjarak 500 m atau kurang",
    chapter: "kompetisi",
    color: "#4d9a94",
    known: (r) => r.m_to_minimarket_exact != null,
    test: (r) => r.m_to_minimarket_exact <= 500,
    agg: (p) => pct(p.pct_minimarket_within_500m),
    cols: { point: ["m_to_minimarket_exact"], agg: ["pct_minimarket_within_500m"] },
    source: "reports/06 + 08",
  },
  {
    id: "land_unverified",
    label: "Lahan belum terverifikasi",
    short: "Lahan",
    detail: "Ada catatan aset lahan, statusnya belum terverifikasi",
    chapter: "uang",
    color: "#8a5a2b",
    known: (r) => r.land_status != null,
    test: (r) => r.land_verified !== true,
    agg: (p) => (p.pct_land_verified == null ? null : 100 - p.pct_land_verified),
    cols: { point: ["land_status", "land_verified"], agg: ["pct_land_verified"] },
    source: "data/raw/kopdes_land_assets.csv",
  },
];

export const MEASURE_BY_ID = Object.fromEntries(MEASURES.map((m) => [m.id, m]));

/**
 * The four bars of the profile glyph, in drawing order: the report's three
 * acts, with access getting two bars because it is the only act the data
 * measures twice (people, then roads).
 *
 * Every bar points the same way — taller is worse — so a tall glyph means an
 * area is troubled on several fronts at once, which is the only reading a
 * four-bar glyph can support at 40 pixels.
 */
export const PROFILE = ["pop_sparse", "road_far", "nn_close", "silent"];

function sum2(a, b) {
  if (a == null && b == null) return null;
  return (a ?? 0) + (b ?? 0);
}

// ---------------------------------------------------------------------------
// Filters — subsets of cooperatives, applied before anything is aggregated
// ---------------------------------------------------------------------------

/**
 * Filters run at grid level only, where individual cooperatives exist. At admin
 * level the mart's shares are already computed over every cooperative in the
 * area and cannot be re-cut in the browser; the UI disables the control and
 * says so rather than silently ignoring it.
 */
export const FILTERS = [
  {
    id: "population",
    label: "Penduduk",
    options: [
      { value: "all", label: "Semua" },
      { value: "sparse", label: "Sekitarnya sepi (<500 orang)", test: (r) => r.pop_k != null && r.pop_k <= 2 },
      { value: "populated", label: "Ada penduduk (≥500)", test: (r) => r.pop_k != null && r.pop_k >= 3 },
    ],
  },
  {
    id: "road",
    label: "Jalan",
    options: [
      { value: "all", label: "Semua" },
      { value: "far", label: "Lebih dari ±500 m", test: (r) => r.road_k != null && r.road_k <= 2 },
      { value: "near", label: "±500 m atau kurang", test: (r) => r.road_k != null && r.road_k >= 3 },
    ],
  },
  {
    id: "transaction",
    label: "Transaksi",
    options: [
      { value: "all", label: "Semua" },
      { value: "reporting", label: "Melaporkan transaksi", test: (r) => r.has_reported_transaction === true },
      { value: "silent", label: "Tidak melaporkan", test: (r) => r.has_reported_transaction === false },
    ],
  },
  {
    id: "land",
    label: "Lahan",
    options: [
      { value: "all", label: "Semua" },
      { value: "verified", label: "Terverifikasi", test: (r) => r.land_verified === true },
      { value: "unverified", label: "Belum terverifikasi", test: (r) => r.land_status != null && r.land_verified !== true },
      { value: "no_record", label: "Tanpa catatan aset", test: (r) => r.land_status == null },
    ],
  },
  {
    id: "coordinate",
    label: "Koordinat",
    options: [
      // Default excludes the 19 impossible coordinates from report 08: they are
      // real rows and belong in the data, but leaving them on by default puts
      // koperasi in the Indian Ocean on the opening view.
      { value: "valid", label: "Hanya yang masuk akal", test: (r) => r.coordinate_suspect !== true },
      { value: "all", label: "Termasuk yang janggal (19)" },
      { value: "suspect", label: "Hanya yang janggal", test: (r) => r.coordinate_suspect === true },
    ],
  },
];

export const FILTER_DEFAULTS = Object.fromEntries(
  FILTERS.map((f) => [f.id, f.options[0].value]),
);
