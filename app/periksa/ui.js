/**
 * ui.js — rendering for /periksa/.
 *
 * The page's output is not "here is the analysis at your point". It is the
 * *difference* between two analyses: the coordinate SIMKOPDES publishes and the
 * coordinate a reader says is correct. That framing is the reason the page
 * exists, so it is the shape of every panel here — two columns and a verdict on
 * the gap between them.
 *
 * Three rules the markup enforces, all inherited from the report's standing
 * caveats:
 *
 * 1. **Neither coordinate is labelled correct.** SIMKOPDES states its own map
 *    positions are representative per area rather than precise; a reader's pin
 *    is unverified in a different way. Both are shown, neither wins.
 * 2. **"Mapped" survives the recomputation.** Moving the pin does not make
 *    OpenStreetMap's rural coverage complete, so every building, road and
 *    minimarket result says *terpetakan* and the lower-bound framing stays.
 * 3. **Nothing is submitted.** The page stores and sends nothing; the only way
 *    a result leaves the browser is the reader copying the link. It says so.
 */

import { id } from "../site.js";
import { KM_PER_RING, MAX_K } from "./analysis.js";

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------

const DASH = "—";

/** A ring distance, always hedged: k x 132 m is a band, never a measurement. */
export function ringKm(k) {
  if (k == null) return `lebih dari ${(MAX_K * KM_PER_RING).toFixed(1)} km`;
  if (k === 0) return "< 70 m";
  const km = k * KM_PER_RING;
  return km < 1
    ? `±${id(Math.round(km * 1000))} m`
    : `±${km.toLocaleString("id-ID", { maximumFractionDigits: 1 })} km`;
}

/** An exact point-to-point distance, which does not need the hedge. */
export function metres(m) {
  if (m == null) return DASH;
  return m < 1000
    ? `${id(Math.round(m))} m`
    : `${(m / 1000).toLocaleString("id-ID", { maximumFractionDigits: 1 })} km`;
}

// ---------------------------------------------------------------------------
// The measure rows
// ---------------------------------------------------------------------------

/**
 * What the two columns compare, in the order the report's three acts run:
 * access first, then competition.
 *
 * `value` renders one side, `raw` is what the two sides are subtracted on, and
 * `diffText` phrases the signed difference. Distances say "lebih dekat" /
 * "lebih jauh" rather than carrying a sign, because a banded distance prints
 * its own ± and "−±264 m" is unreadable. `band` exists only on the measures the
 * report publishes as classes (road and building): it is what tells the page
 * whether a correction merely moved a number or moved the cooperative into a
 * different published category.
 */
const nearer = (d) => (d < 0 ? "lebih dekat" : "lebih jauh");

const MEASURES = [
  {
    id: "pop",
    label: "Penduduk dalam ±1,4 km",
    note: "Kontur 400 m, disusun dari citra satelit",
    value: (r) => id(r.population.within_1_4km),
    raw: (r) => r.population.within_1_4km,
    diffText: (d) => `${d > 0 ? "+" : "−"}${id(Math.abs(d))} orang`,
  },
  {
    id: "road",
    label: "Jalan terpetakan terdekat",
    note: "di luar jalan setapak (track), OpenStreetMap",
    value: (r) => ringKm(r.road.k_non_track),
    raw: (r) => r.road.k_non_track,
    band: (r) => r.road.band,
    // The underlying unit is a ring index, but "2 cincin" means nothing to a
    // reader. Convert to the distance it stands for and keep the ± that says
    // it is a band.
    diffText: (d) => `${nearer(d)} ±${id(Math.abs(d) * 132)} m`,
  },
  {
    id: "building",
    label: "Bangunan terpetakan terdekat",
    note: "gabungan Google, Microsoft dan OpenStreetMap",
    value: (r) => ringKm(r.building.k),
    raw: (r) => r.building.k,
    band: (r) => r.building.band,
    diffText: (d) => `${nearer(d)} ±${id(Math.abs(d) * 132)} m`,
  },
  {
    id: "minimarket",
    label: "Minimarket terpetakan terdekat",
    note: "hanya gerai setara Indomaret/Alfamart",
    value: (r) => metres(r.minimarket.m),
    raw: (r) => r.minimarket.m,
    diffText: (d) => `${nearer(d)} ${metres(Math.abs(d))}`,
  },
  {
    id: "nearest",
    label: "Koperasi lain terdekat",
    note: "sesama KDMP, di luar koperasi ini sendiri",
    value: (r) => metres(r.nearest?.m),
    raw: (r) => r.nearest?.m,
    diffText: (d) => `${nearer(d)} ${metres(Math.abs(d))}`,
  },
];

/**
 * What changed for one measure, or null when there is nothing to say.
 *
 * A null on either side is not a zero: "no road found within 5 km" against
 * "road at 400 m" is a change in kind, not a subtraction, and is reported as
 * one.
 *
 * `crossed` is the only thing this page emphasises, and it is a fact rather
 * than an opinion: the report classifies cooperatives into bands, so a
 * correction changes a published classification exactly when the band changes.
 * There is deliberately no "better"/"worse" flag. An earlier draft had one, and
 * it quietly asserted that a cooperative further from a minimarket is a better
 * cooperative — an argument the report makes with evidence elsewhere, and one
 * a recomputation of a single unverified point has not earned.
 */
function delta(m, a, b) {
  const x = m.raw(a);
  const y = m.raw(b);
  if (x == null && y == null) return null;
  if (x == null || y == null) {
    const foundNow = x == null && y != null;
    return {
      kind: "appeared",
      crossed: true,
      text: foundNow ? "sebelumnya tidak ditemukan" : "kini tidak ditemukan",
    };
  }
  if (x === y) return { kind: "same", crossed: false, text: "tidak berubah" };
  const diff = y - x;
  return {
    kind: "moved",
    crossed: Boolean(m.band && m.band(a) !== m.band(b)),
    text: m.diffText(diff),
  };
}

// ---------------------------------------------------------------------------
// Panels
// ---------------------------------------------------------------------------

/** The comparison table: SIMKOPDES coordinate against the reported one. */
export function renderComparison(el, { official, reported, moved }) {
  const rowsHtml = MEASURES.map((m) => {
    const d = reported ? delta(m, official, reported) : null;
    // Emphasis marks a band crossing, not a direction. See delta().
    const cls = d?.crossed ? "crossed" : d?.kind === "same" ? "same" : "";
    return `
      <tr>
        <th scope="row">
          ${m.label}
          <span class="measure-note">${m.note}</span>
        </th>
        <td class="num" data-label="SIMKOPDES">${m.value(official)}</td>
        <td class="num" data-label="Ditandai">${reported ? m.value(reported) : DASH}</td>
        <td class="num delta ${cls}" data-label="Selisih">${d ? d.text : DASH}</td>
      </tr>`;
  }).join("");

  el.innerHTML = `
    <table class="data-table periksa-table">
      <thead>
        <tr>
          <th scope="col">Yang diukur</th>
          <th scope="col">Koordinat SIMKOPDES</th>
          <th scope="col">Koordinat yang Anda tandai</th>
          <th scope="col">Selisih</th>
        </tr>
      </thead>
      <tbody>${rowsHtml}</tbody>
    </table>
    ${
      reported
        ? `<p class="periksa-move">Titik yang Anda tandai berjarak
             <strong>${metres(moved)}</strong> dari koordinat resmi.</p>`
        : ""
    }`;
}

/**
 * The verdict line.
 *
 * Written to describe, not to judge. An earlier draft counted measures that
 * "membaik" or "memburuk", which quietly asserted that a cooperative sitting
 * further from a minimarket is a better cooperative. That is an argument the
 * report makes with evidence elsewhere; a page recomputing one unverified point
 * has not earned it. So the verdict names what moved, in the units the reader
 * just saw, and leaves the reading to them.
 *
 * What it does emphasise is **band crossings**. The report publishes bands, not
 * raw distances, so a correction only changes a published classification when
 * it moves the cooperative from one band to another. That is the difference
 * between "the number shifted a little" and "this cooperative is filed under
 * the wrong heading", and it is the only thing here that could actually warrant
 * a correction to the report.
 */
export function renderVerdict(el, { official, reported, moved }) {
  if (!reported) {
    el.hidden = true;
    return;
  }
  const changed = [];
  const crossed = [];
  for (const m of MEASURES) {
    const d = delta(m, official, reported);
    if (!d || d.kind === "same") continue;
    changed.push({ m, d });
    if (d.crossed) crossed.push({ m, d });
  }

  let headline;
  if (!changed.length) {
    headline = `Tidak ada satu pun ukuran yang berubah. Pada jarak
      ${metres(moved)} dari koordinat resmi, koreksi ini tidak mengubah
      satu pun angka yang kami terbitkan tentang koperasi ini.`;
  } else if (!crossed.length) {
    headline = `${changed.length} dari ${MEASURES.length} ukuran bergeser,
      tetapi tidak ada yang berpindah kelas. Koreksi sejauh ${metres(moved)} ini
      menggeser angkanya tanpa mengubah kategori mana pun yang dipakai laporan.`;
  } else {
    const names = crossed.map(({ m }) => m.label.toLowerCase());
    headline = `Koreksi sejauh ${metres(moved)} ini memindahkan
      <strong>${names.join(" dan ")}</strong> ke kelas yang berbeda. Kelas
      itulah yang dipakai laporan untuk mengelompokkan koperasi, jadi bila titik
      yang Anda tandai benar, koperasi ini masuk kategori yang berbeda dari yang
      kami terbitkan.`;
  }

  el.hidden = false;
  el.innerHTML = `
    <h2>Apa artinya</h2>
    <p>${headline}</p>
    <p class="periksa-caveat">Angka di atas dihitung ulang di peramban Anda
      dengan metode yang sama persis dengan laporan ini
      (<a href="../methods/03-population-coverage/">populasi</a>,
      <a href="../methods/05-road-access/">jalan</a>,
      <a href="../methods/17-building-proximity/">bangunan</a>,
      <a href="../methods/06-minimarket-proximity/">minimarket</a>,
      <a href="../methods/10-coop-clustering/">koperasi terdekat</a>).
      <strong>Keduanya sama-sama belum terverifikasi</strong>: koordinat
      SIMKOPDES adalah posisi representatif per wilayah menurut platformnya
      sendiri, dan titik yang Anda tandai adalah keterangan yang belum kami
      periksa di lapangan. Halaman ini tidak mengubah satu pun angka nasional
      dalam laporan, dan tidak mengirim atau menyimpan apa pun.</p>`;
}

/**
 * Provenance: what each number was measured against, at what resolution, and
 * which method page derives it.
 *
 * Resolution is stated per row because it is the thing that decides how much a
 * figure can be trusted, and it differs by an order of magnitude across these
 * five: a 400 m population cell and a 132 m road cell are not the same kind of
 * evidence, and a reader comparing them deserves to know that without opening
 * the appendix.
 */
const SOURCE_ROWS = [
  {
    key: "population",
    label: "Penduduk",
    method: "03-population-coverage",
    res: "Petak H3 r8, sekitar 400 m antar pusat petak",
    detail:
      "Kontur Population Density, disusun dari citra satelit. Kami menjumlahkan petak dalam cincin 0, 3 dan 11 (kira-kira 0,2 / 1,4 / 5,1 km).",
  },
  {
    key: "road",
    label: "Jalan",
    method: "05-road-access",
    res: "Petak H3 r10, sekitar 132 m antar pusat petak",
    detail:
      "Jalan OpenStreetMap dirasterkan menjadi petak: tiap garis jalan dipadatkan hingga 55 m lalu diindeks. Jarak dihitung sebagai jumlah cincin dikali 132 m, jadi ini rentang, bukan ukuran pasti.",
  },
  {
    key: "building",
    label: "Bangunan",
    method: "17-building-proximity",
    res: "Petak H3 r10, sekitar 132 m antar pusat petak",
    detail:
      "Gabungan Google Open Buildings, Microsoft Building Footprints dan OpenStreetMap yang dirilis VIDA: 137,1 juta bangunan di Indonesia. Titik tiap bangunan diambil dari pusat kotak batasnya.",
  },
  {
    key: "minimarket",
    label: "Minimarket",
    method: "06-minimarket-proximity",
    res: "Titik koordinat, jarak lingkaran besar (bukan rentang petak)",
    detail:
      "Hanya gerai kelas 1 (minimarket dan toko kelontong modern setara Indomaret atau Alfamart). Supermarket dan department store sengaja dikeluarkan karena bukan pesaing koperasi desa.",
  },
  {
    key: "nearest",
    label: "Koperasi terdekat",
    method: "10-coop-clustering",
    res: "Titik koordinat, jarak lingkaran besar",
    detail:
      "Dihitung terhadap 83.379 koperasi lain dalam data yang sama, tidak termasuk koperasi ini sendiri.",
  },
];

export function renderProvenance(el, manifest) {
  const built = manifest?.built ?? DASH;
  const rows = SOURCE_ROWS.map(
    (s) => `
      <tr>
        <th scope="row"><a href="../methods/${s.method}/">${s.label}</a></th>
        <td>${s.res}</td>
        <td>${s.detail}</td>
      </tr>`,
  ).join("");

  el.innerHTML = `
    <h2>Sumber data dan resolusinya</h2>
    <p>Tiap angka di tabel atas berasal dari satu lampiran metode yang bisa
      ditelusuri sampai ke kodenya. Klik nama ukurannya untuk membaca cara
      penurunannya.</p>
    <div class="periksa-sources-wrap">
      <table class="data-table periksa-sources">
        <thead>
          <tr>
            <th scope="col">Ukuran</th>
            <th scope="col">Resolusi data masukan</th>
            <th scope="col">Keterangan</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
    <p class="periksa-caveat">Peta bangunan, jalan dan minimarket tidak pernah
      lengkap, terutama di pedesaan. Karena itu setiap hasil di halaman ini
      berbunyi <em>terpetakan</em>: "tidak ada bangunan terpetakan dalam 1 km"
      berarti tidak ada yang tercatat di peta, bukan tidak ada rumah di sana.
      Indeks sel yang dipakai halaman ini dibangun ${built}.</p>`;
}

/**
 * A prefilled GitHub issue for one marked point.
 *
 * The page still submits nothing by itself: this hands the reader a filled-in
 * form on a site they control, and they decide whether to send it. That keeps
 * the "nothing leaves your browser automatically" promise intact while giving a
 * correction somewhere to go, which is what the corrections log in /about/
 * already promises.
 */
const REPO_ISSUES = "https://github.com/danylaksono/kopdes-vis/issues";

export function renderReportLink(el, { coop, official, reported, moved }) {
  if (!reported) {
    el.hidden = true;
    return;
  }
  const lines = [
    `**Koperasi**: ${coop.cooperative}`,
    `**ID SIMKOPDES**: ${coop.cooperative_id}`,
    `**Wilayah**: ${coop.village ?? DASH}, Kec. ${coop.subdistrict ?? DASH}, ${coop.district ?? DASH}, ${coop.province ?? DASH}`,
    "",
    `**Koordinat SIMKOPDES**: ${official.lat.toFixed(6)}, ${official.lon.toFixed(6)}`,
    `**Koordinat yang saya laporkan**: ${reported.lat.toFixed(6)}, ${reported.lon.toFixed(6)}`,
    `**Selisih**: ${metres(moved)}`,
    "",
    `**Tautan hasil**: ${location.href}`,
    "",
    "**Dasar koreksi** (mohon isi: citra satelit, kunjungan lapangan, dokumen, dll):",
    "",
  ].join("\n");

  const href =
    `${REPO_ISSUES}/new` +
    `?title=${encodeURIComponent(`Koreksi koordinat: ${coop.cooperative}`)}` +
    `&body=${encodeURIComponent(lines)}`;

  el.hidden = false;
  el.innerHTML = `
    <h2>Melaporkan koreksi ini</h2>
    <p>Halaman ini tidak mengirim apa pun dengan sendirinya. Bila Anda yakin
      titik yang Anda tandai benar, tombol di bawah membuka formulir isu di
      repositori proyek dengan koordinat dan hasil perhitungan sudah terisi.
      Anda yang memutuskan mengirimkannya, dan koreksi yang terverifikasi masuk
      ke <a href="../about/">catatan koreksi publik</a>.</p>
    <p><a class="periksa-report-btn" href="${href}" target="_blank"
      rel="noopener noreferrer">Buka formulir koreksi di GitHub</a></p>
    <p class="periksa-caveat">Butuh akun GitHub. Tidak punya? Kirimkan tautan
      halaman ini lewat kanal mana pun yang tercantum di
      <a href="../about/">Tentang</a>; koordinatnya sudah tersimpan di dalam
      tautan.</p>`;
}

/** Fill the picker's result list. */
export function renderResults(el, matches, onPick) {
  el.innerHTML = "";
  if (!matches.length) {
    el.innerHTML = `<li class="empty">Tidak ada koperasi yang cocok.</li>`;
    return;
  }
  for (const m of matches) {
    const li = document.createElement("li");
    li.innerHTML = `
      <button type="button">
        <span class="r-name">${m.cooperative}</span>
        <span class="r-where">${m.village ?? DASH}, ${m.subdistrict ?? DASH},
          ${m.district ?? DASH}</span>
      </button>`;
    li.querySelector("button").addEventListener("click", () => onPick(m));
    el.append(li);
  }
}
