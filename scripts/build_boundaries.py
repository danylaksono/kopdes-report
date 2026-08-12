"""build_boundaries.py - web-ready administrative boundaries for /explore/.

The geo/ pipeline produces `geo/output/<level>.geojson`: every boundary polygon
with the SIMKOPDES stats merged in. Those files are 5-40 MB, carry a full copy
of the stats, and are gitignored - a Pages deploy cannot serve them.

The explorer does not need any of that. Boundaries there are *context under the
glyphs*: a faint fill that tells you which kabupaten a symbol belongs to. Every
measure the map draws comes from the parquet mart through DuckDB, joined on the
admin id. So this script throws away all the merged stats, keeps `id` + `name`,
simplifies hard, and rounds coordinates to the precision the zoom range can
actually resolve.

    python scripts/build_boundaries.py            # all three levels
    python scripts/build_boundaries.py provinsi   # just one

Output lands in `data/web/boundaries/` and is committed - like the parquet mart,
it is app data, not a regenerable intermediate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from shapely.geometry import mapping, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "geo" / "output"
DST = ROOT / "data" / "web" / "boundaries"

# Per level: the source file, the mart's join key, and how much detail survives.
#
# `tolerance` and `min_part_area` are in degrees / square degrees (1 deg ~ 111 km
# at the equator, and Indonesia straddles it). They are tuned to the zoom each
# level is actually read at: provinsi fills the screen at z4, kecamatan is only
# legible from z8 up, so it keeps roughly an order of magnitude more detail.
#
# `min_part_area` drops islands too small to render as more than a pixel. This
# matters more here than almost anywhere else - Indonesia's polygons carry tens
# of thousands of islets, and at provinsi zoom they are pure file size. The
# threshold is deliberately conservative: 0.0004 deg^2 is ~5 km^2, well under
# any island a reader could point at.
LEVELS = {
    "provinsi": {
        "src": "provinsi.geojson",
        "key": "province_id",
        "tolerance": 0.015,
        "min_part_area": 0.0004,
        "decimals": 3,
    },
    "kabupaten": {
        "src": "kab_kota.geojson",
        "key": "district_id",
        "tolerance": 0.006,
        "min_part_area": 0.00015,
        "decimals": 4,
    },
    "kecamatan": {
        "src": "kecamatan.geojson",
        "key": "subdistrict_id",
        "tolerance": 0.002,
        "min_part_area": 0.00003,
        "decimals": 4,
    },
}


def drop_small_parts(geom, min_area: float):
    """Remove polygon parts below `min_area`, keeping the largest regardless.

    A kabupaten that *is* a small island would otherwise vanish entirely, which
    is worse than carrying it: the reader would see a hole in the map with no
    explanation. So the biggest part always survives the filter.
    """
    if geom.geom_type == "Polygon":
        return geom
    parts = [p for p in geom.geoms if p.area >= min_area]
    if not parts:
        parts = [max(geom.geoms, key=lambda p: p.area)]
    return unary_union(parts) if len(parts) > 1 else parts[0]


def round_coords(obj, decimals: int):
    """Round every coordinate in a GeoJSON geometry mapping, in place-ish.

    Rounding is where most of the file size goes. Shapely emits full float64
    repr (~17 significant digits); 4 decimals is ~11 m, finer than the
    simplification tolerance already applied, so nothing visible is lost.
    """
    if isinstance(obj, (list, tuple)):
        if obj and isinstance(obj[0], (int, float)):
            return [round(float(c), decimals) for c in obj]
        return [round_coords(o, decimals) for o in obj]
    return obj


def build(level: str) -> None:
    cfg = LEVELS[level]
    src = SRC / cfg["src"]
    if not src.exists():
        raise SystemExit(
            f"missing {src}\nRun the geo pipeline first: python geo/run_pipeline.py"
        )

    print(f"[{level}] reading {src.name} ({src.stat().st_size / 1e6:.1f} MB)")
    with src.open(encoding="utf-8") as fh:
        raw = json.load(fh)

    out = []
    dropped = 0
    for feat in raw["features"]:
        props = feat.get("properties") or {}
        raw_id = props.get(cfg["key"])
        if raw_id in (None, "", "None"):
            # No SIMKOPDES id means the polygon never matched the stats export;
            # it can never be joined to a mart row, so it would render as a
            # permanently empty shape. geo/output/<level>_unmatched.csv is the
            # place that gap is accounted for, not the map.
            dropped += 1
            continue

        geom = shape(feat["geometry"])
        geom = drop_small_parts(geom, cfg["min_part_area"])
        geom = geom.simplify(cfg["tolerance"], preserve_topology=True)
        if geom.is_empty:
            dropped += 1
            continue

        gj = mapping(geom)
        out.append(
            {
                "type": "Feature",
                "properties": {"id": int(raw_id), "name": props.get("name") or ""},
                "geometry": {
                    "type": gj["type"],
                    "coordinates": round_coords(gj["coordinates"], cfg["decimals"]),
                },
            }
        )

    DST.mkdir(parents=True, exist_ok=True)
    dst = DST / f"{level}.geojson"
    with dst.open("w", encoding="utf-8") as fh:
        json.dump(
            {"type": "FeatureCollection", "features": out},
            fh,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    size = dst.stat().st_size / 1e6
    print(f"[{level}] wrote {len(out)} features, {dropped} dropped -> {size:.2f} MB")


def main() -> None:
    levels = sys.argv[1:] or list(LEVELS)
    unknown = [lv for lv in levels if lv not in LEVELS]
    if unknown:
        raise SystemExit(f"unknown level(s): {', '.join(unknown)}")
    for level in levels:
        build(level)


if __name__ == "__main__":
    main()
