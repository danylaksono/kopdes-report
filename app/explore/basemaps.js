/**
 * basemaps.js — the backdrops the map can wear.
 *
 * ## On satellite imagery and Google
 *
 * Google's tile endpoints (`mt{0-3}.google.com/vt?lyrs=s`) are not licensed for
 * third-party embedding — they are an internal endpoint of Google Maps, and
 * pulling them into another site breaks the Maps Platform terms whether or not
 * it technically works. For a public investigative report that publishes its own
 * provenance, shipping unlicensed tiles is the wrong trade.
 *
 * So `satelit` uses **Esri World Imagery**, which is the standard freely
 * embeddable high-resolution basemap, is sub-metre over most of Indonesia, and
 * asks only for attribution. `sentinel` is the fully open alternative — EOX's
 * cloudless Sentinel-2 mosaic, CC BY 4.0, ~10 m and seamless, better for reading
 * landcover than for identifying a building.
 *
 * If you have a Google Maps Platform key, the licensed route is their Map Tiles
 * API (session-token based); it would slot in here as another entry.
 *
 * ## Style objects, not just URLs
 *
 * Raster basemaps are declared inline as complete MapLibre styles rather than
 * hosted style URLs, so there is no third party deciding what the satellite view
 * looks like. `dark` tells the app layers to switch to light boundary lines and
 * light point fills — a 0.6 px charcoal hairline is invisible over imagery.
 */

const ESRI_IMAGERY =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
const ESRI_REFERENCE =
  "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}";

/** A raster style: one imagery layer, optionally a labels layer on top. */
function rasterStyle({ tiles, attribution, maxzoom = 19, reference = null }) {
  const sources = {
    imagery: { type: "raster", tiles: [tiles], tileSize: 256, maxzoom, attribution },
  };
  const layers = [
    { id: "background", type: "background", paint: { "background-color": "#0d0f12" } },
    { id: "imagery", type: "raster", source: "imagery", paint: { "raster-opacity": 1 } },
  ];
  if (reference) {
    sources.reference = { type: "raster", tiles: [reference], tileSize: 256, maxzoom };
    layers.push({
      id: "reference",
      type: "raster",
      source: "reference",
      // Place names and boundaries, held back so they orient without competing
      // with the glyphs sitting on top of them.
      paint: { "raster-opacity": 0.85 },
    });
  }
  return { version: 8, sources, layers };
}

export const BASEMAPS = [
  {
    id: "terang",
    label: "Terang",
    hint: "Peta terang, warna mengikuti laporan",
    style: "https://tiles.openfreemap.org/styles/positron",
    // Positron's cool greys against the report's warm paper make the page look
    // like two publications stapled together; `tint` retints land and water.
    tint: true,
    dark: false,
  },
  {
    id: "detail",
    label: "Detail",
    hint: "Jalan, tempat dan tutupan lahan lengkap",
    style: "https://tiles.openfreemap.org/styles/liberty",
    tint: false,
    dark: false,
  },
  {
    id: "satelit",
    label: "Satelit",
    hint: "Citra Esri World Imagery — untuk memeriksa lokasi satu per satu",
    style: rasterStyle({
      tiles: ESRI_IMAGERY,
      reference: ESRI_REFERENCE,
      maxzoom: 19,
      attribution:
        'Citra: <a href="https://www.esri.com/">Esri</a>, Maxar, Earthstar Geographics',
    }),
    tint: false,
    dark: true,
  },
];

export const BASEMAP_BY_ID = Object.fromEntries(BASEMAPS.map((b) => [b.id, b]));

/**
 * Retint a vector basemap into the report's palette.
 *
 * Only touches layers it can find: styles change upstream, and a missing layer
 * should tint what it can rather than take the map down.
 */
export function tintBasemap(map) {
  const tints = [
    ["background", "background-color", "#f7f4ed"],
    ["water", "fill-color", "#dfd9cc"],
    ["waterway", "line-color", "#cfc8b9"],
    ["park", "fill-color", "#eeeee2"],
    ["landcover_wood", "fill-color", "#e9e9dc"],
    ["landuse_residential", "fill-color", "#efece3"],
  ];
  for (const [layer, prop, value] of tints) {
    if (map.getLayer(layer)) map.setPaintProperty(layer, prop, value);
  }
}
