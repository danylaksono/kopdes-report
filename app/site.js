/**
 * site.js — shared shell for the kopdes investigative report.
 *
 * Injects the top navigation and footer (so the markup is not repeated across
 * a dozen static pages), exposes a client-side markdown renderer used by
 * the /methods/ appendix — the single-source-of-truth rule: method pages are
 * rendered from reports/NN-slug/README.md, never written twice — and binds
 * published figures to data/web/figures.json so a re-run report cannot leave a
 * stale number on a page (see applyFigures below).
 *
 * No build step: dependencies are CDN ES modules, everything runs on GitHub
 * Pages as-is.
 */

import { marked } from "https://cdn.jsdelivr.net/npm/marked@12.0.2/lib/marked.esm.js";

const SITE = {
  name: "Koperasi Desa Merah Putih",
  kicker: "Sebuah investigasi data",
};

/**
 * Root-relative prefix for links, set per page via <body data-root="../">.
 * Root page leaves it empty.
 */
const ROOT = document.body.dataset.root ?? "";

const NAV = [
  { href: "", label: "Cerita" },
  { href: "explore/", label: "Peta" },
  { href: "tabel/", label: "Tabel" },
  { href: "periksa/", label: "Periksa" },
  { href: "findings/", label: "Temuan" },
  { href: "methods/", label: "Metode" },
  { href: "data/", label: "Data" },
  { href: "about/", label: "Tentang" },
];

function currentPath() {
  // normalise to a directory path, e.g. "/findings/remoteness/"
  let p = location.pathname;
  if (!p.endsWith("/")) p = p.slice(0, p.lastIndexOf("/") + 1);
  return p;
}

function isActive(n) {
  if (n.href === "") {
    // "Cerita" is active only at the site root.
    return currentPath() === "/";
  }
  const target = new URL(ROOT + n.href, location.href).pathname;
  const cur = currentPath();
  return cur === target || cur.startsWith(target);
}

export function renderNav(container) {
  const nav = document.createElement("nav");
  nav.className = "site-nav";
  nav.innerHTML = `
    <div class="site-nav-inner">
      <div class="brand">
        <a href="${ROOT}"><span class="brand-kicker">${SITE.kicker}</span>${SITE.name}</a>
      </div>
      ${NAV.map(
        (n) =>
          `<a class="nav-link${isActive(n) ? " active" : ""}" href="${ROOT}${n.href}">${n.label}</a>`,
      ).join("")}
    </div>`;
  container.replaceWith(nav);
  return nav;
}

export function renderFooter(container) {
  const f = document.createElement("footer");
  f.className = "site-footer";
  f.innerHTML = `
    <div class="site-footer-inner">
      <p><strong>${SITE.name}</strong>: ${SITE.kicker}.</p>
      <p>Investigasi ini disusun oleh <strong>Dany Laksono</strong>.</p>
      <p>Semua angka dapat ditelusuri ke laporan metode yang dapat direproduksi
      (<a href="${ROOT}methods/">Metode</a>). Data mentah dan jejak revisi:
      <a href="${ROOT}data/">Data</a> · <a href="${ROOT}about/">Kebijakan koreksi</a>.</p>
    </div>`;
  container.replaceWith(f);
  return f;
}

/**
 * The published-figures registry.
 *
 * `data/web/figures.json` is written by scripts/verify_published_figures.py
 * from the committed mart and the report tables, so every number in it is what
 * the data currently says. A page marks a figure with
 * `<span data-fig="key">83.379</span>` and this swaps in the registry's text.
 *
 * The literal stays in the HTML on purpose. It is what a reader sees with no
 * JavaScript, what shows up in a diff, and what the verifier compares against,
 * so the committed page has to be true on its own. This is a safety net for
 * the window between re-running a report and re-reading the prose, not a
 * licence to leave the prose stale: a mismatch is a CI failure.
 *
 * Formatting is not repeated here. The registry ships the rendered Indonesian
 * string and this injects it verbatim, so there is no second formatter to
 * drift out of step with the first.
 */
let figuresPromise = null;

function figures() {
  if (!figuresPromise) {
    // no-cache, not no-store: revalidate against the server every load, but
    // still take a 304 and the cached body when nothing changed. This is the
    // one file on the site whose entire job is to be current, and a reader
    // holding yesterday's copy behind a CDN would reintroduce exactly the
    // stale number it exists to prevent.
    figuresPromise = fetch(`${ROOT}data/web/figures.json`, { cache: "no-cache" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.status))))
      .catch((e) => {
        // Not fatal: every bound element already contains the right number.
        console.warn("figures.json unavailable, keeping the committed text", e);
        return {};
      });
  }
  return figuresPromise;
}

/** Swap every `[data-fig]` inside `root` for the registry's current text. */
export async function applyFigures(root = document) {
  const reg = await figures();
  for (const el of root.querySelectorAll("[data-fig]")) {
    const fig = reg[el.dataset.fig];
    if (!fig) continue;
    if (el.textContent.trim() !== fig.text) {
      console.warn(
        `stale figure in the page source: ${el.dataset.fig} reads ` +
          `"${el.textContent.trim()}", the data says "${fig.text}". ` +
          "Run scripts/verify_published_figures.py --emit and update the prose.",
      );
    }
    el.textContent = fig.text;
  }
}

/** Render a report README (GitHub-flavoured-ish markdown) into a container. */
export async function renderMarkdownInto(container, markdown) {
  container.innerHTML = marked.parse(markdown, { gfm: true, breaks: false });
  container.classList.add("md-prose");
  // give tables the site styling
  for (const t of container.querySelectorAll("table")) {
    t.classList.add("data-table");
  }
  // The method prose carries data-fig spans too, and marked passes inline HTML
  // through, so the registry has to be applied after the parse.
  await applyFigures(container);
}

export async function fetchMarkdown(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`fetch ${url} -> ${res.status}`);
  return res.text();
}

/** Format a number in the Indonesian locale (1.234.567). */
export function id(n, maxFrac = 0) {
  if (n == null || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString("id-ID", { maximumFractionDigits: maxFrac });
}

/** Rupiah shorthand: 202,6 miliar / 40,3 miliar. */
export function rp(n) {
  if (n == null || Number.isNaN(n)) return "—";
  const abs = Math.abs(n);
  if (abs >= 1e12)
    return `${(n / 1e12).toLocaleString("id-ID", { maximumFractionDigits: 1 })} triliun`;
  if (abs >= 1e9)
    return `${(n / 1e9).toLocaleString("id-ID", { maximumFractionDigits: 1 })} miliar`;
  if (abs >= 1e6)
    return `${(n / 1e6).toLocaleString("id-ID", { maximumFractionDigits: 1 })} juta`;
  return n.toLocaleString("id-ID");
}

// Boot the shared shell where the placeholders exist.
document.addEventListener("DOMContentLoaded", () => {
  const navSlot = document.getElementById("site-nav");
  const footSlot = document.getElementById("site-footer");
  if (navSlot) renderNav(navSlot);
  if (footSlot) renderFooter(footSlot);
  applyFigures();
});
