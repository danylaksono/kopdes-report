/**
 * tabel.js — the directory instrument at /tabel/.
 *
 * Every Koperasi Desa Merah Putih in one browsable table. Loads a lean column
 * set from the same mart the explorer reads (kopdes_points.parquet via
 * duckdb-wasm), then searches, filters, sorts and pages in memory, so the
 * first load is the only network round trip.
 *
 * Rules that keep this instrument honest:
 *
 * - One encoding everywhere. Badge colours and the road filter derive from
 *   FAMILIES in measures.js, so the table agrees with the map about what a
 *   band means. The population sparkline is a nested bar (cell 400 m, 1.4 km,
 *   5.1 km) normalised to the 99th percentile of catchment, the same
 *   high-percentile rule the glyphs use instead of the maximum.
 * - Nulls carry meaning, and the cells say what it is: "> 5 km" for a road or
 *   minimarket never found within the ring, "Tidak terhubung" for a village
 *   with no SIMKOPDES transaction record, "Belum melaporkan" for a linked
 *   village whose reported transaction is zero. Never "tidak aktif".
 */

import { rows } from "./explore/data.js";
import { FAMILIES, VERIFIED_LAND_STATUSES } from "./explore/measures.js";
import { id } from "./site.js";

const PARQUET = new URL("../data/web/kopdes_points.parquet", import.meta.url)
  .href;

// ---------------------------------------------------------------------------
// Columns
// ---------------------------------------------------------------------------

const COLS = [
  { key: "cooperative", label: "Koperasi", sort: "text" },
  { key: "village", label: "Desa", sort: "text" },
  { key: "subdistrict", label: "Kecamatan", sort: "text" },
  { key: "district", label: "Kabupaten/kota", sort: "text" },
  { key: "province", label: "Provinsi", sort: "text" },
  { key: "transaction_value", label: "Transaksi", sort: "number", num: true },
  { key: "report_status", label: "Laporan", sort: "number" },
  { key: "km_non_track", label: "Jalan", sort: "number", num: true },
  { key: "km_to_minimarket", label: "Minimarket", sort: "number", num: true },
  {
    key: "m_to_nearest_other",
    label: "Koperasi terdekat",
    sort: "number",
    num: true,
  },
  {
    key: "pop_within_1_4km",
    label: "Populasi 1,4 km",
    sort: "number",
    num: true,
  },
  {
    key: "pop_within_5_1km",
    label: "Populasi 5,1 km",
    sort: "number",
    num: true,
  },
  { key: "catchment", label: "Populasi di sekitar", sort: false },
  { key: "maps", label: "Peta", sort: false },
  { key: "land_cover", label: "Penutup Lahan", sort: "text" },
  { key: "land", label: "Status Lahan", sort: "number" },
];
const COLS_BY_KEY = Object.fromEntries(COLS.map((c) => [c.key, c]));

// Class colours come from the same registry the map uses, so a "Jalan" dot and
// a "Koperasi terdekat" dot agree with the glyph ramps.
const CLASS_COLOR = {};
for (const f of FAMILIES)
  for (const c of f.classes) CLASS_COLOR[`${f.id}:${c.key}`] = c.color;
const ROAD = FAMILIES.find((f) => f.id === "road");

// Sparkline palette: three blues, deliberately not any family ramp, for the
// nested catchment bar (own cell darkest, 5.1 km palest).
const SPARK = { w: 96, h: 10, r: 2, colors: ["#2f4b6e", "#5b7fa6", "#b8c8da"] };
let popP99 = 0;

const collator = new Intl.Collator("id");
const esc = (s) =>
  String(s).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const km = (v) =>
  v == null
    ? "> 5 km"
    : `${v.toLocaleString("id-ID", { maximumFractionDigits: 1 })} km`;
const mtr = (v) => (v == null ? "—" : `${id(Math.round(v))} m`);
const people = (v) => (v == null ? "—" : id(Math.round(v)));
const coord = (v) => v.toFixed(4).replace(".", ",");
const mapsUrl = (r) =>
  `https://www.google.com/maps/@${r.latitude},${r.longitude},250m/data=!3m1!1e3`;

// Penutup Lahan: ESA WorldCover 10 m class at the recorded coordinate (reports/19),
// with two OSM overrides that are unambiguous and specific (reports/07). The
// class is a satellite pixel, not the cooperative's footprint, so the tooltip
// says so rather than letting "Hutan" overclaim.
const LAND_COVER = {
  10: { label: "Hutan / pepohonan", color: "#2f7d4f" },
  20: { label: "Semak belukar", color: "#8a9b4f" },
  30: { label: "Padang rumput", color: "#c2a54f" },
  40: { label: "Lahan pertanian", color: "#b58a2e" },
  50: { label: "Pemukiman / terbangun", color: "#8a5a3a" },
  60: { label: "Tanah terbuka", color: "#a89f91" },
  80: { label: "Perairan", color: "#3a6ea8" },
  90: { label: "Rawa", color: "#4d7a72" },
  95: { label: "Mangrove", color: "#2f6d5a" },
};
const LAND_TITLE =
  "ESA WorldCover 10 m (2021) pada koordinat koperasi: klasifikasi citra satelit, bukan jejak bangunan koperasi.";

function landCoverInfo(r) {
  if (r.in_cemetery)
    return {
      label: "Pemakaman",
      color: "#6b4d8a",
      title:
        "Polygon pemakaman OSM (laporan 07); citra satelit tidak punya kelas makam.",
    };
  if (
    r.in_farmland &&
    (r.farmland_depth_m ?? 0) >= 100 &&
    !r.farmland_polygon_coarse
  )
    return {
      label: "Lahan pertanian",
      color: "#b58a2e",
      title:
        "Polygon lahan pertanian OSM, minimal 100 m dari tepi (laporan 07).",
    };
  const base = LAND_COVER[r.land_cover_code];
  return base
    ? { ...base, title: LAND_TITLE }
    : { label: "Tidak terklasifikasi", color: "#9a9a9a", title: LAND_TITLE };
}

// Status aset lahan per koperasi, dari kopdes_land_assets.csv (name join).
// Ini status VERIFIKASI LAHAN, bukan status pembangunan gedung: data
// pembangunan fisik (build_*) hanya ada di tingkat provinsi (reports/15).
// Kelas hijau mengikuti VERIFIED_LAND_STATUSES dari peta, jadi tabel dan peta
// sepakat tentang status yang dianggap tervalidasi.
const LAND_STATUS = {
  Terverifikasi: { label: "Terverifikasi", order: 3 },
  Selesai: { label: "Selesai", order: 3 },
  "Sedang Diverifikasi": {
    label: "Sedang diverifikasi",
    order: 2,
    cls: "badge-warn",
  },
  "Tidak Ada Lahan": {
    label: "Tidak ada lahan",
    order: 1,
    cls: "badge-neutral",
  },
  Dipertimbangkan: { label: "Dipertimbangkan", order: 1, cls: "badge-warn" },
  "Perlu Verifikasi Lanjutan": {
    label: "Perlu verifikasi lanjutan",
    order: 1,
    cls: "badge-warn",
  },
  Ditolak: { label: "Ditolak", order: 1, cls: "badge-danger" },
};
const LAND_VERIFIED = new Set(VERIFIED_LAND_STATUSES);
const LAND_STATUS_TITLE =
  "Status aset lahan dari SIMKOPDES: verifikasi lahan per koperasi, bukan status " +
  "pembangunan gedung. Data pembangunan fisik hanya tersedia di tingkat provinsi (laporan 15).";

function landStatusInfo(r) {
  const s = r.land_status;
  if (s == null || s === "")
    return {
      label: "Tidak ada catatan",
      cls: "badge-neutral",
      order: 0,
      title:
        LAND_STATUS_TITLE +
        " Tidak ada catatan aset lahan yang tertaut untuk koperasi ini.",
    };
  const known = LAND_STATUS[s];
  const cls =
    known && known.cls
      ? known.cls
      : LAND_VERIFIED.has(s)
        ? "badge-ok"
        : "badge-neutral";
  const label = known ? known.label : "Status lain";
  const order = known ? known.order : 1;
  const tail = known
    ? ` Status: ${known.label}.`
    : ` Nilai mentah dari SIMKOPDES: ${s}.`;
  return { label, cls, order, title: LAND_STATUS_TITLE + tail };
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const state = {
  rows: [],
  search: "",
  filters: { province: "", report: "", road: "" },
  sort: { key: "cooperative", dir: 1 },
  page: 0,
  pageSize: 50,
  sorted: [],
};

// ---------------------------------------------------------------------------
// Data
// ---------------------------------------------------------------------------

async function loadRows() {
  return rows(`
    SELECT
      cooperative_id::INTEGER AS cooperative_id,
      cooperative,
      province, district, subdistrict, village,
      latitude, longitude,
      has_village_stats,
      has_reported_transaction,
      transaction_value::DOUBLE AS transaction_value,
      km_non_track, km_to_minimarket, m_to_nearest_other,
      pop_within_1_4km, pop_within_5_1km, own_cell_pop,
      coordinate_suspect, land_verified, land_status,
      in_cemetery, in_farmland, farmland_depth_m, farmland_polygon_coarse,
      land_cover, land_cover_code,
      road_class, nn_class
    FROM read_parquet('${PARQUET}')
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
  `);
}

// ---------------------------------------------------------------------------
// Filtering and sorting
// ---------------------------------------------------------------------------

function matches(r) {
  const q = state.search.trim().toLowerCase();
  if (q) {
    const tokens = q.split(/\s+/);
    const hay =
      `${r.cooperative} ${r.village} ${r.subdistrict} ${r.district} ${r.province} ${r.cooperative_id}`.toLowerCase();
    if (!tokens.every((t) => hay.includes(t))) return false;
  }
  const f = state.filters;
  if (f.province && r.province !== f.province) return false;
  if (f.report) {
    const s = r.has_village_stats
      ? r.has_reported_transaction
        ? "melaporkan"
        : "belum"
      : "tidak";
    if (s !== f.report) return false;
  }
  if (f.road && r.road_class !== f.road) return false;
  return true;
}

function sortValue(col, r) {
  switch (col.key) {
    case "report_status":
      return r.has_village_stats ? (r.has_reported_transaction ? 2 : 1) : 0;
    case "land_cover":
      return landCoverInfo(r).label;
    case "land":
      return landStatusInfo(r).order;
    case "catchment":
      return r.pop_within_5_1km ?? 0;
    default:
      return r[col.key];
  }
}

function compute() {
  const col = COLS_BY_KEY[state.sort.key];
  const dir = state.sort.dir;
  state.sorted = state.rows.filter(matches).sort((a, b) => {
    const av = sortValue(col, a);
    const bv = sortValue(col, b);
    const an = av == null;
    const bn = bv == null;
    if (an || bn) return an === bn ? 0 : an ? 1 : -1;
    const c =
      col.sort === "number"
        ? av - bv
        : collator.compare(String(av), String(bv));
    return c * dir;
  });
}

// ---------------------------------------------------------------------------
// Cell rendering
// ---------------------------------------------------------------------------

function dot(fid, key) {
  const color = CLASS_COLOR[`${fid}:${key}`];
  return color ? `<span class="dot" style="background:${color}"></span>` : "";
}

function reportBadge(r) {
  if (!r.has_village_stats)
    return `<span class="badge badge-neutral" title="Desa tidak tercantum dalam data transaksi SIMKOPDES; nilainya tidak diketahui">Tidak terhubung</span>`;
  if (r.has_reported_transaction)
    return `<span class="badge badge-ok" title="Ada nilai transaksi yang dilaporkan">Melaporkan</span>`;
  return `<span class="badge badge-warn" title="Belum ada nilai transaksi yang dilaporkan">Belum melaporkan</span>`;
}

function sparkline(r) {
  if (popP99 <= 0) return "";
  const w = (v) => Math.max(0, Math.min(1, v / popP99)) * SPARK.w;
  const own = r.own_cell_pop ?? 0;
  const p14 = r.pop_within_1_4km ?? 0;
  const p51 = r.pop_within_5_1km ?? 0;
  const title = `Populasi: sel 400 m ${people(own)}, dalam 1,4 km ${people(p14)}, dalam 5,1 km ${people(p51)}`;
  return `<svg class="spark" width="${SPARK.w}" height="${SPARK.h}" role="img" aria-label="${title}" focusable="false">
    <title>${title}</title>
    <rect x="0" y="0" width="${w(p51)}" height="${SPARK.h}" rx="${SPARK.r}" fill="${SPARK.colors[2]}"></rect>
    <rect x="0" y="0" width="${w(p14)}" height="${SPARK.h}" fill="${SPARK.colors[1]}"></rect>
    <rect x="0" y="0" width="${w(own)}" height="${SPARK.h}" fill="${SPARK.colors[0]}"></rect>
  </svg>`;
}

function cell(col, r) {
  switch (col.key) {
    case "cooperative":
      return `<span class="coop-name">${esc(r.cooperative)}</span><span class="coop-id">#${id(r.cooperative_id)}</span>`;
    case "transaction_value":
      return r.transaction_value == null
        ? "—"
        : `Rp ${id(r.transaction_value)}`;
    case "report_status":
      return reportBadge(r);
    case "km_non_track":
      return dot("road", r.road_class) + km(r.km_non_track);
    case "km_to_minimarket":
      return km(r.km_to_minimarket);
    case "m_to_nearest_other":
      return dot("nn", r.nn_class) + mtr(r.m_to_nearest_other);
    case "pop_within_1_4km":
      return people(r.pop_within_1_4km);
    case "pop_within_5_1km":
      return people(r.pop_within_5_1km);
    case "catchment":
      return sparkline(r);
    case "maps": {
      const c = `${coord(r.latitude)}, ${coord(r.longitude)}`;
      const link = `<a class="map-link" href="${mapsUrl(r)}" target="_blank" rel="noopener" title="Buka lokasi di Google Maps (${c})">Lihat peta ↗</a>`;
      return r.coordinate_suspect
        ? `<span class="badge badge-danger" title="Koordinat ${c} tidak masuk akal dan belum diverifikasi">Perlu dicek</span> ${link}`
        : link;
    }
    case "land_cover": {
      const lu = landCoverInfo(r);
      return `<span class="land-cover" title="${esc(lu.title)}"><span class="dot" style="background:${lu.color}"></span>${lu.label}</span>`;
    }
    case "land": {
      const s = landStatusInfo(r);
      return `<span class="badge ${s.cls}" title="${esc(s.title)}">${s.label}</span>`;
    }
    default:
      return esc(r[col.key] ?? "");
  }
}

// ---------------------------------------------------------------------------
// DOM
// ---------------------------------------------------------------------------

const $ = (sel) => document.querySelector(sel);
const statusEl = $("#status");
const tabelEl = $("#tabel");
const theadEl = $("#thead");
const tbodyEl = $("#tbody");
const countEl = $("#count");
const pageEl = $("#page");
const prevBtn = $("#prev");
const nextBtn = $("#next");
const sizeSel = $("#size");
const searchEl = $("#search");
const provinceSel = $("#f-province");
const reportSel = $("#f-report");
const roadSel = $("#f-road");
const wideBtn = $("#wide");

function renderHeader() {
  theadEl.innerHTML =
    "<tr>" +
    COLS.map((c) => {
      const active = state.sort.key === c.key;
      const dir = active ? (state.sort.dir === 1 ? "asc" : "desc") : "";
      const aria = active ? ` aria-sort="${dir}"` : "";
      const inner = c.sort
        ? `<button class="sort" data-key="${c.key}" type="button"${aria}>${c.label}<span class="caret">${dir === "asc" ? "▲" : dir === "desc" ? "▼" : ""}</span></button>`
        : `<span>${c.label}</span>`;
      return `<th class="${c.num ? "num" : ""}" scope="col">${inner}</th>`;
    }).join("") +
    "</tr>";
}

function renderBody() {
  const total = state.sorted.length;
  const pages = Math.max(1, Math.ceil(total / state.pageSize));
  if (state.page >= pages) state.page = pages - 1;
  const start = state.page * state.pageSize;
  const slice = state.sorted.slice(start, start + state.pageSize);

  tbodyEl.innerHTML = slice
    .map(
      (r) =>
        `<tr>${COLS.map((c) => `<td class="${c.num ? "num" : ""}">${cell(c, r)}</td>`).join("")}</tr>`,
    )
    .join("");

  countEl.textContent = total
    ? `Menampilkan ${id(start + 1)}–${id(Math.min(start + state.pageSize, total))} dari ${id(total)} koperasi`
    : "Tidak ada koperasi yang cocok";

  pageEl.textContent = `Halaman ${id(state.page + 1)} dari ${id(pages)}`;
  prevBtn.disabled = state.page === 0;
  nextBtn.disabled = state.page >= pages - 1;
}

// ---------------------------------------------------------------------------
// Events
// ---------------------------------------------------------------------------

theadEl.addEventListener("click", (ev) => {
  const btn = ev.target.closest("button.sort");
  if (!btn) return;
  const key = btn.dataset.key;
  if (state.sort.key === key) state.sort.dir *= -1;
  else state.sort = { key, dir: 1 };
  state.page = 0;
  compute();
  renderHeader();
  renderBody();
});

let searchTimer;
searchEl.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    state.search = searchEl.value;
    state.page = 0;
    compute();
    renderBody();
  }, 120);
});

provinceSel.addEventListener("change", () => {
  state.filters.province = provinceSel.value;
  state.page = 0;
  compute();
  renderBody();
});
reportSel.addEventListener("change", () => {
  state.filters.report = reportSel.value;
  state.page = 0;
  compute();
  renderBody();
});
roadSel.addEventListener("change", () => {
  state.filters.road = roadSel.value;
  state.page = 0;
  compute();
  renderBody();
});

prevBtn.addEventListener("click", () => {
  if (state.page > 0) {
    state.page--;
    renderBody();
  }
});
nextBtn.addEventListener("click", () => {
  state.page++;
  renderBody();
});
sizeSel.addEventListener("change", () => {
  state.pageSize = Number(sizeSel.value);
  state.page = 0;
  renderBody();
});
wideBtn.addEventListener("click", () => {
  const wide = document.body.classList.toggle("tabel-wide");
  wideBtn.setAttribute("aria-pressed", String(wide));
  wideBtn.textContent = wide ? "Lebar normal" : "Lebar penuh";
});

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

function populateFilters() {
  const provinces = [...new Set(state.rows.map((r) => r.province))].sort(
    collator.compare,
  );
  provinceSel.innerHTML =
    `<option value="">Semua provinsi</option>` +
    provinces
      .map((p) => `<option value="${esc(p)}">${esc(p)}</option>`)
      .join("");
  roadSel.innerHTML =
    `<option value="">Semua jarak jalan</option>` +
    ROAD.classes
      .map((c) => `<option value="${c.key}">${c.label}</option>`)
      .join("");
}

function percentile(values, p) {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const idx = Math.min(
    sorted.length - 1,
    Math.floor((p / 100) * sorted.length),
  );
  return sorted[idx];
}

async function boot() {
  try {
    const data = await loadRows();
    state.rows = data;
    popP99 = percentile(
      data.map((r) => r.pop_within_5_1km ?? 0),
      99,
    );
    populateFilters();
    compute();
    renderHeader();
    renderBody();
    statusEl.hidden = true;
    tabelEl.hidden = false;
  } catch (err) {
    statusEl.textContent =
      "Gagal memuat data. Muat ulang halaman untuk mencoba lagi.";
    console.error(err);
  }
}

boot();
