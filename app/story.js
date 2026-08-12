/** story.js — the scrollytelling controller for the report's home page.
 *
 * A lightweight scroll-driven narrative: a sticky figure on the right, text
 * steps on the left, IntersectionObserver swaps the figure as each step
 * enters the middle of the viewport. All charts are hand-built inline SVG —
 * no charting dependency, no build step.
 */

const CHART = {
  coverage: {
    title: "Jangkauan program",
    unit: "% penduduk",
    note: "95% penduduk tinggal dalam ±1,4 km dari sebuah koperasi.",
    bars: [
      { label: "Sel sendiri (400 m)", v: 23.4 },
      { label: "±0,5 km", v: 73.2 },
      { label: "±1,4 km", v: 95.0, hl: true },
      { label: "±2,8 km", v: 98.9 },
      { label: "±5,1 km", v: 99.8 },
    ],
  },
  tail: {
    title: "Ekor keterpencilan",
    unit: "koperasi",
    note: "Hanya 0,21% koperasi tanpa penduduk dalam 5 km — tetapi itu 174 kasus konkret.",
    bars: [
      { label: "Tanpa penduduk 5 km", v: 174, hl: true },
      { label: "< 500 orang", v: 1574 },
      { label: "500–2.000", v: 2408 },
      { label: "2.000–10.000", v: 8133 },
      { label: "> 10.000", v: 71053 },
    ],
  },
  road: {
    title: "Jarak ke jalan bagi yang ‘tanpa jalan’",
    unit: "koperasi",
    note: "5.114 koperasi tanpa jalan beraspal dalam ±5 km; median 9,7 km.",
    bars: [
      { label: "5–10 km", v: 2466 },
      { label: "10–25 km", v: 1870 },
      { label: "25–50 km", v: 526 },
      { label: "50–100 km", v: 58 },
      { label: "> 100 km", v: 16, hl: true },
    ],
  },
  nn: {
    title: "Koperasi vs koperasi",
    unit: "% koperasi",
    note: "1 dari 5 koperasi punya koperasi lain dalam 1 km.",
    bars: [
      { label: "dalam 500 m", v: 4.6 },
      { label: "dalam 1 km", v: 22.1, hl: true },
      { label: "dalam 2 km", v: 58.9 },
      { label: "dalam 5 km", v: 91.2 },
    ],
  },
  cluster: {
    title: "Penumpukan sejati",
    unit: "% koperasi",
    note: "Hanya 6,7% berbagi sel ±1 km dengan koperasi lain — dan tanpa penalti kinerja.",
    bars: [
      { label: "Sendiri di selnya", v: 93.3 },
      { label: "≥2 di sel yang sama", v: 6.7, hl: true },
    ],
  },
  funnel: {
    title: "Corong pendaftaran → operasi",
    unit: "% desa",
    note: "Mesin pendaftaran bekerja; mesin operasi tidak.",
    bars: [
      { label: "Akun terdaftar", v: 96.0 },
      { label: "NPWP", v: 97.1 },
      { label: "NIB (izin usaha)", v: 72.9 },
      { label: "Modal pokok", v: 11.9 },
      { label: "Iuran wajib", v: 9.2 },
      { label: "Transaksi", v: 3.0, hl: true },
    ],
  },
  concentration: {
    title: "Konsentrasi nilai",
    unit: "% nilai nasional",
    note: "100 desa membawa 37% dari seluruh nilai transaksi yang dilaporkan.",
    bars: [
      { label: "100 desa teratas", v: 37, hl: true },
      { label: "1.000 desa teratas", v: 93 },
    ],
  },
  nib: {
    title: "Izin usaha ada; operasinya tidak",
    unit: "% desa",
    note: "70,1% desa memegang izin usaha tanpa transaksi yang dilaporkan.",
    bars: [
      { label: "Izin tanpa transaksi", v: 70.1, hl: true },
      { label: "Izin + transaksi", v: 3.0 },
      { label: "Transaksi tanpa izin", v: 0.03 },
      { label: "Tanpa keduanya", v: 26.9 },
    ],
  },
};

function fmt(v) {
  if (v >= 1000) return v.toLocaleString("id-ID");
  return String(v).replace(".", ",");
}

function renderChart(name, container) {
  const c = CHART[name];
  if (!c) return;
  const max = Math.max(...c.bars.map((b) => b.v));
  const W = 620,
    x0 = 250,
    x1 = W - 78,
    rowH = 26,
    top = 34;
  const H = top + c.bars.length * rowH + (c.note ? 22 : 0);
  const barW = (v) => Math.max((v / max) * (x1 - x0), 2);

  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${c.title}" style="width:100%;height:auto">`;
  c.bars.forEach((b, i) => {
    const y = top + i * rowH;
    s += `<text x="${x0 - 12}" y="${y + 12}" text-anchor="end" class="axis">${b.label}</text>`;
    s += `<rect x="${x0}" y="${y + 2}" width="${barW(b.v)}" height="15" rx="3"
            class="bar${b.hl ? "" : " muted"}"/>`;
    s += `<text x="${x0 + barW(b.v) + 8}" y="${y + 13}" class="axis">${fmt(b.v)}${c.unit === "%" ? "%" : ""}</text>`;
  });
  if (c.note) s += `<text x="${x0}" y="${H - 4}" class="axis">${c.note}</text>`;
  s += "</svg>";
  container.innerHTML = `<h3>${c.title}</h3>${s}`;
}

function initScrolly() {
  const scrolly = document.querySelector(".scrolly");
  if (!scrolly) return;
  const sticky = scrolly.querySelector(".sticky .figure-inner");
  const steps = [...scrolly.querySelectorAll(".step")];
  if (!steps.length) return;

  const setActive = (idx) => {
    steps.forEach((s, i) => s.classList.toggle("is-active", i === idx));
    const chart = steps[idx].dataset.chart;
    if (chart) renderChart(chart, sticky);
  };

  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (e.isIntersecting) setActive(steps.indexOf(e.target));
      }
    },
    { rootMargin: "-45% 0px -45% 0px" },
  );
  steps.forEach((s) => io.observe(s));
  setActive(0);
}

document.addEventListener("DOMContentLoaded", initScrolly);
