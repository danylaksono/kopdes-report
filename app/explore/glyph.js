/**
 * glyph.js — one glyph specification, drawn identically at all four scales.
 *
 * The map has two very different cell sources: a screen-space grid cell holding
 * N cooperative rows, and an administrative anchor holding one pre-aggregated
 * row. `summarize*` flattens both into the same shape, and everything below it
 * draws that shape without knowing which it came from. That is what keeps a
 * kecamatan glyph and a grid glyph comparable.
 *
 *     { count, values: { measureId: percent|null }, shares: { familyId: [..] } }
 *
 * ## The per-frame budget
 *
 * `summarizeCell` runs inside screengrid's `onAfterAggregate`, which fires once
 * per aggregation — and screengrid aggregates on every rendered frame. So it
 * has to stay a single pass of integer comparisons over the cell's members with
 * no sorting, no closures per row, and no intermediate arrays. `spec` exists to
 * keep it that way: only the measures actually on screen are counted.
 */

import { FAMILY_BY_ID, MEASURE_BY_ID } from "./measures.js";

// ---------------------------------------------------------------------------
// Summaries
// ---------------------------------------------------------------------------

/**
 * What the current view needs computed. Built once when the glyph mode changes,
 * not per cell.
 *
 * @param {'profile'|'composition'|'measure'} mode
 * @param {string[]} measureIds  measures whose share must be counted
 * @param {string|null} familyId class family whose composition must be counted
 * @param {boolean} stretch      fit the ramp to the data instead of 0–100%
 */
export function makeSpec(mode, measureIds, familyId, stretch = false) {
  return {
    mode,
    measures: measureIds.map((id) => MEASURE_BY_ID[id]).filter(Boolean),
    family: familyId ? FAMILY_BY_ID[familyId] : null,
    stretch,
  };
}

/** A screen-grid cell wraps each member as `{data, weight}`. */
const cellMember = (d) => d.data;

/** A bare row is already the cooperative. */
export const identity = (d) => d;

/**
 * Summarise a set of cooperatives.
 *
 * `get` exists so the national reference figures in the legend run through this
 * exact code path over the raw rows. Two implementations of "what share of
 * these cooperatives are far from a road" is one more than can stay in
 * agreement, and the legend is precisely where a disagreement would show.
 */
export function summarizeCell(cellData, spec, get = cellMember) {
  const n = cellData.length;
  if (!n) return null;

  const values = {};
  for (const m of spec.measures) {
    let hits = 0;
    let known = 0;
    for (let i = 0; i < n; i++) {
      const row = get(cellData[i]);
      if (!m.known(row)) continue;
      known++;
      if (m.test(row)) hits++;
    }
    // No measurable member is not the same as none meeting the condition, and
    // the glyph draws the two differently.
    values[m.id] = known ? (100 * hits) / known : null;
  }

  const shares = {};
  if (spec.family) {
    const fam = spec.family;
    const key = `${fam.id}_k`;
    const counts = new Array(fam.classes.length).fill(0);
    let known = 0;
    for (let i = 0; i < n; i++) {
      const k = get(cellData[i])[key];
      if (k == null) continue;
      counts[k - 1]++; // class codes are 1-based, from list_position()
      known++;
    }
    shares[fam.id] = known ? counts.map((c) => (100 * c) / known) : null;
  }

  return { count: n, values, shares };
}

/** Summarise an administrative anchor from its pre-aggregated row. */
export function summarizeAnchor(props, spec) {
  const values = {};
  for (const m of spec.measures) values[m.id] = m.agg(props);

  const shares = {};
  if (spec.family) {
    const fam = spec.family;
    const parts = fam.classes.map((c) => props[`${fam.id}_share_${c.key}`]);
    shares[fam.id] = parts.every((p) => p == null)
      ? null
      : parts.map((p) => p ?? 0);
  }

  return { count: props.cooperatives ?? 0, values, shares };
}

// ---------------------------------------------------------------------------
// Sizing
// ---------------------------------------------------------------------------

/**
 * The count a full-size glyph represents.
 *
 * Not the maximum: cooperative counts in Indonesia are extremely skewed, and
 * scaling to the true maximum pins Java at full size and squashes everything
 * from Sumatra eastwards into the minimum, where every glyph looks the same and
 * the encoding stops carrying information. Scaling to a high percentile spends
 * the size range on the cells there are most of, and lets the handful above it
 * clamp — they are already unmistakable by position.
 */
export function sizeReference(counts, q = 0.92) {
  if (!counts.length) return 1;
  const sorted = Float64Array.from(counts).sort();
  return Math.max(
    1,
    sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * q))],
  );
}

/**
 * Glyph side length in pixels for a cell holding `count` cooperatives.
 *
 * Square-rooted so the glyph's *area* tracks the count — the standard
 * proportional-symbol correction. `minPx` keeps a one-cooperative cell above
 * the threshold where a glyph stops being readable as a glyph at all.
 *
 * **Not used by profile mode**, and that is the point of `sizeFor` below.
 */
export function glyphSize(count, reference, maxPx, minPx = 11) {
  if (!count) return 0;
  const t = Math.min(1, Math.sqrt(count / reference));
  return Math.max(Math.min(minPx, maxPx), Math.min(maxPx, maxPx * t));
}

/**
 * The box a glyph is drawn in, which depends on what the glyph encodes.
 *
 * Profile mode gets a **uniform** box at every cell. Sizing it by count breaks
 * the mode twice over: the small boxes fall below the size where four bars
 * read as four bars, and — worse — bar height stops being comparable between
 * cells, because the same 40 % share draws taller in a big box than in a small
 * one. A profile glyph exists to be compared with the profile glyph next to it,
 * and a varying box is exactly the thing that prevents it.
 *
 * Composition and measure mode keep the count encoding. Composition reads as
 * proportion-of-whole, which is scale-invariant, and measure mode spends colour
 * on the value, which leaves size free — the ordinary proportional-symbol
 * arrangement.
 *
 * The trade: in profile mode nothing on the map says how many cooperatives a
 * cell holds. The legend says so, and the count is one click away.
 */
export function sizeFor(spec, count, reference, maxPx, uniformPx = maxPx) {
  if (spec.mode === "profile") return count ? uniformPx : 0;
  return glyphSize(count, reference, maxPx);
}

// ---------------------------------------------------------------------------
// Drawing
// ---------------------------------------------------------------------------

const PAPER = "rgba(255,254,251,0.66)";
const RULE = "rgba(26,26,26,0.3)";
const NODATA = "rgba(26,26,26,0.16)";

/** Ramp for single-measure mode: paper to the report's investigative red. */
const MEASURE_STOPS = [
  [252, 247, 240],
  [246, 216, 180],
  [235, 165, 120],
  [206, 96, 70],
  [154, 26, 30],
  [98, 0, 16],
];

export function measureColor(pct, domain = [0, 100]) {
  if (pct == null) return "rgba(26,26,26,0.12)";
  const [lo, hi] = domain;
  const t = hi > lo ? Math.min(Math.max((pct - lo) / (hi - lo), 0), 1) : 0.5;
  const pos = t * (MEASURE_STOPS.length - 1);
  const i = Math.min(Math.floor(pos), MEASURE_STOPS.length - 2);
  const f = pos - i;
  const a = MEASURE_STOPS[i];
  const b = MEASURE_STOPS[i + 1];
  return `rgb(${Math.round(a[0] + (b[0] - a[0]) * f)},${Math.round(
    a[1] + (b[1] - a[1]) * f,
  )},${Math.round(a[2] + (b[2] - a[2]) * f)})`;
}

/** CSS gradient matching `measureColor`, for the legend ramp. */
export function measureRampCss(steps = 24) {
  const parts = [];
  for (let i = 0; i < steps; i++) {
    const p = (i / (steps - 1)) * 100;
    parts.push(`${measureColor(p)} ${p.toFixed(1)}%`);
  }
  return `linear-gradient(to right, ${parts.join(", ")})`;
}

/**
 * The range a stretched ramp should span, from the values actually present.
 *
 * Several measures in this dataset sit in a narrow band near one end — 96.5% of
 * cooperatives report no transactions, so on an absolute 0–100% ramp every area
 * in the country is the same dark red and the map says nothing beyond a fact
 * the legend already stated. Stretching recovers the variation within that
 * band. It is off by default and the legend prints the bounds when it is on,
 * because a ramp whose ends move is a ramp that can mislead.
 */
export function valueExtent(values) {
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of values) {
    if (v == null) continue;
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  if (lo === Infinity) return [0, 100];
  // Identical values would divide by zero; give them a nominal band so the
  // single value lands mid-ramp rather than at an arbitrary end.
  return hi > lo ? [lo, hi] : [Math.max(0, lo - 1), Math.min(100, hi + 1)];
}

/**
 * Draw one cell. `x`/`y` is the cell centre.
 *
 * The paper plate is only painted where the mark needs a ground. Profile bars
 * do: they are thin, they leave most of the glyph empty, and without a plate
 * the short ones vanish into whatever coastline or label happens to run under
 * them. A stacked column and a filled square are already opaque, and at
 * administrative scales — where hundreds of glyphs overlap around Java —
 * plating them turns a readable map into a pile of paper chips.
 */
export function drawGlyph(ctx, x, y, summary, opts) {
  const { spec, size, hovered, domain } = opts;
  if (!summary || size <= 0) return;

  const half = size / 2;
  ctx.save();

  if (spec.mode === "profile" || hovered) {
    ctx.fillStyle = PAPER;
    ctx.strokeStyle = hovered ? "rgba(160,0,0,0.9)" : "rgba(26,26,26,0.16)";
    ctx.lineWidth = hovered ? 1.5 : 0.75;
    roundRect(ctx, x - half, y - half, size, size, Math.min(3, size * 0.12));
    if (spec.mode === "profile") ctx.fill();
    ctx.stroke();
  }

  if (spec.mode === "composition")
    drawComposition(ctx, x, y, size, summary, spec);
  else if (spec.mode === "measure")
    drawMeasure(ctx, x, y, size, summary, spec, domain);
  else drawProfile(ctx, x, y, size, summary, spec);

  ctx.restore();
}

/** Four deficit bars, one per report act. Taller is worse, always. */
function drawProfile(ctx, x, y, size, summary, spec) {
  const measures = spec.measures;
  if (!measures.length) return;

  const pad = Math.max(1, size * 0.1);
  const inner = size - pad * 2;
  const left = x - size / 2 + pad;
  const base = y + size / 2 - pad;
  const slot = inner / measures.length;
  const barW = Math.max(1, slot * 0.68);

  // Baseline: without it, a row of short bars reads as noise rather than as
  // four measurements that happen to be low.
  ctx.strokeStyle = RULE;
  ctx.lineWidth = 0.75;
  ctx.beginPath();
  ctx.moveTo(left, base + 0.5);
  ctx.lineTo(left + inner, base + 0.5);
  ctx.stroke();

  for (let i = 0; i < measures.length; i++) {
    const m = measures[i];
    const v = summary.values[m.id];
    const bx = left + slot * i + (slot - barW) / 2;

    if (v == null) {
      // Unmeasured: a stub at the baseline, so the slot is visibly occupied by
      // "no data" rather than looking like a zero.
      ctx.fillStyle = NODATA;
      ctx.fillRect(bx, base - 1.5, barW, 1.5);
      continue;
    }
    const h = Math.max(0.75, (Math.min(v, 100) / 100) * inner);
    ctx.fillStyle = m.color;
    ctx.fillRect(bx, base - h, barW, h);
  }
}

/** A stacked column: how the area's cooperatives divide across one family. */
function drawComposition(ctx, x, y, size, summary, spec) {
  const fam = spec.family;
  const parts = summary.shares[fam.id];
  const pad = Math.max(1, size * 0.1);
  const inner = size - pad * 2;
  const w = Math.max(2, inner * 0.62);
  const left = x - w / 2;
  let top = y - inner / 2;

  if (!parts) {
    ctx.fillStyle = NODATA;
    ctx.fillRect(left, top, w, inner);
    return;
  }

  const total = parts.reduce((a, b) => a + b, 0) || 1;
  for (let i = 0; i < parts.length; i++) {
    const h = (parts[i] / total) * inner;
    if (h <= 0) continue;
    ctx.fillStyle = fam.classes[i].color;
    // +0.4 closes the hairline seams that rounding leaves between segments.
    ctx.fillRect(left, top, w, h + 0.4);
    top += h;
  }
  ctx.strokeStyle = RULE;
  ctx.lineWidth = 0.6;
  ctx.strokeRect(left, y - inner / 2, w, inner);
}

/** One measure: a filled plate, darker the higher the share. */
function drawMeasure(ctx, x, y, size, summary, spec, domain) {
  const m = spec.measures[0];
  if (!m) return;
  const v = summary.values[m.id];
  const pad = Math.max(1, size * 0.16);
  const inner = size - pad * 2;

  ctx.fillStyle = measureColor(v, domain);
  roundRect(
    ctx,
    x - inner / 2,
    y - inner / 2,
    inner,
    inner,
    Math.min(2, inner * 0.12),
  );
  ctx.fill();

  if (v == null) {
    // A diagonal through the plate: unmistakably "not measured here" at any
    // size, where a pale fill would just read as a low value.
    ctx.strokeStyle = "rgba(26,26,26,0.35)";
    ctx.lineWidth = 0.9;
    ctx.beginPath();
    ctx.moveTo(x - inner / 2, y + inner / 2);
    ctx.lineTo(x + inner / 2, y - inner / 2);
    ctx.stroke();
  }
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  if (typeof ctx.roundRect === "function") {
    ctx.roundRect(x, y, w, h, r);
    return;
  }
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}
