#!/usr/bin/env python3
"""
link_kopdes.py

Joins kopdes_stats_<level>.csv onto the BIG boundary GeoJSON for the same
level (geo/geojson/<level>.geojson), matching on normalized administrative
names (province -> district -> subdistrict -> village) since the kopdes
export uses SIMKOPDES's own internal ids, not BPS/Kemendagri codes.

Matching resolves one level at a time, coarsest to finest (province, then
district, then subdistrict, then village for kel_desa). At each level it
first tries an exact match on the normalized name *within the parent scope
already resolved*, and falls back to a fuzzy match (difflib, cutoff 0.82)
against only the candidates sharing that resolved parent if the exact match
fails. This catches spelling variants at any level - not just the finest one
- without ever matching across the wrong province/district/subdistrict. It's
needed because the BIG shapefiles have their own typos too (e.g. "Johan
Pahwalan" for "Johan Pahlawan" in Kab. Aceh Barat's kecamatan layer), which
would otherwise silently fail every village underneath that one subdistrict.

Every kopdes row that matches has its stat columns merged into the matched
GeoJSON feature's properties. GeoJSON features with no matching kopdes row
are kept (properties left as-is) so the output boundary set stays complete
for mapping. Unmatched kopdes rows and a summary are written to geo/output/.

Usage: python link_kopdes.py [level ...]
       (levels: provinsi kab_kota kecamatan kel_desa; default: all four)
"""

import csv
import difflib
import json
import sys
from pathlib import Path

from name_utils import normalize_name

ROOT = Path(__file__).parent
GEOJSON_DIR = ROOT / "geojson"
OUT_DIR = ROOT / "output"
DATA_DIR = ROOT.parent / "data" / "raw"

FUZZY_CUTOFF = 0.82

# level key -> (kopdes csv filename, [(csv_column, normalize_kind), ... coarsest->finest],
#               [geojson parent property label, ... coarsest->finest, matching convert_to_geojson.py])
LEVELS = {
    "provinsi": dict(
        csv="kopdes_stats_province.csv",
        csv_cols=[("province", None)],
        parent_labels=[],
    ),
    "kab_kota": dict(
        csv="kopdes_stats_district.csv",
        csv_cols=[("province", None), ("district", "district")],
        parent_labels=["provinsi"],
    ),
    "kecamatan": dict(
        csv="kopdes_stats_subdistrict.csv",
        csv_cols=[("province", None), ("district", "district"), ("subdistrict", "subdistrict")],
        parent_labels=["provinsi", "kab_kota"],
    ),
    "kel_desa": dict(
        csv="kopdes_stats_village.csv",
        csv_cols=[
            ("province", None), ("district", "district"),
            ("subdistrict", "subdistrict"), ("village", "village"),
        ],
        parent_labels=["provinsi", "kab_kota", "kecamatan"],
    ),
}


def log(*args):
    print("[link]", *args, flush=True)


def feature_key(props: dict, parent_labels: list) -> tuple:
    return tuple(props[f"{label}_norm"] for label in parent_labels) + (props["name_norm"],)


def build_level_maps(features, depth: int):
    """level_maps[L]: prefix tuple of length L -> {normalized name at position L: True}
    e.g. for kel_desa (depth 4), level_maps[2][(prov_norm, kab_norm)] holds every
    subdistrict name seen under that (province, district) pair."""
    level_maps = [dict() for _ in range(depth)]
    for feat in features:
        key = feat["_key"]
        for L in range(depth):
            prefix = key[:L]
            level_maps[L].setdefault(prefix, {})[key[L]] = True
    return level_maps


def resolve(row_norms: tuple, level_maps: list):
    """Cascades exact-then-fuzzy matching one level at a time. Returns
    (resolved_key_or_None, tier_reached, reasons) where reasons explains
    the first level that failed to resolve, if any."""
    depth = len(row_norms)
    resolved = ()
    any_fuzzy = False
    for L in range(depth):
        candidates = level_maps[L].get(resolved)
        if not candidates:
            return None, any_fuzzy, f"no boundary candidates at level {L} for parent {resolved!r}"
        target = row_norms[L]
        if target in candidates:
            resolved = resolved + (target,)
            continue
        close = difflib.get_close_matches(target, list(candidates.keys()), n=1, cutoff=FUZZY_CUTOFF)
        if not close:
            return None, any_fuzzy, f"no match at level {L} ('{target}' vs {len(candidates)} candidates under {resolved!r})"
        resolved = resolved + (close[0],)
        any_fuzzy = True
    return resolved, any_fuzzy, None


def link(level_key: str, cfg: dict):
    geojson_path = GEOJSON_DIR / f"{level_key}.geojson"
    csv_path = DATA_DIR / cfg["csv"]
    log(f"{level_key}: loading {geojson_path.name} and {csv_path.name}")

    with open(geojson_path, encoding="utf-8") as f:
        fc = json.load(f)
    features = fc["features"]
    depth = len(cfg["parent_labels"]) + 1

    for feat in features:
        feat["_key"] = feature_key(feat["properties"], cfg["parent_labels"])

    level_maps = build_level_maps(features, depth)
    by_full_key = {}
    for idx, feat in enumerate(features):
        by_full_key.setdefault(feat["_key"], []).append(idx)

    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    stat_cols = [c for c, _ in cfg["csv_cols"]]
    exact = fuzzy = unmatched = 0
    unmatched_rows = []

    for row in rows:
        row_norms = tuple(normalize_name(row[col], kind) for col, kind in cfg["csv_cols"])
        resolved, any_fuzzy, reason = resolve(row_norms, level_maps)

        if resolved is None:
            unmatched += 1
            unmatched_rows.append({**row, "_reason": reason})
            continue

        idxs = by_full_key[resolved]
        for idx in idxs:
            features[idx]["properties"].update({c: row[c] for c in row if c not in stat_cols})
            features[idx]["properties"]["_kopdes_match"] = "fuzzy" if any_fuzzy else "exact"

        if any_fuzzy:
            fuzzy += 1
        else:
            exact += 1

    for feat in features:
        del feat["_key"]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_geojson = OUT_DIR / f"{level_key}.geojson"
    with open(out_geojson, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False)

    unmatched_path = OUT_DIR / f"{level_key}_unmatched.csv"
    if unmatched_rows:
        with open(unmatched_path, "w", encoding="utf-8", newline="") as f:
            fieldnames = list(unmatched_rows[0].keys())
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(unmatched_rows)
    elif unmatched_path.exists():
        unmatched_path.unlink()

    total = len(rows)
    log(
        f"{level_key}: {total} kopdes rows -> exact={exact} fuzzy={fuzzy} "
        f"unmatched={unmatched} ({(exact + fuzzy) / total:.1%} matched)"
    )
    if unmatched_rows:
        log(f"{level_key}: unmatched rows written to {unmatched_path}")


def main():
    requested = [a.lower() for a in sys.argv[1:]] or list(LEVELS.keys())
    for key in requested:
        if key not in LEVELS:
            log(f"unknown level '{key}', skipping (valid: {', '.join(LEVELS)})")
            continue
        link(key, LEVELS[key])
    log("done")


if __name__ == "__main__":
    main()
