/**
 * search.js — find a cooperative or an area by name.
 *
 * The index is built once from the rows already in memory, so searching costs
 * no extra fetch and works offline of the mart. 83.379 cooperatives plus ~7.800
 * administrative names is small enough to scan linearly per keystroke; the one
 * thing that matters for that to stay true is that the lowercased name is
 * precomputed, because lowercasing 83.000 strings on every keystroke is not.
 *
 * Ranking is deliberately simple and explainable: exact name, then prefix, then
 * word-start, then anywhere. Administrative areas outrank cooperatives at equal
 * quality — someone typing "Wonosari" more often wants the kecamatan than one
 * of the cooperatives inside it, and the cooperative is one rung further down
 * the ladder anyway.
 */

const KIND_RANK = { provinsi: 0, kabupaten: 1, kecamatan: 2, koperasi: 3 };

const norm = (s) =>
  String(s ?? "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();

/**
 * Build the searchable index.
 *
 * Administrative entries are derived from the points rather than from the
 * aggregate tables, so search works the moment the points land and does not
 * wait on three more queries. The coordinate is the mean of the area's member
 * cooperatives, which is close enough to fly to; the exact anchor comes from
 * the aggregate row once that level loads.
 */
export function buildIndex(rows) {
  const entries = [];
  const areas = new Map(); // key -> accumulator

  const addArea = (kind, id, name, parent, lon, lat) => {
    if (id == null || !name) return;
    const key = `${kind}:${id}`;
    let a = areas.get(key);
    if (!a) {
      a = { kind, id, name, parent, lon: 0, lat: 0, n: 0 };
      areas.set(key, a);
    }
    a.lon += lon;
    a.lat += lat;
    a.n++;
  };

  for (const r of rows) {
    // Impossible coordinates would drag an area's mean into the ocean, and the
    // search result would fly somewhere that is not the place you asked for.
    if (r.coordinate_suspect === true) continue;
    entries.push({
      kind: "koperasi",
      id: r.cooperative_id,
      name: r.cooperative,
      nameLower: norm(r.cooperative),
      parent: [r.subdistrict, r.district].filter(Boolean).join(", "),
      lon: r.longitude,
      lat: r.latitude,
      row: r,
    });
    addArea("provinsi", r.province_id, r.province, "", r.longitude, r.latitude);
    addArea(
      "kabupaten",
      r.district_id,
      r.district,
      r.province,
      r.longitude,
      r.latitude,
    );
    addArea(
      "kecamatan",
      r.subdistrict_id,
      r.subdistrict,
      r.district,
      r.longitude,
      r.latitude,
    );
  }

  for (const a of areas.values()) {
    entries.push({
      kind: a.kind,
      id: a.id,
      name: a.name,
      nameLower: norm(a.name),
      parent: a.parent,
      lon: a.lon / a.n,
      lat: a.lat / a.n,
      count: a.n,
    });
  }

  return entries;
}

/** 0 = no match; higher is better. */
function score(entry, q) {
  const name = entry.nameLower;
  if (name === q) return 100;
  if (name.startsWith(q)) return 80;
  const at = name.indexOf(q);
  if (at < 0) return 0;
  // A match at a word boundary reads as intentional; one mid-word is usually
  // incidental ("sari" inside "Pasarkemis").
  return name[at - 1] === " " ? 60 : 30;
}

export function search(index, query, limit = 12) {
  const q = norm(query);
  if (q.length < 2) return [];

  const hits = [];
  for (const entry of index) {
    const s = score(entry, q);
    if (s) hits.push({ entry, score: s });
  }

  hits.sort(
    (a, b) =>
      b.score - a.score ||
      KIND_RANK[a.entry.kind] - KIND_RANK[b.entry.kind] ||
      (b.entry.count ?? 0) - (a.entry.count ?? 0) ||
      a.entry.name.length - b.entry.name.length,
  );

  return hits.slice(0, limit).map((h) => h.entry);
}
