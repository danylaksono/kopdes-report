/**
 * points-layer.js
 *
 * The original per-cooperative view: every kopdes as a clustered MapLibre
 * circle, colored by land-asset verification status. Good for "where exactly
 * is this cooperative", useless for reading national density (83k points
 * collapse into a handful of clusters), which is what grid-layer.js is for.
 */

export const VERIFIED_COLORS = {
  verified: "#2e9e5b",
  not_verified: "#e0a13d",
  no_record: "#9aa0a6",
};

export const VERIFIED_LABELS = {
  verified: "Verified",
  not_verified: "Not verified",
  no_record: "No asset record",
};

const SOURCE_ID = "kopdes";
const LAYER_IDS = ["clusters", "cluster-count", "unclustered-point"];

let popup = null;
const handlers = [];

function on(map, type, layer, fn) {
  map.on(type, layer, fn);
  handlers.push([type, layer, fn]);
}

export function addPointsLayer(map, geojson) {
  map.addSource(SOURCE_ID, {
    type: "geojson",
    data: geojson,
    cluster: true,
    clusterMaxZoom: 12,
    clusterRadius: 45,
  });

  map.addLayer({
    id: "clusters",
    type: "circle",
    source: SOURCE_ID,
    filter: ["has", "point_count"],
    paint: {
      "circle-color": [
        "step",
        ["get", "point_count"],
        "#7fb2f0", 50,
        "#4a90d9", 250,
        "#2c5f9e", 1000,
        "#1b3a63",
      ],
      "circle-radius": ["step", ["get", "point_count"], 14, 50, 18, 250, 24, 1000, 32],
      "circle-stroke-width": 1,
      "circle-stroke-color": "#fff",
    },
  });

  map.addLayer({
    id: "cluster-count",
    type: "symbol",
    source: SOURCE_ID,
    filter: ["has", "point_count"],
    layout: {
      "text-field": ["get", "point_count_abbreviated"],
      "text-font": ["Noto Sans Regular"],
      "text-size": 12,
    },
    paint: { "text-color": "#fff" },
  });

  map.addLayer({
    id: "unclustered-point",
    type: "circle",
    source: SOURCE_ID,
    filter: ["!", ["has", "point_count"]],
    paint: {
      "circle-color": [
        "match",
        ["get", "verified"],
        "verified", VERIFIED_COLORS.verified,
        "not_verified", VERIFIED_COLORS.not_verified,
        VERIFIED_COLORS.no_record,
      ],
      "circle-radius": 5,
      "circle-stroke-width": 1,
      "circle-stroke-color": "#fff",
    },
  });

  on(map, "click", "clusters", (e) => {
    const [feature] = map.queryRenderedFeatures(e.point, { layers: ["clusters"] });
    const clusterId = feature.properties.cluster_id;
    map.getSource(SOURCE_ID).getClusterExpansionZoom(clusterId, (err, zoom) => {
      if (err) return;
      map.easeTo({ center: feature.geometry.coordinates, zoom });
    });
  });

  on(map, "click", "unclustered-point", (e) => {
    const feature = e.features[0];
    const { name, province, district, subdistrict, verified, asset_status } = feature.properties;
    const statusLine = asset_status
      ? `${escapeHtml(VERIFIED_LABELS[verified])} (${escapeHtml(asset_status)})`
      : escapeHtml(VERIFIED_LABELS[verified]);
    popup = new maplibregl.Popup()
      .setLngLat(feature.geometry.coordinates)
      .setHTML(
        `<b>${escapeHtml(name)}</b><br>${escapeHtml(subdistrict)}, ${escapeHtml(district)}<br>${escapeHtml(province)}` +
          `<br><span style="color:${VERIFIED_COLORS[verified]}">&#9679;</span> ${statusLine}`
      )
      .addTo(map);
  });

  for (const layer of ["clusters", "unclustered-point"]) {
    on(map, "mouseenter", layer, () => (map.getCanvas().style.cursor = "pointer"));
    on(map, "mouseleave", layer, () => (map.getCanvas().style.cursor = ""));
  }
}

export function removePointsLayer(map) {
  for (const [type, layer, fn] of handlers.splice(0)) map.off(type, layer, fn);
  if (popup) {
    popup.remove();
    popup = null;
  }
  for (const id of LAYER_IDS) if (map.getLayer(id)) map.removeLayer(id);
  if (map.getSource(SOURCE_ID)) map.removeSource(SOURCE_ID);
  map.getCanvas().style.cursor = "";
}

export function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}
