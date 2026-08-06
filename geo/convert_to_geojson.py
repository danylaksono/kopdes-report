#!/usr/bin/env python3
"""
convert_to_geojson.py

Converts the extracted BIG boundary shapefiles (geo/raw/<level>/extracted/*.shp)
into GeoJSON FeatureCollections (geo/geojson/<level>.geojson), adding a
normalized-name property at every level (province/district/subdistrict/village)
so link_kopdes.py can join on names without redoing the normalization.

Source shapefiles come from Alf-Anas/batas-administrasi-indonesia and use BPS
codes (KODE_PROV/KODE_KK/KODE_KEC/KODE_DESA) - those are carried through as
properties too, in case a future kopdes export starts using them directly.

Usage: python convert_to_geojson.py [level ...]
       (levels: provinsi kab_kota kecamatan kel_desa; default: all four)
"""

import json
import sys
from pathlib import Path

import shapefile
from shapely.geometry import mapping, shape

from name_utils import normalize_name

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "raw"
OUT_DIR = ROOT / "geojson"

# Source shapefiles are BIG survey-grade data at 1:10.000 scale - a raw
# conversion produces ~460MB of GeoJSON for 38 province polygons alone.
# Simplify (Douglas-Peucker, topology-preserving) to a tolerance in degrees
# suited to each level's typical display/analysis scale; ~1 degree latitude
# is ~111km, so 0.001 degrees is roughly 100m.
SIMPLIFY_TOLERANCE = {
    "provinsi": 0.005,
    "kab_kota": 0.002,
    "kecamatan": 0.001,
    "kel_desa": 0.0005,
}

# field maps: (shapefile basename, own {code,name} field, list of parent
# {code,name} field pairs from coarsest to finest, our own normalization kind)
LEVELS = {
    "provinsi": dict(
        shp="Provinsi.shp",
        code_field="KODE_PROV", name_field="PROVINSI", kind=None,
        parents=[],
    ),
    "kab_kota": dict(
        shp="Kab_Kota.shp",
        code_field="KODE_KK", name_field="KAB_KOTA", kind="district",
        parents=[("KODE_PROV", "PROVINSI", None)],
    ),
    "kecamatan": dict(
        shp="Kecamatan.shp",
        code_field="KODE_KEC", name_field="KECAMATAN", kind="subdistrict",
        parents=[("KODE_PROV", "PROVINSI", None), ("KODE_KK", "KAB_KOTA", "district")],
    ),
    "kel_desa": dict(
        shp="Kel_Desa.shp",
        code_field="KODE_KD", name_field="KEL_DESA", kind="village",
        parents=[
            ("KODE_PROV", "PROVINSI", None),
            ("KODE_KK", "KAB_KOTA", "district"),
            ("KODE_KEC", "KECAMATAN", "subdistrict"),
        ],
    ),
}


def log(*args):
    print("[convert]", *args, flush=True)


def find_shp(level_key: str, expected_name: str) -> Path:
    extracted = RAW_DIR / level_key / "extracted"
    exact = extracted / expected_name
    if exact.exists():
        return exact
    candidates = list(extracted.rglob("*.shp"))
    if len(candidates) == 1:
        return candidates[0]
    raise FileNotFoundError(
        f"Expected {exact} not found and {len(candidates)} other .shp candidates exist "
        f"under {extracted} - inspect field names and update LEVELS in this script."
    )


def convert(level_key: str, cfg: dict):
    shp_path = find_shp(level_key, cfg["shp"])
    log(f"{level_key}: reading {shp_path}")
    sf = shapefile.Reader(str(shp_path))
    field_names = [f[0] for f in sf.fields[1:]]  # skip DeletionFlag
    for required in [cfg["code_field"], cfg["name_field"]] + [f for p in cfg["parents"] for f in p[:2]]:
        if required not in field_names:
            raise KeyError(
                f"{level_key}: field '{required}' not found in {shp_path} "
                f"(available: {field_names}) - update LEVELS in this script."
            )

    tolerance = SIMPLIFY_TOLERANCE.get(level_key, 0.001)
    features = []
    for shape_rec in sf.iterShapeRecords():
        rec = shape_rec.record.as_dict()
        raw_geom = shape_rec.shape.__geo_interface__
        if raw_geom is None or not raw_geom.get("coordinates"):
            continue
        simplified = shape(raw_geom).simplify(tolerance, preserve_topology=True)
        if simplified.is_empty:
            continue
        geom = mapping(simplified)

        props = {
            "code": rec.get(cfg["code_field"]),
            "name": rec.get(cfg["name_field"]),
            "name_norm": normalize_name(rec.get(cfg["name_field"]), cfg["kind"]),
        }
        for code_field, name_field, parent_kind in cfg["parents"]:
            label = name_field.lower()
            props[f"{label}_code"] = rec.get(code_field)
            props[f"{label}_name"] = rec.get(name_field)
            props[f"{label}_norm"] = normalize_name(rec.get(name_field), parent_kind)

        features.append({"type": "Feature", "properties": props, "geometry": geom})

    fc = {"type": "FeatureCollection", "features": features}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{level_key}.geojson"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False)
    log(f"{level_key}: wrote {len(features)} features -> {out_path}")


def main():
    requested = [a.lower() for a in sys.argv[1:]] or list(LEVELS.keys())
    for key in requested:
        if key not in LEVELS:
            log(f"unknown level '{key}', skipping (valid: {', '.join(LEVELS)})")
            continue
        convert(key, LEVELS[key])
    log("done")


if __name__ == "__main__":
    main()
