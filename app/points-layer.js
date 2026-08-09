const VERIFIED_COLORS = {
  verified: "#2e9e5b",
  not_verified: "#e0a13d",
  no_record: "#9aa0a6",
};

const VERIFIED_LABELS = {
  verified: "Verified",
  not_verified: "Not verified",
  no_record: "No asset record",
};

const map = new maplibregl.Map({
  container: "map",
  style: "https://tiles.openfreemap.org/styles/positron",
  center: [117.5, -2.5], // roughly the middle of Indonesia
  zoom: 4.2,
});

map.addControl(new maplibregl.NavigationControl(), "top-right");

const info = document.getElementById("info");

map.on("load", async () => {
  const res = await fetch("data/points.geojson");
  const data = await res.json();

  map.addSource("kopdes", {
    type: "geojson",
    data,
    cluster: true,
    clusterMaxZoom: 12,
    clusterRadius: 45,
  });

  map.addLayer({
    id: "clusters",
    type: "circle",
    source: "kopdes",
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
    source: "kopdes",
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
    source: "kopdes",
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

  info.textContent = `Kopdes Merah Putih cooperatives — ${data.features.length.toLocaleString()} points`;

  map.on("click", "clusters", (e) => {
    const [feature] = map.queryRenderedFeatures(e.point, { layers: ["clusters"] });
    const clusterId = feature.properties.cluster_id;
    map.getSource("kopdes").getClusterExpansionZoom(clusterId, (err, zoom) => {
      if (err) return;
      map.easeTo({ center: feature.geometry.coordinates, zoom });
    });
  });

  map.on("click", "unclustered-point", (e) => {
    const feature = e.features[0];
    const { name, province, district, subdistrict, verified, asset_status } = feature.properties;
    const statusLine = asset_status
      ? `${escapeHtml(VERIFIED_LABELS[verified])} (${escapeHtml(asset_status)})`
      : escapeHtml(VERIFIED_LABELS[verified]);
    new maplibregl.Popup()
      .setLngLat(feature.geometry.coordinates)
      .setHTML(
        `<b>${escapeHtml(name)}</b><br>${escapeHtml(subdistrict)}, ${escapeHtml(district)}<br>${escapeHtml(province)}` +
          `<br><span style="color:${VERIFIED_COLORS[verified]}">&#9679;</span> ${statusLine}`
      )
      .addTo(map);
  });

  for (const layer of ["clusters", "unclustered-point"]) {
    map.on("mouseenter", layer, () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", layer, () => (map.getCanvas().style.cursor = ""));
  }
});

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}
