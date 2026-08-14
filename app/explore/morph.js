/**
 * morph.js — the "Kisi Provinsi" scale.
 *
 * geo-morpher morphs the regular provinsi boundary into a grid cartogram while
 * the kopdes provinsi glyphs ride the interpolated centroids. The glyphs reuse
 * app/explore/glyph.js, so profile / composition / measure stay identical to
 * the provinsi scale; only the geometry underneath changes.
 *
 * geo-morpher is loaded lazily: it is a CDN ESM module that the rest of the
 * explorer never pays for until this scale is entered.
 *
 * The controller the caller owns:
 *   enter()            animate 0 -> 1 (map to grid)
 *   exit(done)         clear glyphs, animate 1 -> 0, then tear down
 *   remove()           tear down immediately (basemap swap)
 *   setSpec(spec)      redraw glyphs for a new mode/family/measure
 *   factor()           current morph factor
 *   glyphs             the underlying glyph controller (size-slider redraws)
 */

import {
  drawGlyph,
  sizeFor,
  sizeReference,
  summarizeAnchor,
  valueExtent,
} from "./glyph.js";
import { loadBoundaries, loadProvinceCartogram } from "./data.js";

const GEOMORPHER_URL =
  "https://cdn.jsdelivr.net/npm/geo-morpher@0.2.0/dist/geo-morpher.esm.js";

let gmPromise = null;
function loadGeomorpher() {
  if (!gmPromise) gmPromise = import(GEOMORPHER_URL);
  return gmPromise;
}

/** Two instances overlap whenever the reader leaves and re-enters the scale
 *  while the exit is still animating. They must not share layer and source
 *  ids: the old instance's teardown removes them by id, and with one shared
 *  idBase it takes the live instance's layers down with it — the scale goes
 *  blank, and the live instance only finds out when its next updateMorphFactor
 *  throws. Each instance gets its own namespace instead. */
let instanceSeq = 0;

/** geo-morpher hands out join keys as strings (the grid CSV column); the
 *  aggregate rows use INTEGER admin ids, so lookups are keyed by string. */
const strId = (v) => (v == null ? v : String(v));

export async function createMorphLevel({
  map,
  boundary,
  rows, // loadLevel("provinsi") — one FeatureCollection of full aggregate rows
  spec,
  sizing, // state.sizing, mutated in place by the size slider
  onStats,
  onHover,
  onClick,
}) {
  const gm = await loadGeomorpher();
  const gridCsv = await loadProvinceCartogram();

  // Our boundary stores province_id as a JSON number; the grid CSV stores it
  // as a string. Coerce the boundary side so the two join keys match, and key
  // the glyph data the same way.
  const regular = {
    ...boundary,
    features: boundary.features.map((f) => ({
      ...f,
      properties: { ...f.properties, id: String(f.properties.id) },
    })),
  };

  const byId = new Map();
  const anchorById = new Map();
  for (const f of rows.features) {
    const id = strId(f.properties.admin_id);
    byId.set(id, f.properties);
    anchorById.set(id, f.geometry.coordinates);
  }

  const morpher = new gm.GeoMorpher({
    regularGeoJSON: regular,
    cartogramGeoJSON: gridCsv,
    geoJSONJoinColumn: "id",
    normalize: false,
    projection: gm.WGS84Projection,
    cartogramGridOptions: {
      idField: "id",
      rowField: "row",
      colField: "col",
      cellPadding: 0.08,
      rowOrientation: "top",
      colOrientation: "left",
      // A compact, centred lattice instead of the country's full geographic
      // extent. When the grid is stretched over the whole map its cell centres
      // sit almost on top of the provinces, so the glyphs barely move and the
      // morph reads as polygons changing shape rather than a re-layout. Giving
      // the grid its own smaller extent makes the morph visibly collapse the
      // provinces into a grid, and the glyphs travel to their cells.
      extent: [100.5, -11.6, 134.5, 6.6],
    },
  });
  await morpher.prepare();

  const morph = await gm.createMapLibreMorphLayers({
    morpher,
    map,
    morphFactor: 0,
    idBase: `kisi-${++instanceSeq}`,
    // The one layer that moves. Styled like the boundary layer on the plain
    // Provinsi scale (layers.js: almost invisible fill, hairline outline) so
    // that at factor 0 the morph reads as those same boundaries lifting off.
    interpolatedStyle: {
      paint: {
        "fill-color": "#6b6255",
        "fill-opacity": 0.06,
        "fill-outline-color": "#8f8674",
      },
    },
  });

  // geo-morpher also draws the two endpoints — the untouched provinces and the
  // finished grid — and leaves both on the whole time. That is what hides the
  // animation: the provinces and the grid are on screen at once, and the
  // interpolated polygons travel between two static copies of themselves, so
  // nothing appears to move. Only the interpolated geometry is shown; at factor
  // 0 and 1 it *is* the regular / cartogram geometry, so nothing is lost.
  morph.setLayerVisibility({
    regular: false,
    cartogram: false,
    interpolated: true,
  });

  const counts = rows.features.map((f) => f.properties.cooperatives || 0);
  const reference = sizeReference(counts);
  const max = counts.reduce((a, b) => (b > a ? b : a), 0);
  const total = counts.reduce((a, b) => a + b, 0);

  let currentSpec = spec;
  let currentSizing = sizing;
  let domain = [0, 100];
  let hoveredId = null;
  let factor = 0;
  let animRaf = null;
  let dead = false; // the animation must stop
  let removed = false; // the layers and listeners are already gone
  // Set at the start of exit(). The glyphs keep riding, but the shapes are
  // moving and on their way out, so they stop answering hover and click.
  let exiting = false;

  function computeStats() {
    let d = [0, 100];
    if (currentSpec.mode === "measure" && currentSpec.stretch) {
      const m = currentSpec.measures[0];
      if (m) d = valueExtent(rows.features.map((f) => m.agg(f.properties)));
    }
    domain = d;
    onStats?.({
      cells: rows.features.length,
      max,
      total,
      domain,
      kind: "admin",
    });
  }

  /**
   * Where a glyph sits at a given factor.
   *
   * geo-morpher rides a glyph on its polygon's centroid, but the Provinsi scale
   * puts the same glyph on the aggregate's own anchor (data.js: anchor_lon /
   * anchor_lat, the mean position of the koperasi themselves). For a province
   * whose mass sits well off the middle of its territory the two are far apart,
   * so entering the scale threw every glyph to a new spot before the morph had
   * moved at all — the snap at the start — and leaving it could never hand back
   * cleanly. Riding the anchor at factor 0 and the grid cell at factor 1 makes
   * both ends of the morph line up with the scale on either side of it.
   *
   * geo-morpher takes `geometry` as a function, and reads `feature.centroid`
   * when one is present, so this only moves the glyphs: the polygons underneath
   * still interpolate the way the library built them.
   */
  const cells = morpher.getCartogramLookup();
  const glyphGeometry = ({ morphFactor: t }) => {
    const fc = morpher.getInterpolatedFeatureCollection(t);
    for (const f of fc.features) {
      const id = strId(f.properties?.id ?? f.properties?.code);
      const from = anchorById.get(id);
      const to = cells[id]?.centroid;
      if (!from || !to) continue;
      f.centroid = [
        from[0] + (to[0] - from[0]) * t,
        from[1] + (to[1] - from[1]) * t,
      ];
    }
    return fc;
  };

  const glyphs = await gm.createMapLibreCustomGlyphLayer({
    morpher,
    map,
    maplibreNamespace: maplibregl,
    geometry: glyphGeometry,
    morphFactor: 0,
    getFeatureId: (f) => f.properties?.id ?? f.properties?.code,
    getGlyphData: ({ featureId }) => byId.get(strId(featureId)) ?? null,
    drawGlyph: ({ data, featureId }) => {
      if (!data) return null;
      const size = sizeFor(
        currentSpec,
        data.cooperatives,
        reference,
        currentSizing.maxPx,
        currentSizing.uniformPx,
      );
      if (size <= 0) return null;
      const summary = summarizeAnchor(data, currentSpec);
      return {
        shape: "custom",
        size,
        customRender: (ctx, x, y, s) =>
          drawGlyph(ctx, x, y, summary, {
            spec: currentSpec,
            size: s,
            hovered: strId(featureId) === hoveredId,
            domain,
          }),
      };
    },
  });

  function setFactor(v) {
    factor = v;
    try {
      morph.updateMorphFactor(v);
      glyphs.updateGlyphs({ morphFactor: v });
    } catch (err) {
      // A basemap swap mid-animation destroys the sources the morph updates;
      // stop rather than throw into the rAF loop. Anything else reaching here
      // is a bug that would otherwise freeze the morph in silence, so say so.
      console.warn("kisi provinsi: morph stopped", err);
      dead = true;
      cancelAnimationFrame(animRaf);
    }
  }

  // Hover and click on the interpolated layer. The payload is the same admin
  // shape the screengrid anchor layer produces, so the tooltip and inspector
  // never learn which layer produced the hit.
  function rowOf(props) {
    return byId.get(strId(props?.id ?? props?.code)) ?? null;
  }

  function onMapMove(e) {
    if (exiting) return;
    const feats = map.queryRenderedFeatures(e.point, {
      layers: [morph.layerIds.interpolated],
    });
    if (!feats.length) {
      if (hoveredId != null) {
        hoveredId = null;
        glyphs.updateGlyphs({ morphFactor: factor });
      }
      map.getCanvas().style.cursor = "";
      onHover?.(null, e);
      return;
    }
    const props = rowOf(feats[0].properties);
    const next = strId(feats[0].properties?.id ?? feats[0].properties?.code);
    if (next !== hoveredId) {
      hoveredId = next;
      glyphs.updateGlyphs({ morphFactor: factor });
    }
    map.getCanvas().style.cursor = "pointer";
    if (props) {
      onHover?.(
        {
          kind: "admin",
          count: props.cooperatives ?? 0,
          rows: null,
          summary: null,
          props,
        },
        e,
      );
    }
  }

  function onMapClick(e) {
    if (exiting) return;
    const feats = map.queryRenderedFeatures(e.point, {
      layers: [morph.layerIds.interpolated],
    });
    if (!feats.length) return;
    const props = rowOf(feats[0].properties);
    if (props) {
      onClick?.({
        kind: "admin",
        count: props.cooperatives ?? 0,
        rows: null,
        summary: null,
        props,
      });
    }
  }

  map.on("mousemove", onMapMove);
  map.on("click", onMapClick);

  /**
   * Drive the factor to `target` over a fixed wall-clock span.
   *
   * Not a fixed step per frame. A frame here costs 38 flubber interpolations
   * plus a full glyph redraw, and the scale being left or entered is drawing
   * its own thousands of glyphs at the same time, so the frame rate swings
   * wildly — a per-frame step turns that straight into speed, which is what
   * made the morph lurch at the start and crawl on the way out to a dense
   * scale. Reading the clock instead keeps the timing honest whatever the
   * renderer is doing, and guarantees the animation ends.
   */
  const FULL_TRIP_MS = 900;
  // Ease in and out, so the polygons gather speed rather than starting at full
  // tilt from a standstill.
  const ease = (p) =>
    p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;

  function animateTo(target, stepFn, onDone) {
    cancelAnimationFrame(animRaf);
    const finish = () => {
      animRaf = null;
      onDone?.();
    };
    const from = factor;
    const span = target - from;
    if (dead || span === 0) {
      if (!dead) stepFn(target);
      return finish();
    }
    // Scale by distance, so leaving part-way through an entry comes back at the
    // same speed instead of spending the whole beat on a short trip.
    const ms = FULL_TRIP_MS * Math.abs(span);
    const t0 = performance.now();
    const step = (now) => {
      if (dead) return finish();
      const p = Math.min(1, (now - t0) / ms);
      stepFn(p >= 1 ? target : from + span * ease(p));
      if (dead || p >= 1) return finish();
      animRaf = requestAnimationFrame(step);
    };
    animRaf = requestAnimationFrame(step);
  }

  function teardown() {
    // Tracked apart from `dead`: an animation that gave up mid-flight also sets
    // `dead`, and gating the cleanup on it would leave the layers, the glyph
    // canvas and the map listeners behind for good.
    if (removed) return;
    removed = true;
    dead = true;
    cancelAnimationFrame(animRaf);
    map.off("mousemove", onMapMove);
    map.off("click", onMapClick);
    try {
      glyphs.destroy();
    } catch (err) {
      /* ignore */
    }
    try {
      morph.remove();
    } catch (err) {
      /* ignore */
    }
  }

  computeStats();

  return {
    glyphs,
    factor: () => factor,
    enter: () => animateTo(1, setFactor),
    exit: (done) => {
      // The glyphs ride the polygons back rather than being cleared: they are
      // the thing the reader is following, and dropping them at the grid while
      // the map reassembles behind them is what made the return read as broken.
      // The caller holds the next scale's glyphs back until `done` fires, so
      // the two sets never share the screen — and because factor 0 puts these
      // glyphs on the aggregate anchors, the hand-off lands on the same pixels.
      exiting = true;
      animateTo(0, setFactor, () => {
        teardown();
        done?.();
      });
    },
    setSpec(nextSpec) {
      currentSpec = nextSpec;
      computeStats();
      glyphs.updateGlyphs({ morphFactor: factor });
    },
    remove: teardown,
  };
}
