#!/usr/bin/env python3
"""
extract_kopdes.py

Reproducible extraction of Kopdes / Koperasi Desa Merah Putih locations,
attributes and statistics from SIMKOPDES (https://simkopdes.go.id).

Install:  pip install requests pycryptodome      (or: pip install requests cryptography)
Usage:    python extract_kopdes.py [output_dir]
Env:      CONCURRENCY (default 12), PERIOD (default current year),
          SKIP_VILLAGES=1 to skip the slow per-village pass.

How it works
------------
api.simkopdes.go.id answers with {"message": ..., "data": "<base64>"} where
data is AES-256-CBC ciphertext. The public web app decrypts it with
    key = SHA256(secret)      iv = utf8_bytes(iv)
and both plain strings ship inside the site JS bundle. Step 1 re-reads them from
the bundle at runtime, so no secret is hardcoded here and the script keeps
working if the values are rotated.

Everything else is two bulk endpoints plus a walk of the national-readiness
hierarchy: province -> district -> subdistrict -> village.
"""

import base64
import csv
import hashlib
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import requests

try:
    from Crypto.Cipher import AES  # pycryptodome

    def aes_cbc_decrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
        return AES.new(key, AES.MODE_CBC, iv).decrypt(data)

except ImportError:  # fall back to the cryptography package
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    def aes_cbc_decrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
        decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        return decryptor.update(data) + decryptor.finalize()


SITE = "https://simkopdes.go.id"
API = "https://api.simkopdes.go.id/api"
OUT_DIR = Path(sys.argv[1] if len(sys.argv) > 1 else "kopdes_export")
CONCURRENCY = int(os.environ.get("CONCURRENCY", "12"))
PERIOD = os.environ.get("PERIOD", str(date.today().year))
SKIP_VILLAGES = os.environ.get("SKIP_VILLAGES") == "1"

STAT_COLS = [
    "cooperatives", "accounts_count", "npwp_count", "nib_count", "rat_count",
    "transaction_volume", "transaction_value",
    "simpanan_pokok_amount", "simpanan_pokok_members", "simpanan_pokok_tx",
    "simpanan_wajib_amount", "simpanan_wajib_members", "simpanan_wajib_tx",
    "savings_total_amount",
]

_local = threading.local()


def log(*args):
    print("[kopdes]", *args, flush=True)


def session() -> requests.Session:
    if not hasattr(_local, "s"):
        _local.s = requests.Session()
        _local.s.headers.update({"accept": "application/json"})
    return _local.s


def pkcs7_unpad(data: bytes) -> bytes:
    if not data:
        return data
    pad = data[-1]
    return data[:-pad] if 0 < pad <= 16 else data


# ------------------------------------------------------------------ 1. cipher
def discover_cipher():
    log("discovering cipher parameters from the public bundle...")
    html = session().get(SITE + "/pers/dashboard", timeout=60).text
    chunks = []
    for piece in html.split('"'):
        if piece.startswith("/_next/static/chunks/") and piece.endswith(".js") and piece not in chunks:
            chunks.append(piece)
    marker = ".C)("  # the app calls (0, x.C)(payload, "<secret>", "<iv>") in decrRes
    for chunk in chunks:
        js = session().get(SITE + chunk, timeout=60).text
        at = js.find(marker)
        while at != -1:
            parts = js[at + len(marker): at + len(marker) + 400].split('"')
            if len(parts) >= 4:
                secret, iv = parts[1], parts[3]
                if len(iv) == 16 and len(secret) >= 16:
                    log("cipher parameters found in", chunk)
                    return secret, iv
            at = js.find(marker, at + 1)
    raise RuntimeError("Could not locate the AES parameters in the SIMKOPDES bundle - the site build changed.")


# ------------------------------------------------------------------ 2. client
class Client:
    def __init__(self, secret: str, iv: str):
        self.key = hashlib.sha256(secret.encode("utf-8")).digest()
        self.iv = iv.encode("utf-8")

    def get(self, endpoint: str, tries: int = 4):
        last = None
        for attempt in range(tries):
            try:
                res = session().get(API + endpoint, timeout=180)
                res.raise_for_status()
                body = res.json()
                data = body.get("data")
                if not isinstance(data, str):
                    return data
                raw = base64.b64decode("".join(data.split()))
                plain = pkcs7_unpad(aes_cbc_decrypt(self.key, self.iv, raw))
                import json
                return json.loads(plain.decode("utf-8"))
            except Exception as exc:  # noqa: BLE001
                last = exc
                time.sleep(0.4 * (attempt + 1))
        raise RuntimeError("failed " + endpoint + ": " + str(last))


def pool(items, worker, label=None):
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool_exec:
        results = []
        for index, value in enumerate(pool_exec.map(worker, items), start=1):
            results.append(value)
            if label and index % 500 == 0:
                log(label, str(index) + "/" + str(len(items)))
        return results


# ------------------------------------------------------------------ 3. output
def write_csv(name, headers, rows):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / name, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in headers})
    log("wrote", name, "(" + str(len(rows)) + " rows)")


def stats(node):
    savings = node.get("savings_summary") or {}
    pokok = savings.get("simpanan_pokok") or {}
    wajib = savings.get("simpanan_wajib") or {}
    return {
        "cooperatives": node.get("count"),
        "accounts_count": node.get("accounts_count"),
        "npwp_count": node.get("npwp_count"),
        "nib_count": node.get("nib_count"),
        "rat_count": node.get("rat_count"),
        "transaction_volume": node.get("transaction_volume"),
        "transaction_value": node.get("transaction_value"),
        "simpanan_pokok_amount": pokok.get("total_amount"),
        "simpanan_pokok_members": pokok.get("total_members"),
        "simpanan_pokok_tx": pokok.get("total_transaction"),
        "simpanan_wajib_amount": wajib.get("total_amount"),
        "simpanan_wajib_members": wajib.get("total_members"),
        "simpanan_wajib_tx": wajib.get("total_transaction"),
        "savings_total_amount": savings.get("total_amount"),
    }


# ------------------------------------------------------------------ 4. main
def main():
    secret, iv = discover_cipher()
    api = Client(secret, iv)

    # A. every kopdes with its coordinates (one bulk call, ~83k records)
    log("fetching /cooperatives/get-all-nested ...")
    nested = api.get("/cooperatives/get-all-nested")
    locations = []
    for province in nested.get("grouped") or []:
        for district in province.get("districts") or []:
            for subdistrict in district.get("subdistricts") or []:
                for coop in subdistrict.get("cooperatives") or []:
                    locations.append({
                        "cooperative_id": coop.get("cooperative_id"),
                        "name": coop.get("name"),
                        "province": province.get("province"),
                        "district": district.get("district"),
                        "subdistrict": subdistrict.get("subdistrict"),
                        "latitude": coop.get("latitude"),
                        "longitude": coop.get("longitude"),
                    })
    write_csv("kopdes_locations.csv",
              ["cooperative_id", "name", "province", "district", "subdistrict", "latitude", "longitude"],
              locations)

    # B. surveyed land / asset points (one bulk call, ~66k records)
    log("fetching /cooperative-assets/get-all ...")
    asset_tree = api.get("/cooperative-assets/get-all")
    asset_rows = []
    for province, p_node in (asset_tree.get("grouped") or {}).items():
        for district, d_node in (p_node.get("districts") or {}).items():
            for subdistrict, s_node in (d_node.get("subdistricts") or {}).items():
                for village, v_node in (s_node.get("villages") or {}).items():
                    for asset in v_node.get("assets") or []:
                        asset_rows.append({
                            "asset_id": asset.get("asset_id"),
                            "cooperative": asset.get("cooperative"),
                            "province": province,
                            "district": district,
                            "subdistrict": subdistrict,
                            "village": village,
                            "status": asset.get("status"),
                            "surveyor": asset.get("surveyor"),
                            "latitude": asset.get("latitude"),
                            "longitude": asset.get("longitude"),
                        })
    write_csv("kopdes_land_assets.csv",
              ["asset_id", "cooperative", "province", "district", "subdistrict", "village",
               "status", "surveyor", "latitude", "longitude"],
              asset_rows)

    # C. province level statistics + centroid + health
    log("fetching national and province level statistics ...")
    national = api.get("/statistics/national-readiness/cooperative-stats?period=" + PERIOD)
    health_map = api.get("/cooperative-financial/statistics/national/map")
    consolidation = api.get("/statistics/dashboard-consolidation")

    coord_by_province = {item.get("province_id"): item for item in health_map.get("cooperatives") or []}
    health_by_province = {item.get("province_id"): item
                          for item in (consolidation.get("maps_economic_impact_card") or {}).get("maps") or []}

    province_rows = []
    for p in national["nested_data"].get("grouped") or []:
        coord = coord_by_province.get(p.get("province_id")) or {}
        health = health_by_province.get(p.get("province_id")) or {}
        row = {
            "province_id": p.get("province_id"),
            "province": p.get("province"),
            "latitude": coord.get("latitude"),
            "longitude": coord.get("longitude"),
        }
        row.update(stats(p))
        row.update({
            "health_score": coord.get("health_score"),
            "health_status": coord.get("health_status"),
            "health_total_cooperative": health.get("total_cooperative"),
            "healthy_count": health.get("healthy_count"),
            "fairly_healthy_count": health.get("fairly_healthy_count"),
            "unhealthy_count": health.get("unhealthy_count"),
            "average_health_index": health.get("average_health_index"),
        })
        province_rows.append(row)
    write_csv("kopdes_stats_province.csv",
              ["province_id", "province", "latitude", "longitude"] + STAT_COLS +
              ["health_score", "health_status", "health_total_cooperative", "healthy_count",
               "fairly_healthy_count", "unhealthy_count", "average_health_index"],
              province_rows)

    # D. district level (38 calls)
    province_ids = [row["province_id"] for row in province_rows]
    province_details = pool(province_ids,
                            lambda pid: api.get("/statistics/national-readiness/province/" + str(pid)),
                            "provinces")
    district_rows = []
    for detail in province_details:
        td = (detail or {}).get("territorial_data")
        if not td:
            continue
        for d in td.get("districts") or []:
            row = {"province_id": td.get("province_id"), "province": td.get("province"),
                   "district_id": d.get("district_id"), "district": d.get("district")}
            row.update(stats(d))
            district_rows.append(row)
    write_csv("kopdes_stats_district.csv",
              ["province_id", "province", "district_id", "district"] + STAT_COLS, district_rows)

    # E. subdistrict level (~525 calls)
    district_details = pool([row["district_id"] for row in district_rows],
                            lambda did: api.get("/statistics/national-readiness/district/" + str(did)),
                            "districts")
    subdistrict_rows = []
    for detail in district_details:
        td = (detail or {}).get("territorial_data")
        if not td:
            continue
        for s in td.get("subdistricts") or []:
            row = {"province_id": td.get("province_id"), "province": td.get("province"),
                   "district_id": td.get("district_id"), "district": td.get("district"),
                   "subdistrict_id": s.get("subdistrict_id"), "subdistrict": s.get("subdistrict")}
            row.update(stats(s))
            subdistrict_rows.append(row)
    write_csv("kopdes_stats_subdistrict.csv",
              ["province_id", "province", "district_id", "district", "subdistrict_id", "subdistrict"] + STAT_COLS,
              subdistrict_rows)

    # F. village level = effectively one row per kopdes (~7.4k calls, a few minutes)
    if SKIP_VILLAGES:
        log("SKIP_VILLAGES=1 - skipping the per-village pass")
    else:
        subdistrict_details = pool([row["subdistrict_id"] for row in subdistrict_rows],
                                   lambda sid: api.get("/statistics/national-readiness/subdistrict/" + str(sid)),
                                   "subdistricts")
        village_rows = []
        for detail in subdistrict_details:
            td = (detail or {}).get("territorial_data")
            if not td:
                continue
            for v in td.get("villages") or []:
                row = {"province_id": td.get("province_id"), "province": td.get("province"),
                       "district_id": td.get("district_id"), "district": td.get("district"),
                       "subdistrict_id": td.get("subdistrict_id"), "subdistrict": td.get("subdistrict"),
                       "village_id": v.get("village_id"), "village": v.get("village")}
                row.update(stats(v))
                village_rows.append(row)
        write_csv("kopdes_stats_village.csv",
                  ["province_id", "province", "district_id", "district", "subdistrict_id", "subdistrict",
                   "village_id", "village"] + STAT_COLS,
                  village_rows)

    # G. per province RAT status, construction progress, top products
    rat_rows = []
    product_rows = []
    for index, detail in enumerate(province_details):
        if not detail:
            continue
        province_id = province_rows[index]["province_id"]
        province_name = province_rows[index]["province"]
        rat = detail.get("rat_summary") or {}
        readiness = {item.get("label"): item.get("value") for item in detail.get("store_readiness") or []}
        economic = detail.get("economic_impact") or {}
        rat_rows.append({
            "province_id": province_id,
            "province": province_name,
            "rat_period": rat.get("period"),
            "total_rat": rat.get("total_rat"),
            "total_done_rat": rat.get("total_done_rat"),
            "total_verified_rat": rat.get("total_verified_rat"),
            "total_draft_rat": rat.get("total_draft_rat"),
            "total_no_rat": rat.get("total_no_rat"),
            "build_upto_20": readiness.get("Total Pembangunan hingga 20%"),
            "build_21_50": readiness.get("Total Pembangunan 21% - 50%"),
            "build_51_75": readiness.get("Total Pembangunan 51% - 75%"),
            "build_76_99": readiness.get("Total Pembangunan 76% - 99%"),
            "build_100": readiness.get("Total Pembangunan 100%"),
            "economic_total_volume": economic.get("total_volume"),
            "economic_total_value": economic.get("total_value"),
            "updated_at": detail.get("updated_at"),
        })
        for product in economic.get("rows") or []:
            product_rows.append({
                "province_id": province_id,
                "province": province_name,
                "product": product.get("product"),
                "volume": product.get("volume"),
                "value": product.get("value"),
            })
    write_csv("kopdes_province_rat_and_construction.csv",
              ["province_id", "province", "rat_period", "total_rat", "total_done_rat", "total_verified_rat",
               "total_draft_rat", "total_no_rat", "build_upto_20", "build_21_50", "build_51_75",
               "build_76_99", "build_100", "economic_total_volume", "economic_total_value", "updated_at"],
              rat_rows)
    write_csv("kopdes_province_top_products.csv",
              ["province_id", "province", "product", "volume", "value"], product_rows)

    # H. national headline numbers
    landing = api.get("/cooperatives/landing-summary") or {}
    land = api.get("/statistics/land-mapping") or {}
    coop_stats = national.get("cooperative_stats") or {}
    national_rows = [
        {"metric": "total_cooperatives", "value": coop_stats.get("total")},
        {"metric": "total_legal_entity", "value": coop_stats.get("total_legal")},
        {"metric": "with_account", "value": coop_stats.get("total_with_account")},
        {"metric": "with_npwp", "value": coop_stats.get("total_with_npwp")},
        {"metric": "with_nib", "value": coop_stats.get("total_with_nib")},
        {"metric": "stats_updated_at", "value": coop_stats.get("updated_at")},
    ]
    for key, value in landing.items():
        national_rows.append({"metric": "landing_" + key, "value": value})
    for key, value in (land.get("data") or {}).items():
        national_rows.append({"metric": "land_" + key, "value": value})
    write_csv("kopdes_national_summary.csv", ["metric", "value"], national_rows)

    log("done - files are in", OUT_DIR.resolve())


if __name__ == "__main__":
    main()
