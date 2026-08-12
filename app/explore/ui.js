/**
 * ui.js — the explorer's chrome: rail, ladder, legend, tooltip, inspector.
 *
 * Renders from the registries in `measures.js` rather than from markup, so
 * adding a measure adds a control, a legend row and an inspector line at once.
 * Nothing here touches the map; the controller in `index.js` owns that and
 * passes handlers in.
 */

import { id as fmtId, rp } from "../site.js";
import {
  FAMILIES,
  FILTERS,
  LEVELS,
  MEASURES,
  MEASURE_BY_ID,
  PROFILE,
} from "./measures.js";
import { measureRampCss } from "./glyph.js";
import { icon } from "./icons.js";

export const MODES = [
  { id: "profile", label: "Profil", icon: "bars", hint: "Empat batang: sepi · jalan · dempet · senyap" },
  { id: "composition", label: "Komposisi", icon: "pie", hint: "Satu kolom bertumpuk per kelas" },
  { id: "measure", label: "Ukuran", icon: "halfCircle", hint: "Warna sesuai satu persentase" },
];

const pctText = (v) => (v == null ? "—" : `${v.toLocaleString("id-ID", { maximumFractionDigits: 1 })}%`);

export function escapeHtml(s) {
  return String(s ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
}

// ---------------------------------------------------------------------------
// Controls that live over the map canvas
// ---------------------------------------------------------------------------
//
// These change *how you look at the data*, not what the data says. The rail is
// for scale, encoding, measures and filters; search and the basemap belong to
// the view, and putting them here keeps the rail from growing a fifth section
// nobody can reach without scrolling.

const KIND_LABEL = {
  koperasi: "Koperasi",
  kecamatan: "Kecamatan",
  kabupaten: "Kabupaten / kota",
  provinsi: "Provinsi",
};

/**
 * Typeahead over cooperative and area names.
 *
 * `onQuery` returns results synchronously — the index is in memory — so there is
 * no loading state and no race to manage. Keyboard handling is the part worth
 * getting right: arrows move, Enter picks, Escape closes without clearing, so
 * the field stays usable without the mouse.
 */
export function renderSearch(root, { onQuery, onPick }) {
  root.innerHTML = `
    <div class="search-field">
      ${icon("target", 15)}
      <input id="search-input" type="search" autocomplete="off" spellcheck="false"
             placeholder="Cari koperasi atau wilayah…"
             aria-label="Cari koperasi atau wilayah"
             role="combobox" aria-expanded="false" aria-controls="search-results" />
      <button class="search-clear" type="button" hidden aria-label="Kosongkan">${icon("close", 13)}</button>
    </div>
    <ul class="search-results" id="search-results" role="listbox" hidden></ul>`;

  const input = root.querySelector("#search-input");
  const list = root.querySelector("#search-results");
  const clear = root.querySelector(".search-clear");
  let results = [];
  let active = -1;

  function close() {
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
    active = -1;
  }

  function paint() {
    if (!results.length) {
      list.innerHTML = `<li class="search-empty">Tidak ada yang cocok.</li>`;
      list.hidden = false;
      input.setAttribute("aria-expanded", "true");
      return;
    }
    list.innerHTML = results
      .map(
        (r, i) => `
        <li role="option" data-i="${i}" aria-selected="${i === active}"
            class="${i === active ? "is-active" : ""}">
          <span class="res-kind res-${r.kind}">${escapeHtml(KIND_LABEL[r.kind])}</span>
          <span class="res-name">${escapeHtml(r.name)}</span>
          <span class="res-parent">${escapeHtml(
            r.kind === "koperasi" ? r.parent : `${fmtId(r.count)} koperasi · ${r.parent}`,
          )}</span>
        </li>`,
      )
      .join("");
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
  }

  function run() {
    clear.hidden = !input.value;
    results = onQuery(input.value);
    active = results.length ? 0 : -1;
    if (!input.value.trim()) return close();
    paint();
  }

  // The index scan is a few milliseconds, but a keystroke-per-scan on a 83.000
  // entry list is still work worth coalescing while someone is mid-word.
  let timer = null;
  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(run, 110);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (list.hidden || !results.length) return;
      e.preventDefault();
      active = (active + (e.key === "ArrowDown" ? 1 : -1) + results.length) % results.length;
      paint();
      list.querySelector(".is-active")?.scrollIntoView({ block: "nearest" });
    } else if (e.key === "Enter") {
      if (active >= 0 && results[active]) {
        e.preventDefault();
        onPick(results[active]);
        close();
        input.blur();
      }
    } else if (e.key === "Escape") {
      close();
      input.blur();
    }
  });

  list.addEventListener("mousedown", (e) => {
    // mousedown, not click: the input's blur would tear the list down first.
    const li = e.target.closest("li[data-i]");
    if (!li) return;
    e.preventDefault();
    onPick(results[Number(li.dataset.i)]);
    close();
    input.blur();
  });

  clear.addEventListener("click", () => {
    input.value = "";
    clear.hidden = true;
    close();
    input.focus();
  });

  input.addEventListener("focus", () => {
    if (input.value.trim() && results.length) paint();
  });
  document.addEventListener("click", (e) => {
    if (!root.contains(e.target)) close();
  });

  return { focus: () => input.focus() };
}

/** Basemap switcher: a compact pill over the canvas, one button per backdrop. */
export function renderBasemaps(root, basemaps, current, onPick) {
  root.innerHTML = `
    <div class="basemap-pill" role="radiogroup" aria-label="Peta dasar">
      ${basemaps
        .map(
          (b) => `
        <button class="basemap-opt${b.id === current ? " is-active" : ""}" type="button"
                role="radio" aria-checked="${b.id === current}"
                data-basemap="${b.id}" title="${escapeHtml(b.hint)}">
          ${escapeHtml(b.label)}
        </button>`,
        )
        .join("")}
    </div>`;
  root.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-basemap]");
    if (btn) onPick(btn.dataset.basemap);
  });
}

export function updateBasemaps(root, current) {
  for (const btn of root.querySelectorAll("[data-basemap]")) {
    const on = btn.dataset.basemap === current;
    btn.classList.toggle("is-active", on);
    btn.setAttribute("aria-checked", String(on));
  }
}

// ---------------------------------------------------------------------------
// Rail
// ---------------------------------------------------------------------------

/**
 * Build the control rail once and return the handles the controller updates.
 * `on` carries one callback per control; the controller decides what each does.
 */
export function renderRail(root, on) {
  root.innerHTML = `
    <header class="rail-head">
      <p class="rail-kicker">Peta interaktif</p>
      <p class="rail-count"><b id="rail-n">—</b><span>koperasi<br />sedang dipetakan</span></p>
    </header>

    <section class="rail-sec">
      <h2 class="rail-h">${icon("stack", 13)} Skala</h2>
      <div class="ladder" id="ladder" role="radiogroup" aria-label="Skala agregasi">
        ${LEVELS.map(
          (l) => `
          <button class="rung" type="button" role="radio" aria-checked="false"
                  data-level="${l.id}" title="${escapeHtml(l.note)}">
            <span class="rung-dot"></span>
            <span class="rung-label">${escapeHtml(l.label)}</span>
            <span class="rung-n" data-count-for="${l.id}">—</span>
          </button>`,
        ).join("")}
      </div>
      <div class="field" id="size-field">
        <label for="size-range"><span id="size-label">Ukuran sel</span>
          <span class="field-val" id="size-val"></span></label>
        <input type="range" id="size-range" min="24" max="120" step="4" value="52" />
      </div>
    </section>

    <section class="rail-sec">
      <h2 class="rail-h">${icon("bars", 13)} Yang digambar</h2>
      <div class="segmented" id="modes" role="radiogroup" aria-label="Bentuk gliph">
        ${MODES.map(
          (m) => `
          <button class="seg" type="button" role="radio" aria-checked="false"
                  data-mode="${m.id}" title="${escapeHtml(m.hint)}">
            ${icon(m.icon, 14)}<span>${escapeHtml(m.label)}</span>
          </button>`,
        ).join("")}
      </div>
      <div id="mode-detail" class="mode-detail"></div>
    </section>

    <section class="rail-sec">
      <h2 class="rail-h">${icon("polygon", 13)} Lapisan tambahan</h2>
      <label class="switch">
        <input type="checkbox" id="toggle-points" />
        <span>${icon("pin", 14)} Titik koperasi</span>
      </label>
      <label class="switch">
        <input type="checkbox" id="toggle-boundaries" checked />
        <span>${icon("polygon", 14)} Batas wilayah</span>
      </label>
      <p class="switch-note" id="boundary-note"></p>
    </section>

    <details class="rail-sec rail-filters" id="filters">
      <summary>
        ${icon("funnel", 13)} <span>Filter</span>
        <span class="badge" id="filter-badge" hidden></span>
        ${icon("caret", 12)}
      </summary>
      <div class="filter-body">
        ${FILTERS.map(
          (f) => `
          <label class="field">
            <span>${escapeHtml(f.label)}</span>
            <select id="f-${f.id}">
              ${f.options
                .map((o) => `<option value="${o.value}">${escapeHtml(o.label)}</option>`)
                .join("")}
            </select>
          </label>`,
        ).join("")}
        <button class="linkish" type="button" id="filter-reset">
          ${icon("reset", 12)} Kembalikan ke awal
        </button>
        <p class="switch-note" id="filter-scope-note"></p>
      </div>
    </details>

    <section class="rail-legend" id="legend"></section>

    <footer class="rail-foot" id="rail-foot"></footer>`;

  const el = (sel) => root.querySelector(sel);

  el("#ladder").addEventListener("click", (e) => {
    const rung = e.target.closest(".rung");
    if (rung) on.level(rung.dataset.level);
  });

  el("#modes").addEventListener("click", (e) => {
    const seg = e.target.closest(".seg");
    if (seg) on.mode(seg.dataset.mode);
  });

  const size = el("#size-range");
  size.addEventListener("input", () => {
    el("#size-val").textContent = `${size.value} px`;
    on.size(Number(size.value));
  });

  el("#toggle-points").addEventListener("change", (e) => on.points(e.target.checked));
  el("#toggle-boundaries").addEventListener("change", (e) => on.boundaries(e.target.checked));

  for (const f of FILTERS) {
    el(`#f-${f.id}`).addEventListener("change", () => on.filters(readFilters(root)));
  }
  el("#filter-reset").addEventListener("click", () => {
    for (const f of FILTERS) el(`#f-${f.id}`).value = f.options[0].value;
    on.filters(readFilters(root));
  });

  return { root, el };
}

export function readFilters(root) {
  const out = {};
  for (const f of FILTERS) out[f.id] = root.querySelector(`#f-${f.id}`).value;
  return out;
}

/** Highlight the active rung and print each scale's cardinality. */
export function updateLadder(root, activeLevel, counts) {
  for (const rung of root.querySelectorAll(".rung")) {
    const active = rung.dataset.level === activeLevel;
    rung.classList.toggle("is-active", active);
    rung.setAttribute("aria-checked", String(active));
  }
  for (const [level, n] of Object.entries(counts)) {
    const slot = root.querySelector(`[data-count-for="${level}"]`);
    if (slot) slot.textContent = fmtId(n);
  }
}

export function updateModes(root, mode) {
  for (const seg of root.querySelectorAll(".seg")) {
    const active = seg.dataset.mode === mode;
    seg.classList.toggle("is-active", active);
    seg.setAttribute("aria-checked", String(active));
  }
}

/** The secondary control that only some glyph modes need. */
export function renderModeDetail(root, state, on) {
  const slot = root.querySelector("#mode-detail");
  if (state.mode === "profile") {
    slot.innerHTML = `<p class="switch-note">Empat batang tetap, satu per pertanyaan
      laporan. Makin tinggi, makin bermasalah — dan semua gliph berukuran sama,
      jadi tingginya bisa langsung dibandingkan.</p>`;
    return;
  }
  if (state.mode === "composition") {
    slot.innerHTML = `
      <label class="field">
        <span>Kelas</span>
        <select id="family-select">
          ${FAMILIES.map(
            (f) =>
              `<option value="${f.id}"${f.id === state.family ? " selected" : ""}>${escapeHtml(f.label)}</option>`,
          ).join("")}
        </select>
      </label>`;
    slot.querySelector("#family-select").addEventListener("change", (e) => on.family(e.target.value));
    return;
  }
  slot.innerHTML = `
    <label class="field">
      <span>Ukuran</span>
      <select id="measure-select">
        ${MEASURES.map(
          (m) =>
            `<option value="${m.id}"${m.id === state.measure ? " selected" : ""}>${escapeHtml(m.label)}</option>`,
        ).join("")}
      </select>
    </label>
    <p class="switch-note">${escapeHtml(MEASURE_BY_ID[state.measure]?.detail ?? "")}</p>
    <label class="switch">
      <input type="checkbox" id="stretch-scale"${state.stretch ? " checked" : ""} />
      <span>Regangkan skala ke rentang data</span>
    </label>
    ${
      MEASURE_BY_ID[state.measure]?.denominatorNote
        ? `<p class="switch-note">${escapeHtml(MEASURE_BY_ID[state.measure].denominatorNote)}</p>`
        : ""
    }`;
  slot.querySelector("#measure-select").addEventListener("change", (e) => on.measure(e.target.value));
  slot.querySelector("#stretch-scale").addEventListener("change", (e) => on.stretch(e.target.checked));
}

// ---------------------------------------------------------------------------
// Legend
// ---------------------------------------------------------------------------

/**
 * The legend always shows the national figure next to the encoding, because
 * every number on this map is a share and a share only means something against
 * a baseline. Without it "31%" is a colour; with it, it is above or below the
 * country.
 */
export function renderLegend(root, state, stats, national) {
  const slot = root.querySelector("#legend");
  const scope =
    state.level === "grid"
      ? `${fmtId(stats?.cells ?? 0)} sel terisi`
      : `${fmtId(stats?.cells ?? 0)} wilayah`;

  let body = "";
  if (state.mode === "profile") {
    body = `
      <table class="legend-keys">
        ${PROFILE.map((mid) => {
          const m = MEASURE_BY_ID[mid];
          const nat = national?.values?.[mid];
          return `
            <tr>
              <td><span class="key-swatch" style="background:${m.color}"></span></td>
              <td class="key-label">${escapeHtml(m.short)}</td>
              <td class="key-bar"><span style="width:${Math.min(nat ?? 0, 100)}%;background:${m.color}"></span></td>
              <td class="key-num">${pctText(nat)}</td>
            </tr>`;
        }).join("")}
      </table>
      <p class="legend-note">Angka di kanan = rata-rata nasional. Batang gliph
        yang lebih tinggi berarti di atas angka itu.</p>`;
  } else if (state.mode === "composition") {
    const fam = FAMILIES.find((f) => f.id === state.family);
    const parts = national?.shares?.[fam.id];
    body = `
      <div class="legend-stack">
        ${fam.classes
          .map(
            (c, i) =>
              `<span style="background:${c.color};flex:${Math.max(parts?.[i] ?? 1, 0.6)}"
                     title="${escapeHtml(c.label)} — ${pctText(parts?.[i])}"></span>`,
          )
          .join("")}
      </div>
      <table class="legend-keys">
        ${fam.classes
          .map(
            (c, i) => `
            <tr>
              <td><span class="key-swatch" style="background:${c.color}"></span></td>
              <td class="key-label">${escapeHtml(c.label)}</td>
              <td class="key-num">${pctText(parts?.[i])}</td>
            </tr>`,
          )
          .join("")}
      </table>
      <p class="legend-note">Proporsi nasional. Kolom pada peta menunjukkan
        proporsi wilayahnya sendiri.</p>`;
  } else {
    const m = MEASURE_BY_ID[state.measure];
    const nat = national?.values?.[state.measure];
    const [lo, hi] = stats?.domain ?? [0, 100];
    const stretched = lo > 0 || hi < 100;
    // Where the national figure falls on the ramp as drawn, not on 0–100.
    const markAt = nat == null || hi <= lo ? null : ((nat - lo) / (hi - lo)) * 100;
    body = `
      <p class="legend-measure">${escapeHtml(m.label)}</p>
      <div class="legend-ramp" style="background:${measureRampCss()}">
        ${
          markAt == null || markAt < 0 || markAt > 100
            ? ""
            : `<span class="ramp-mark" style="left:${markAt}%"></span>`
        }
      </div>
      <div class="legend-scale"><span>${pctText(lo)}</span><span>${pctText(hi)}</span></div>
      <p class="legend-note">${
        stretched
          ? `Skala diregangkan ke rentang yang benar-benar muncul di skala ini.
             Bandingkan hanya di dalam satu tampilan — ujung skala berpindah
             saat skala atau ukuran diganti.`
          : `Skala tetap 0–100%, jadi warna tidak berubah arti saat peta digeser.`
      }${nat == null ? "" : ` Garis = angka nasional (${pctText(nat)}).`}</p>`;
  }

  // Size means different things in different modes, and saying so is not
  // optional: a legend that claims "bigger = more" while profile mode draws
  // every glyph the same size is worse than no legend at all.
  const sizeNote =
    state.mode === "profile"
      ? `Semua gliph berukuran sama, supaya tinggi batang bisa dibandingkan
         langsung antar wilayah. Jumlah koperasi ada di rincian (klik gliph);
         terbanyak di sini ${fmtId(stats?.max ?? 0)}.`
      : `Gliph makin besar makin banyak koperasi (terbanyak:
         ${fmtId(stats?.max ?? 0)}).`;

  slot.innerHTML = `
    <h2 class="rail-h">${icon("info", 13)} Legenda</h2>
    ${body}
    <p class="legend-scope">${scope} · ${sizeNote}</p>
    ${
      state.tooDense
        ? `<p class="legend-warn">${icon("warning", 12)} Pada zoom ini gliph
             ${escapeHtml(state.levelLabel.toLowerCase())} saling menumpuk.
             Perbesar peta untuk membacanya satu per satu.</p>`
        : ""
    }`;
}

export function updateCount(root, n) {
  root.querySelector("#rail-n").textContent = fmtId(n);
}

export function updateFilterBadge(root, activeCount, enabled) {
  const badge = root.querySelector("#filter-badge");
  badge.hidden = activeCount === 0;
  badge.textContent = String(activeCount);
  const note = root.querySelector("#filter-scope-note");
  note.textContent = enabled
    ? ""
    : "Filter hanya berlaku pada kisi dinamis dan lapisan titik. Angka agregat kecamatan ke atas sudah dihitung atas seluruh koperasi di wilayahnya.";
  root.querySelector("#filters").classList.toggle("is-muted", !enabled);
}

export function setBoundaryNote(root, text) {
  root.querySelector("#boundary-note").textContent = text;
}

/**
 * Point the one size slider at the current scale.
 *
 * The control is the same control at every scale; only what it sizes changes —
 * the aggregation cell on the grid, the glyph itself on an administrative
 * scale, where there is no cell to speak of. Hiding it above the grid, as it
 * was, left no way to make 7.235 kecamatan glyphs fit.
 */
export function setSizeControl(root, sizing, value) {
  const input = root.querySelector("#size-range");
  input.min = String(sizing.min);
  input.max = String(sizing.max);
  input.step = String(sizing.step);
  input.value = String(value);
  root.querySelector("#size-label").textContent = sizing.label;
  root.querySelector("#size-val").textContent = `${value} px`;
}

export function renderFoot(root, manifest) {
  root.querySelector("#rail-foot").innerHTML = `
    <p>Ekspor SIMKOPDES ${escapeHtml(manifest?.source_snapshot?.match(/\d{4}-\d{2}-\d{2}/)?.[0] ?? "")} ·
      ${fmtId(manifest?.coverage?.cooperatives)} koperasi.</p>
    <p>Nol transaksi berarti <em>belum melapor</em>, bukan tidak aktif —
      <a href="../methods/01-snapshot-drift/">metode 01</a>. Jarak dari OSM adalah
      batas atas — <a href="../methods/05-road-access/">metode 05</a>.</p>`;
}

// ---------------------------------------------------------------------------
// Tooltip
// ---------------------------------------------------------------------------

export function showTip(el, payload, event, state) {
  if (!payload || !event) return hideTip(el);
  const title =
    payload.kind === "admin"
      ? escapeHtml(payload.props.name)
      : `${fmtId(payload.count)} koperasi`;
  const sub =
    payload.kind === "admin" ? `${fmtId(payload.count)} koperasi` : "sel kisi";

  el.innerHTML = `<b>${title}</b><span>${sub}</span><em>Klik untuk rincian</em>`;
  el.style.display = "block";
  // Flip before the pointer once the card would run off the right or bottom
  // edge, so the thing you are inspecting never sits under its own tooltip.
  const w = el.offsetWidth;
  const h = el.offsetHeight;
  const x = event.point.x;
  const y = event.point.y;
  const flipX = x + w + 28 > el.parentElement.clientWidth;
  const flipY = y + h + 28 > el.parentElement.clientHeight;
  el.style.left = `${flipX ? x - w - 14 : x + 14}px`;
  el.style.top = `${flipY ? y - h - 14 : y + 14}px`;
}

export function hideTip(el) {
  el.style.display = "none";
}

// ---------------------------------------------------------------------------
// Inspector
// ---------------------------------------------------------------------------

/** Median of a numeric column, nulls dropped. Only ever called on click. */
function median(rows, key) {
  const vals = [];
  for (const r of rows) if (r[key] != null) vals.push(r[key]);
  if (!vals.length) return null;
  vals.sort((a, b) => a - b);
  const mid = vals.length >> 1;
  return vals.length % 2 ? vals[mid] : (vals[mid - 1] + vals[mid]) / 2;
}

/**
 * Distance to the nearest made road, in the unit that makes it readable.
 *
 * A plain "0 km" here is not a missing value and not a rounding artifact: it is
 * report 05's ring search reporting that the cooperative sits in the same cell
 * as a road. Printing the band it came from says that, where the number alone
 * looks like a bug.
 */
function roadDistance(km) {
  if (km == null) return "—";
  if (km === 0) return "di petak jalan (< 70 m)";
  if (km < 1) return `${fmtId(km * 1000)} m`;
  return `${fmtId(km, 2)} km`;
}

function barRow(label, value, color, note = "") {
  return `
    <tr>
      <td class="ins-label">${escapeHtml(label)}</td>
      <td class="ins-bar"><span style="width:${Math.min(value ?? 0, 100)}%;background:${color}"></span></td>
      <td class="ins-num">${pctText(value)}</td>
    </tr>
    ${note ? `<tr class="ins-note-row"><td colspan="3">${escapeHtml(note)}</td></tr>` : ""}`;
}

/**
 * The click card. Everything a glyph compresses into forty pixels, written out:
 * the four profile shares against the national figure, the medians the glyph
 * deliberately does not encode, and the economics.
 */
export function renderInspector(el, payload, state, national, onClose, onDrill) {
  if (!payload) return hideInspector(el);

  const isAdmin = payload.kind === "admin";
  const p = payload.props;
  const rows = payload.rows;

  const title = isAdmin ? p.name : `${fmtId(payload.count)} koperasi`;
  const subtitle = isAdmin
    ? [p.district, p.province].filter((v) => v && v !== p.name).join(" · ")
    : "Sel kisi pada tampilan saat ini";

  // Profile shares: read from the aggregate row at admin level, counted from
  // members at grid level — the same two paths the glyph uses.
  const shares = {};
  for (const mid of PROFILE) {
    const m = MEASURE_BY_ID[mid];
    if (isAdmin) shares[mid] = m.agg(p);
    else {
      let hits = 0;
      let known = 0;
      for (const r of rows) {
        if (!m.known(r)) continue;
        known++;
        if (m.test(r)) hits++;
      }
      shares[mid] = known ? (100 * hits) / known : null;
    }
  }

  const medians = isAdmin
    ? {
        pop: p.median_pop_within_1_4km,
        road: p.median_km_to_road,
        nn: p.median_m_to_nearest_other,
      }
    : {
        pop: median(rows, "pop_within_1_4km"),
        road: median(rows, "km_non_track"),
        nn: median(rows, "m_to_nearest_other"),
      };

  const econ = isAdmin
    ? `
      <h3>Ekonomi</h3>
      <dl class="ins-dl">
        <dt>Desa melapor</dt>
        <dd>${fmtId(p.villages_reporting)} dari ${fmtId(p.villages)}</dd>
        <dt>Nilai transaksi</dt>
        <dd>Rp ${rp(p.transaction_value)}</dd>
      </dl>`
    : `
      <h3>Ekonomi</h3>
      <dl class="ins-dl">
        <dt>Nilai transaksi</dt>
        <dd>Rp ${rp(rows.reduce((a, r) => a + (r.transaction_value ?? 0), 0))}</dd>
      </dl>
      <p class="ins-caveat">${icon("warning", 12)} Jumlah ini hanya mencakup koperasi
        yang tertaut ke data desa. Untuk total wilayah, baca angka pada tingkat
        kecamatan ke atas.</p>`;

  // Grid cells hold named cooperatives; admin rows do not, so the list only
  // appears where there is something to list.
  const sample =
    !isAdmin && rows.length
      ? `
      <h3>Koperasi di sel ini</h3>
      <ul class="ins-list">
        ${rows
          .slice(0, 6)
          .map(
            (r) => `<li>
              <a href="${escapeHtml(r.imagery_url)}" target="_blank" rel="noopener">${escapeHtml(r.cooperative)}</a>
              <span>${escapeHtml([r.subdistrict, r.district].filter(Boolean).join(", "))}</span>
            </li>`,
          )
          .join("")}
      </ul>
      ${rows.length > 6 ? `<p class="ins-caveat">…dan ${fmtId(rows.length - 6)} lainnya.</p>` : ""}
      <p class="ins-caveat">Nama koperasi belum diverifikasi satu per satu —
        lihat <a href="../about/">kebijakan verifikasi</a>.</p>`
      : "";

  el.innerHTML = `
    <button class="ins-close" type="button" aria-label="Tutup">${icon("close", 14)}</button>
    <p class="ins-kicker">${escapeHtml(state.levelLabel)}</p>
    <h2 class="ins-title">${escapeHtml(title)}</h2>
    ${subtitle ? `<p class="ins-sub">${escapeHtml(subtitle)}</p>` : ""}
    <p class="ins-count"><b>${fmtId(payload.count)}</b> koperasi</p>
    ${
      onDrill
        ? `<button class="ins-drill" type="button">${icon("target", 13)} Turun satu tingkat di sini</button>`
        : ""
    }

    <h3>Profil</h3>
    <table class="ins-table">
      ${PROFILE.map((mid) => {
        const m = MEASURE_BY_ID[mid];
        const nat = national?.values?.[mid];
        const delta =
          shares[mid] == null || nat == null
            ? ""
            : `nasional ${pctText(nat)}`;
        return barRow(m.label, shares[mid], m.color, delta);
      }).join("")}
    </table>

    <h3>Nilai tengah</h3>
    <dl class="ins-dl">
      <dt>Penduduk dalam 1,4 km</dt><dd>${fmtId(medians.pop)}</dd>
      <dt>Jarak ke jalan</dt><dd>${roadDistance(medians.road)}</dd>
      <dt>Koperasi terdekat</dt><dd>${medians.nn == null ? "—" : `${fmtId(medians.nn)} m`}</dd>
    </dl>

    ${econ}
    ${sample}`;

  el.querySelector(".ins-close").addEventListener("click", onClose);
  el.querySelector(".ins-drill")?.addEventListener("click", onDrill);
  el.hidden = false;
  el.scrollTop = 0;
}

export function hideInspector(el) {
  el.hidden = true;
  el.innerHTML = "";
}
