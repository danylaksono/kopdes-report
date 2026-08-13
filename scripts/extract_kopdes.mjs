#!/usr/bin/env node
//
// extract_kopdes.mjs
// Reproducible extraction of Kopdes / Koperasi Desa Merah Putih locations,
// attributes and statistics from SIMKOPDES (https://simkopdes.go.id).
//
// Requirements: Node 18+ (uses global fetch). No external dependencies.
// Usage:        node extract_kopdes.mjs [outputDir]
// Env:          CONCURRENCY (default 12), PERIOD (default current year),
//               SKIP_VILLAGES=1 to skip the slow per-village pass.
//
// How it works
// ------------
// api.simkopdes.go.id answers with { message, data: "<base64>" } where data is
// AES-256-CBC ciphertext. The public web app decrypts it with
//   key = SHA256(secret)   iv = utf8Bytes(iv)
// and both of those plain strings ship inside the site JS bundle. Step 1 below
// re-reads them from the bundle at runtime, so nothing secret is hardcoded and
// the script keeps working if the values are rotated.
//
// Everything else is just two bulk endpoints plus a walk of the
// national-readiness hierarchy (province -> district -> subdistrict -> village).

import { createHash, createDecipheriv } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const NL = String.fromCharCode(10); // newline
const CR = String.fromCharCode(13); // carriage return

const SITE = "https://simkopdes.go.id";
const API = "https://api.simkopdes.go.id/api";
const OUT_DIR = process.argv[2] || "kopdes_export";
const CONCURRENCY = Number(process.env.CONCURRENCY || 12);
const PERIOD = process.env.PERIOD || String(new Date().getFullYear());

const log = (...args) => console.log("[kopdes]", ...args);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function retry(fn, tries = 4) {
  let lastError;
  for (let attempt = 0; attempt < tries; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastError = err;
      await sleep(400 * (attempt + 1));
    }
  }
  throw lastError;
}

async function pool(items, limit, worker, label) {
  const out = new Array(items.length);
  let next = 0;
  let done = 0;
  const runners = Array.from(
    { length: Math.min(limit, items.length) },
    async () => {
      while (next < items.length) {
        const index = next++;
        out[index] = await worker(items[index]);
        done++;
        if (label && done % 500 === 0) log(label, done + "/" + items.length);
      }
    },
  );
  await Promise.all(runners);
  return out;
}

// ---------------------------------------------------------------- 1. cipher
async function discoverCipher() {
  log("discovering cipher parameters from the public bundle...");
  const html = await (await fetch(SITE + "/pers/dashboard")).text();
  const chunks = [];
  for (const piece of html.split('"')) {
    if (
      piece.startsWith("/_next/static/chunks/") &&
      piece.endsWith(".js") &&
      !chunks.includes(piece)
    ) {
      chunks.push(piece);
    }
  }
  // the app calls  (0, x.C)(payload, "<secret>", "<iv>")  inside its decrRes helper
  const marker = ".C)(";
  for (const chunk of chunks) {
    const js = await (await fetch(SITE + chunk)).text();
    let at = js.indexOf(marker);
    while (at !== -1) {
      const parts = js
        .slice(at + marker.length, at + marker.length + 400)
        .split('"');
      const secret = parts[1];
      const iv = parts[3];
      if (secret && iv && iv.length === 16 && secret.length >= 16) {
        log("cipher parameters found in", chunk);
        return { secret, iv };
      }
      at = js.indexOf(marker, at + 1);
    }
  }
  throw new Error(
    "Could not locate the AES parameters in the SIMKOPDES bundle - the site build changed.",
  );
}

// ---------------------------------------------------------------- 2. client
function makeClient(cipher) {
  const key = createHash("sha256").update(cipher.secret, "utf8").digest();
  const iv = Buffer.from(cipher.iv, "utf8");
  return function get(endpoint) {
    return retry(async () => {
      const res = await fetch(API + endpoint, {
        headers: { accept: "application/json" },
      });
      if (!res.ok) throw new Error("HTTP " + res.status + " for " + endpoint);
      const body = await res.json();
      if (typeof body.data !== "string") return body.data;
      const decipher = createDecipheriv("aes-256-cbc", key, iv);
      const plain = Buffer.concat([
        decipher.update(Buffer.from(body.data, "base64")),
        decipher.final(),
      ]).toString("utf8");
      return JSON.parse(plain);
    });
  };
}

// ---------------------------------------------------------------- 3. csv
function csvCell(value) {
  if (value === null || value === undefined) return "";
  const s = String(value);
  if (s.includes(",") || s.includes('"') || s.includes(NL) || s.includes(CR)) {
    return '"' + s.split('"').join('""') + '"';
  }
  return s;
}

async function writeCsv(name, headers, rows) {
  const lines = [headers.join(",")];
  for (const row of rows)
    lines.push(headers.map((h) => csvCell(row[h])).join(","));
  await writeFile(path.join(OUT_DIR, name), lines.join(NL) + NL, "utf8");
  log("wrote", name, "(" + rows.length + " rows)");
}

// ---------------------------------------------------------------- 4. shapes
const STAT_COLS = [
  "cooperatives",
  "accounts_count",
  "npwp_count",
  "nib_count",
  "rat_count",
  "transaction_volume",
  "transaction_value",
  "simpanan_pokok_amount",
  "simpanan_pokok_members",
  "simpanan_pokok_tx",
  "simpanan_wajib_amount",
  "simpanan_wajib_members",
  "simpanan_wajib_tx",
  "savings_total_amount",
];

function stats(node) {
  const savings = node.savings_summary || {};
  const pokok = savings.simpanan_pokok || {};
  const wajib = savings.simpanan_wajib || {};
  return {
    cooperatives: node.count,
    accounts_count: node.accounts_count,
    npwp_count: node.npwp_count,
    nib_count: node.nib_count,
    rat_count: node.rat_count,
    transaction_volume: node.transaction_volume,
    transaction_value: node.transaction_value,
    simpanan_pokok_amount: pokok.total_amount,
    simpanan_pokok_members: pokok.total_members,
    simpanan_pokok_tx: pokok.total_transaction,
    simpanan_wajib_amount: wajib.total_amount,
    simpanan_wajib_members: wajib.total_members,
    simpanan_wajib_tx: wajib.total_transaction,
    savings_total_amount: savings.total_amount,
  };
}

// ---------------------------------------------------------------- 5. main
async function main() {
  await mkdir(OUT_DIR, { recursive: true });
  const get = makeClient(await discoverCipher());

  // A. every kopdes with its coordinates (one bulk call, ~83k records)
  log("fetching /cooperatives/get-all-nested ...");
  const nested = await get("/cooperatives/get-all-nested");
  const locations = [];
  for (const province of nested.grouped || []) {
    for (const district of province.districts || []) {
      for (const subdistrict of district.subdistricts || []) {
        for (const coop of subdistrict.cooperatives || []) {
          locations.push({
            cooperative_id: coop.cooperative_id,
            name: coop.name,
            province: province.province,
            district: district.district,
            subdistrict: subdistrict.subdistrict,
            latitude: coop.latitude,
            longitude: coop.longitude,
          });
        }
      }
    }
  }
  await writeCsv(
    "kopdes_locations.csv",
    [
      "cooperative_id",
      "name",
      "province",
      "district",
      "subdistrict",
      "latitude",
      "longitude",
    ],
    locations,
  );

  // B. surveyed land / asset points (one bulk call, ~66k records)
  log("fetching /cooperative-assets/get-all ...");
  const assetTree = await get("/cooperative-assets/get-all");
  const assetRows = [];
  for (const [province, pNode] of Object.entries(assetTree.grouped || {})) {
    for (const [district, dNode] of Object.entries(pNode.districts || {})) {
      for (const [subdistrict, sNode] of Object.entries(
        dNode.subdistricts || {},
      )) {
        for (const [village, vNode] of Object.entries(sNode.villages || {})) {
          for (const asset of vNode.assets || []) {
            assetRows.push({
              asset_id: asset.asset_id,
              cooperative: asset.cooperative,
              province,
              district,
              subdistrict,
              village,
              status: asset.status,
              surveyor: asset.surveyor,
              latitude: asset.latitude,
              longitude: asset.longitude,
            });
          }
        }
      }
    }
  }
  await writeCsv(
    "kopdes_land_assets.csv",
    [
      "asset_id",
      "cooperative",
      "province",
      "district",
      "subdistrict",
      "village",
      "status",
      "surveyor",
      "latitude",
      "longitude",
    ],
    assetRows,
  );

  // C. province level statistics + centroid + health
  log("fetching national and province level statistics ...");
  const nationalStats = await get(
    "/statistics/national-readiness/cooperative-stats?period=" + PERIOD,
  );
  const healthMap = await get("/cooperative-financial/statistics/national/map");
  const consolidation = await get("/statistics/dashboard-consolidation");

  const coordByProvince = {};
  for (const item of healthMap.cooperatives || [])
    coordByProvince[item.province_id] = item;
  const healthByProvince = {};
  for (const item of (consolidation.maps_economic_impact_card || {}).maps || [])
    healthByProvince[item.province_id] = item;

  const provinceRows = (nationalStats.nested_data.grouped || []).map((p) => {
    const coord = coordByProvince[p.province_id] || {};
    const health = healthByProvince[p.province_id] || {};
    return {
      province_id: p.province_id,
      province: p.province,
      latitude: coord.latitude,
      longitude: coord.longitude,
      ...stats(p),
      health_score: coord.health_score,
      health_status: coord.health_status,
      health_total_cooperative: health.total_cooperative,
      healthy_count: health.healthy_count,
      fairly_healthy_count: health.fairly_healthy_count,
      unhealthy_count: health.unhealthy_count,
      average_health_index: health.average_health_index,
    };
  });
  await writeCsv(
    "kopdes_stats_province.csv",
    [
      "province_id",
      "province",
      "latitude",
      "longitude",
      ...STAT_COLS,
      "health_score",
      "health_status",
      "health_total_cooperative",
      "healthy_count",
      "fairly_healthy_count",
      "unhealthy_count",
      "average_health_index",
    ],
    provinceRows,
  );

  // D. district level (38 calls)
  const provinceDetails = await pool(
    provinceRows.map((r) => r.province_id),
    CONCURRENCY,
    (id) => get("/statistics/national-readiness/province/" + id),
    "provinces",
  );
  const districtRows = [];
  for (const detail of provinceDetails) {
    const td = detail && detail.territorial_data;
    if (!td) continue;
    for (const d of td.districts || []) {
      districtRows.push({
        province_id: td.province_id,
        province: td.province,
        district_id: d.district_id,
        district: d.district,
        ...stats(d),
      });
    }
  }
  await writeCsv(
    "kopdes_stats_district.csv",
    ["province_id", "province", "district_id", "district", ...STAT_COLS],
    districtRows,
  );

  // E. subdistrict level (~525 calls)
  const districtDetails = await pool(
    districtRows.map((r) => r.district_id),
    CONCURRENCY,
    (id) => get("/statistics/national-readiness/district/" + id),
    "districts",
  );
  const subdistrictRows = [];
  for (const detail of districtDetails) {
    const td = detail && detail.territorial_data;
    if (!td) continue;
    for (const s of td.subdistricts || []) {
      subdistrictRows.push({
        province_id: td.province_id,
        province: td.province,
        district_id: td.district_id,
        district: td.district,
        subdistrict_id: s.subdistrict_id,
        subdistrict: s.subdistrict,
        ...stats(s),
      });
    }
  }
  await writeCsv(
    "kopdes_stats_subdistrict.csv",
    [
      "province_id",
      "province",
      "district_id",
      "district",
      "subdistrict_id",
      "subdistrict",
      ...STAT_COLS,
    ],
    subdistrictRows,
  );

  // F. village level = effectively one row per kopdes (~7.4k calls, a few minutes)
  if (process.env.SKIP_VILLAGES !== "1") {
    const subdistrictDetails = await pool(
      subdistrictRows.map((r) => r.subdistrict_id),
      CONCURRENCY,
      (id) => get("/statistics/national-readiness/subdistrict/" + id),
      "subdistricts",
    );
    const villageRows = [];
    for (const detail of subdistrictDetails) {
      const td = detail && detail.territorial_data;
      if (!td) continue;
      for (const v of td.villages || []) {
        villageRows.push({
          province_id: td.province_id,
          province: td.province,
          district_id: td.district_id,
          district: td.district,
          subdistrict_id: td.subdistrict_id,
          subdistrict: td.subdistrict,
          village_id: v.village_id,
          village: v.village,
          ...stats(v),
        });
      }
    }
    await writeCsv(
      "kopdes_stats_village.csv",
      [
        "province_id",
        "province",
        "district_id",
        "district",
        "subdistrict_id",
        "subdistrict",
        "village_id",
        "village",
        ...STAT_COLS,
      ],
      villageRows,
    );
  } else {
    log("SKIP_VILLAGES=1 - skipping the per-village pass");
  }

  // G. per province RAT status, construction progress, top products
  const provinceNameById = {};
  for (const row of provinceRows)
    provinceNameById[row.province_id] = row.province;
  const ratRows = [];
  const productRows = [];
  provinceDetails.forEach((detail, index) => {
    if (!detail) return;
    const provinceId = provinceRows[index].province_id;
    const provinceName = provinceNameById[provinceId];
    const rat = detail.rat_summary || {};
    const readiness = {};
    for (const item of detail.store_readiness || [])
      readiness[item.label] = item.value;
    const economic = detail.economic_impact || {};
    ratRows.push({
      province_id: provinceId,
      province: provinceName,
      rat_period: rat.period,
      total_rat: rat.total_rat,
      total_done_rat: rat.total_done_rat,
      total_verified_rat: rat.total_verified_rat,
      total_draft_rat: rat.total_draft_rat,
      total_no_rat: rat.total_no_rat,
      build_upto_20: readiness["Total Pembangunan hingga 20%"],
      build_21_50: readiness["Total Pembangunan 21% - 50%"],
      build_51_75: readiness["Total Pembangunan 51% - 75%"],
      build_76_99: readiness["Total Pembangunan 76% - 99%"],
      build_100: readiness["Total Pembangunan 100%"],
      economic_total_volume: economic.total_volume,
      economic_total_value: economic.total_value,
      updated_at: detail.updated_at,
    });
    for (const product of economic.rows || []) {
      productRows.push({
        province_id: provinceId,
        province: provinceName,
        product: product.product,
        volume: product.volume,
        value: product.value,
      });
    }
  });
  await writeCsv(
    "kopdes_province_rat_and_construction.csv",
    [
      "province_id",
      "province",
      "rat_period",
      "total_rat",
      "total_done_rat",
      "total_verified_rat",
      "total_draft_rat",
      "total_no_rat",
      "build_upto_20",
      "build_21_50",
      "build_51_75",
      "build_76_99",
      "build_100",
      "economic_total_volume",
      "economic_total_value",
      "updated_at",
    ],
    ratRows,
  );
  await writeCsv(
    "kopdes_province_top_products.csv",
    ["province_id", "province", "product", "volume", "value"],
    productRows,
  );

  // H. national headline numbers
  const landingSummary = await get("/cooperatives/landing-summary");
  const landMapping = await get("/statistics/land-mapping");
  const coopStats = nationalStats.cooperative_stats || {};
  const nationalRows = [
    { metric: "total_cooperatives", value: coopStats.total },
    { metric: "total_legal_entity", value: coopStats.total_legal },
    { metric: "with_account", value: coopStats.total_with_account },
    { metric: "with_npwp", value: coopStats.total_with_npwp },
    { metric: "with_nib", value: coopStats.total_with_nib },
    { metric: "stats_updated_at", value: coopStats.updated_at },
  ];
  for (const [k, v] of Object.entries(landingSummary || {}))
    nationalRows.push({ metric: "landing_" + k, value: v });
  for (const [k, v] of Object.entries((landMapping || {}).data || {}))
    nationalRows.push({ metric: "land_" + k, value: v });
  // The dashboard's headline numbers come from nested_data.totals (rat_count,
  // transaction_value), NOT landing-summary; the two diverge. Record both so
  // every snapshot can detect the divergence (see scripts/extract_kopdes.py).
  const nestedTotals = (nationalStats.nested_data || {}).totals || {};
  for (const k of [
    "count",
    "accounts_count",
    "npwp_count",
    "nib_count",
    "rat_count",
    "transaction_volume",
    "transaction_value",
    "generated_at",
  ]) {
    if (k in nestedTotals)
      nationalRows.push({ metric: "nested_" + k, value: nestedTotals[k] });
  }
  for (const item of nationalStats.store_readiness || []) {
    if (item.label)
      nationalRows.push({
        metric: "readiness_" + item.label,
        value: item.value,
      });
  }
  await writeCsv(
    "kopdes_national_summary.csv",
    ["metric", "value"],
    nationalRows,
  );

  log("done - files are in", path.resolve(OUT_DIR));
}

main().catch((err) => {
  console.error("[kopdes] failed:", err);
  process.exit(1);
});
