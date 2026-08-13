/** story.js — the scrollytelling controller for the report's home page.
 *
 * Three two-column chapters (text left, sticky figure right), each an
 * independent `.scrolly` block. An IntersectionObserver per block swaps the
 * figure's chart as steps cross the middle of the viewport, exactly the
 * classic scrollytelling pattern — but the figure now lives in its own column,
 * so text never sits on top of a chart.
 *
 * Also drives the ambient motion: a scroll-progress bar, scroll-reveal for
 * chapter heads / photos / verdicts, animated bar charts, and a lazy boot of
 * the interactive map (story-map.js) the first time it scrolls near.
 *
 * Charts are hand-built inline SVG — no charting dependency, no build step.
 */

const CHART = {
  coverage: {
    title: "Jangkauan program",
    pct: true,
    caption:
      "95% penduduk Indonesia tinggal dalam ±1,4 km dari sebuah koperasi (laporan 03).",
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
    pct: false,
    caption:
      "Hanya 0,21% koperasi tanpa penduduk dalam 5 km — tetapi itu 174 kasus konkret (laporan 03).",
    bars: [
      { label: "Tanpa penduduk 5 km", v: 174, hl: true },
      { label: "< 500 orang", v: 1574 },
      { label: "500–2.000", v: 2408 },
      { label: "2.000–10.000", v: 8133 },
      { label: "> 10.000", v: 71053 },
    ],
  },
  road: {
    title: "Jarak ke jalan, bagi yang “tanpa jalan”",
    pct: false,
    caption:
      "5.114 koperasi tanpa jalan beraspal dalam ±5 km; jarak median 9,7 km (laporan 05, 08).",
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
    pct: true,
    caption: "1 dari 5 koperasi punya koperasi lain dalam 1 km (laporan 10).",
    bars: [
      { label: "dalam 500 m", v: 4.6 },
      { label: "dalam 1 km", v: 22.1, hl: true },
      { label: "dalam 2 km", v: 58.9 },
      { label: "dalam 5 km", v: 91.2 },
    ],
  },
  cluster: {
    title: "Penumpukan sejati",
    pct: true,
    caption:
      "Hanya 6,7% berbagi sel ±1 km dengan koperasi lain — dan tanpa penalti kinerja (laporan 10).",
    bars: [
      { label: "Sendiri di selnya", v: 93.3 },
      { label: "≥ 2 di sel yang sama", v: 6.7, hl: true },
    ],
  },
  funnel: {
    title: "Corong pendaftaran → operasi",
    pct: true,
    caption:
      "Mesin pendaftaran bekerja (rekening, NPWP, izin); mesin operasinya senyap (laporan 11, 13).",
    bars: [
      { label: "Akun terdaftar", v: 96.0 },
      { label: "NPWP", v: 97.1 },
      { label: "NIB (izin usaha)", v: 72.9 },
      { label: "Modal pokok", v: 11.9 },
      { label: "Iuran wajib", v: 9.2 },
      { label: "Transaksi", v: 3.0, hl: true },
    ],
  },
  nib: {
    title: "Izin usaha ada; operasinya tidak",
    pct: true,
    caption: "70,1% desa memegang izin usaha tanpa transaksi yang dilaporkan (laporan 13).",
    bars: [
      { label: "Izin tanpa transaksi", v: 70.1, hl: true },
      { label: "Izin + transaksi", v: 3.0 },
      { label: "Transaksi tanpa izin", v: 0.03 },
      { label: "Tanpa keduanya", v: 26.9 },
    ],
  },
  concentration: {
    title: "Konsentrasi nilai",
    pct: true,
    caption: "100 desa membawa 37% dari seluruh nilai transaksi yang dilaporkan (laporan 02).",
    bars: [
      { label: "100 desa teratas", v: 37, hl: true },
      { label: "1.000 desa teratas", v: 93 },
    ],
  },
};

function fmtPct(v) {
  return Number.isInteger(v) ? String(v) : String(v).replace(".", ",");
}
function fmtCount(v) {
  return v.toLocaleString("id-ID");
}

/**
 * Render one chart into a figure card's `.chart-slot`, then animate.
 *
 * The animation is a two-frame width grow: bars are inserted at width 0 (and
 * value labels hidden), then forced to their target width on the next frame
 * so the CSS `transition: width` does the work. Re-rendering replaces the
 * whole slot, so a figure only ever holds its current chart.
 */
function renderChart(name, slot, card) {
  const c = CHART[name];
  if (!c) return;
  const max = Math.max(...c.bars.map((b) => b.v));
  const W = 720,
    x0 = 356,
    x1 = W - 34,
    rowH = 36,
    barH = 20,
    top = 26;
  const H = top + c.bars.length * rowH + 8;
  const grad = `bar-grad-${name}`;

  const barW = (v) => Math.max((v / max) * (x1 - x0), 2);

  let svg = `<svg class="chart-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="${c.title}" style="width:100%;height:auto">`;
  svg += `<defs><linearGradient id="${grad}" x1="0" y1="0" x2="1" y2="0">` +
    `<stop offset="0" stop-color="#c21c1c"/><stop offset="1" stop-color="#7a0000"/></linearGradient></defs>`;

  c.bars.forEach((b, i) => {
    const y = top + i * rowH;
    svg += `<line x1="${x0}" y1="${y + barH + 6}" x2="${x1}" y2="${y + barH + 6}" class="grid-line"/>`;
    svg += `<text x="${x0 - 14}" y="${y + barH / 2 + 4}" text-anchor="end" class="axis row-label${b.hl ? " hl" : ""}">${b.label}</text>`;
    svg += `<rect x="${x0}" y="${y}" width="0" height="${barH}" rx="5"
            class="bar${b.hl ? " hl" : " muted"}"/>`;
    svg += `<text x="${x0}" y="${y + barH / 2 + 4}" class="axis val${b.hl ? " hl" : ""}">${
      c.pct ? fmtPct(b.v) + "%" : fmtCount(b.v)
    }</text>`;
  });
  svg += "</svg>";

  slot.innerHTML = `<div class="figure-card-head"><h3>${c.title}</h3></div>${svg}` +
    `<figcaption>${c.caption}</figcaption>`;

  // Animate: lay out at zero, then grow on the next frame.
  const bars = [...slot.querySelectorAll("rect.bar")];
  const vals = [...slot.querySelectorAll("text.val")];
  bars.forEach((rect, i) => (rect.style.transitionDelay = `${i * 45}ms`));
  vals.forEach((t) => (t.style.opacity = 0));

  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      bars.forEach((rect, i) => rect.setAttribute("width", barW(c.bars[i].v)));
      vals.forEach((t) => {
        t.style.transition = "opacity .4s ease .3s";
        t.style.opacity = 1;
      });
    });
  });
}

/** Boot one two-column scrolly block: step observer + chart swapping. */
function initScrolly(block) {
  const steps = [...block.querySelectorAll(".step")];
  if (!steps.length) return;
  const card = block.querySelector(".figure-card");
  const slot = card?.querySelector(".chart-slot");
  if (!card || !slot) return;

  const setActive = (idx) => {
    steps.forEach((s, i) => s.classList.toggle("is-active", i === idx));
    const chart = steps[idx].dataset.chart;
    if (chart) {
      card.classList.remove("is-showing");
      // Re-render + animate on the next frame so the fade-out can start cleanly.
      requestAnimationFrame(() => {
        renderChart(chart, slot, card);
        card.classList.add("is-showing");
      });
    }
  };

  const isMobile = window.matchMedia("(max-width: 920px)").matches;
  // Mobile stacks the figure above the steps, so a step should become active
  // only once it is well into the lower part of the viewport — that is where
  // its text (pinned to the bottom of a full-height step) actually sits, clear
  // of the sticky figure. Desktop keeps the classic middle band.
  const rootMargin = isMobile ? "-68% 0px -22% 0px" : "-45% 0px -45% 0px";
  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (e.isIntersecting) setActive(steps.indexOf(e.target));
      }
    },
    { rootMargin },
  );
  steps.forEach((s) => io.observe(s));
  setActive(0);
}

/** Scroll-reveal for anything marked `.reveal`. */
function initReveals() {
  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (e.isIntersecting) {
          e.target.classList.add("is-revealed");
          io.unobserve(e.target);
        }
      }
    },
    { threshold: 0.12, rootMargin: "0px 0px -8% 0px" },
  );
  document.querySelectorAll(".reveal").forEach((el) => io.observe(el));
}

/** Thin scroll-progress bar at the very top of the page. */
function initProgress() {
  const bar = document.getElementById("story-progress-bar");
  if (!bar) return;
  let ticking = false;
  const update = () => {
    const doc = document.documentElement;
    const max = doc.scrollHeight - window.innerHeight;
    bar.style.width = (max > 0 ? (window.scrollY / max) * 100 : 0) + "%";
    ticking = false;
  };
  window.addEventListener(
    "scroll",
    () => {
      if (!ticking) {
        ticking = true;
        requestAnimationFrame(update);
      }
    },
    { passive: true },
  );
  update();
}

/** Boot the interactive map the first time it scrolls near (lazy: saves the
 *  duckdb + maplibre download for readers who never reach it). */
function initMapLazy() {
  const section = document.getElementById("peta");
  if (!section) return;
  let started = false;
  const io = new IntersectionObserver(
    (entries) => {
      if (entries.some((e) => e.isIntersecting) && !started) {
        started = true;
        io.disconnect();
        import("./story-map.js")
          .then((m) => m.initStoryMap())
          .catch((err) => {
            console.error("story map failed to load:", err);
            const loading = document.getElementById("story-map-loading");
            if (loading) loading.textContent = "Peta gagal dimuat.";
          });
      }
    },
    { rootMargin: "600px 0px" },
  );
  io.observe(section);
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".scrolly").forEach(initScrolly);
  initReveals();
  initProgress();
  initMapLazy();
});
