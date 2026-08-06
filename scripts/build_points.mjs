#!/usr/bin/env node
/**
 * build_points.mjs
 *
 * Converts data/raw/kopdes_locations.csv (cooperative_id, name, province,
 * district, subdistrict, latitude, longitude) into a Point FeatureCollection
 * for the web viewer: web/data/points.geojson.
 *
 * Rows with missing/non-numeric coordinates, or coordinates far outside
 * Indonesia's bounding box (a sign of bad/placeholder data in the SIMKOPDES
 * export - see geo/README.md's "Known match gaps" for other examples of the
 * same issue), are skipped and counted rather than plotted.
 *
 * Verification status is joined in from data/raw/kopdes_land_assets.csv,
 * which carries a per-asset "status" field (Terverifikasi / Sedang
 * Diverifikasi / Tidak Ada Lahan / ...) keyed by cooperative *name* - there's
 * no shared id between the two exports. The join matches on exact
 * (normalized) name, which resolves 65,895 of 65,921 land-asset names
 * (99.96%) against kopdes_locations.csv, so no fuzzy matching is used here
 * (unlike geo/link_kopdes.py's admin-boundary join, which needs it). Each
 * point gets:
 *   - asset_status: the raw SIMKOPDES status string, or null if the
 *     cooperative has no land-asset record at all
 *   - verified: "verified" (status === "Terverifikasi"), "not_verified"
 *     (any other known status), or "no_record" (no matching asset row)
 *
 * Usage: node scripts/build_points.mjs
 */

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const LOCATIONS_PATH = path.join(ROOT, "data", "raw", "kopdes_locations.csv");
const LAND_ASSETS_PATH = path.join(ROOT, "data", "raw", "kopdes_land_assets.csv");
const OUT_PATH = path.join(ROOT, "web", "data", "points.geojson");

// Loose bounding box around Indonesia (incl. EEZ margin), used only to
// flag obviously-wrong coordinates (e.g. 0,0 or another country entirely).
const BBOX = { minLat: -11.5, maxLat: 6.5, minLon: 94.5, maxLon: 141.5 };

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        field += c;
      }
    } else if (c === '"') {
      inQuotes = true;
    } else if (c === ",") {
      row.push(field);
      field = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += c;
    }
  }
  if (field.length > 0 || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  return rows.filter((r) => r.length > 1 || r[0] !== "");
}

function loadAssetStatusByName(csvPath) {
  const rows = parseCsv(readFileSync(csvPath, "utf-8"));
  const header = rows[0];
  const idx = Object.fromEntries(header.map((h, i) => [h, i]));
  const byName = new Map();
  for (const r of rows.slice(1)) {
    byName.set(r[idx.cooperative], r[idx.status]);
  }
  return byName;
}

function classifyVerified(status) {
  if (status === undefined) return "no_record";
  return status === "Terverifikasi" ? "verified" : "not_verified";
}

function main() {
  const assetStatusByName = loadAssetStatusByName(LAND_ASSETS_PATH);

  const rows = parseCsv(readFileSync(LOCATIONS_PATH, "utf-8"));
  const header = rows[0];
  const idx = Object.fromEntries(header.map((h, i) => [h, i]));

  const features = [];
  let skippedBadCoords = 0;
  const verifiedCounts = { verified: 0, not_verified: 0, no_record: 0 };

  for (const r of rows.slice(1)) {
    const lat = parseFloat(r[idx.latitude]);
    const lon = parseFloat(r[idx.longitude]);
    const valid =
      Number.isFinite(lat) &&
      Number.isFinite(lon) &&
      lat >= BBOX.minLat &&
      lat <= BBOX.maxLat &&
      lon >= BBOX.minLon &&
      lon <= BBOX.maxLon;

    if (!valid) {
      skippedBadCoords++;
      continue;
    }

    const name = r[idx.name];
    const assetStatus = assetStatusByName.get(name) ?? null;
    const verified = classifyVerified(assetStatusByName.get(name));
    verifiedCounts[verified]++;

    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [lon, lat] },
      properties: {
        id: r[idx.cooperative_id],
        name,
        province: r[idx.province],
        district: r[idx.district],
        subdistrict: r[idx.subdistrict],
        asset_status: assetStatus,
        verified,
      },
    });
  }

  const fc = { type: "FeatureCollection", features };

  mkdirSync(path.dirname(OUT_PATH), { recursive: true });
  writeFileSync(OUT_PATH, JSON.stringify(fc));

  console.log(
    `[build_points] wrote ${features.length} points to ${path.relative(ROOT, OUT_PATH)} ` +
      `(skipped ${skippedBadCoords} rows with missing/out-of-bounds coordinates)`
  );
  console.log(
    `[build_points] verified=${verifiedCounts.verified} not_verified=${verifiedCounts.not_verified} ` +
      `no_record=${verifiedCounts.no_record}`
  );
}

main();
