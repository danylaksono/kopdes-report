#!/usr/bin/env python3
"""
build_cell_indexes.py — the spatial layer /periksa/ reads in the browser.

The report's analyses run in Python over indexes that are far too large to
ship (the road cell index alone is 34 MB unsorted, the VIDA building index
larger still). /periksa/ has to answer the same questions at one arbitrary
coordinate, in a static page, with no backend. This script builds the artifacts
that make that possible.

The trick, and why this is not a compromise
-------------------------------------------
H3 cell ids sort hierarchically: every r10 descendant of a given r7 parent
occupies one contiguous range of the uint64 id space. So if the file is sorted
by `h3`, then

  1. delta encoding on near-consecutive uint64s compresses hard — the road
     index drops from 34 MB to ~12 MB purely from the sort, and
  2. a k-ring lookup becomes a narrow BETWEEN over that id space, which Parquet
     row-group statistics prune almost perfectly.

Measured on the road index with 20k-row row groups: a k=38 (~5 km) query at a
random cooperative touches 1–8 of 442 row groups and transfers 28–220 KB
(median 54 KB) out of a 12 MB file. Footers are 8–60 KB and read once. A full
five-measure analysis at a point costs roughly 150 KB of range requests.

This is the same DuckDB + H3-parquet shape the reports already use. Nothing is
recomputed or redefined here: these are the *same* cells the reports consume,
re-sorted and re-chunked for range-request access.

The parent column
-----------------
Each file also carries its cells' coarse parent (`p`), r7 for the r10 indexes
and r5 for the r8 population grid. The browser could instead derive one
[min,max] id range per query and filter the surplus in JS — the sort makes that
work — but a parent column lets the query say exactly what it wants:

    SELECT h3 FROM road WHERE p IN (<~15 parents covering the 5 km disk>)

Because the file is sorted by `h3` and H3 ids sort hierarchically, `p` is sorted
too, so row-group statistics prune on it just as well, and the rows that come
back are only the cells in the neighbourhood rather than everything in the
straddled id range. It costs almost nothing on disk: `p` is constant across long
runs of a sorted file, which is the best case for RLE.

Outputs (committed — /periksa/ 404s without them):
  data/web/cells/road_r10.parquet        h3 UBIGINT, p UBIGINT, non_track BOOLEAN
  data/web/cells/building_r10.parquet    h3 UBIGINT, p UBIGINT
  data/web/cells/pop_r8.parquet          h3 UBIGINT, p UBIGINT, population DOUBLE
  data/web/cells/minimarket.parquet      lon, lat, brand   (tier-1 only)
  data/web/cells/cells_manifest.json     provenance + row counts for the page

Usage:
  python scripts/build_cell_indexes.py
  python scripts/build_cell_indexes.py --buildings osm     # force the old layer
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "reports"))

OUT = ROOT / "data" / "web" / "cells"
ROAD_CELLS = ROOT / "data" / "osm" / "road_cells_h3r10.parquet"
BLD_OSM = ROOT / "data" / "osm" / "building_cells_h3r10.parquet"
BLD_VIDA = ROOT / "data" / "osm" / "building_cells_vida_h3r10.parquet"
POP = ROOT / "data" / "population" / "population_h3.parquet"
MINIMARKETS = ROOT / "data" / "osm" / "indonesia_minimarkets.gpkg"

# Small row groups are the whole point: they are the granularity at which the
# browser can skip data it does not need. 20k rows lands each group at ~26 KB
# for the road index, which is about one HTTP round trip's worth.
ROW_GROUP = 20_000

# Parent resolution per index. Chosen so the k-ring the page actually asks for
# lands on a handful of parents: a 5 km disk is ~78 km2, an r7 cell ~5.16 km2
# (so ~15 parents), and for the r8 population grid an r5 cell is ~252 km2 (so
# 1-4 parents). Coarser would return surplus rows, finer would bloat the IN list.
PARENT_RES = {"r10": 7, "r8": 5}


def copy_sorted(con, select_sql, dest: Path, label: str):
    con.execute(
        f"copy ({select_sql} order by h3) to '{dest.as_posix()}' "
        f"(format parquet, compression zstd, row_group_size {ROW_GROUP})"
    )
    n = con.execute(f"select count(*) from read_parquet('{dest.as_posix()}')").fetchone()[0]
    mb = dest.stat().st_size / 1e6
    print(f"  {label:<24} {n:>12,} cells  {mb:>7.2f} MB  -> {dest.name}")
    return {"rows": n, "bytes": dest.stat().st_size}


def build_minimarkets(con, dest: Path):
    """
    Tier-1 convenience/minimarket POIs only, exactly as report 06 defines them.

    The tiering is imported from the report rather than restated: a Matahari is
    not competition for a village cooperative selling rice and LPG, and if this
    file and the report ever disagreed about which POIs count, /periksa/ would
    quietly contradict the published figure.
    """
    import importlib.util

    import pyogrio

    spec = importlib.util.spec_from_file_location(
        "minimarket_report", ROOT / "reports" / "06-minimarket-proximity" / "run.py"
    )
    mod = importlib.util.module_from_spec(spec)
    saved, sys.argv = sys.argv, ["run"]
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.argv = saved

    mm = pyogrio.read_dataframe(MINIMARKETS)
    mm["lon"], mm["lat"] = mm.geometry.x, mm.geometry.y
    mm = mod.reclassify(mm.reset_index(drop=True))
    mm = mm[mm.tier == mod.TIER_CONVENIENCE].reset_index(drop=True)
    out = mm[["lon", "lat", "brand_label2"]].rename(columns={"brand_label2": "brand"})
    con.register("mm_out", out)
    con.execute(
        f"copy (select round(lon,6) lon, round(lat,6) lat, brand from mm_out) "
        f"to '{dest.as_posix()}' (format parquet, compression zstd)"
    )
    mb = dest.stat().st_size / 1e6
    print(f"  {'minimarkets (tier 1)':<24} {len(out):>12,} pts    {mb:>7.2f} MB  -> {dest.name}")
    return {"rows": len(out), "bytes": dest.stat().st_size}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--buildings", choices=["auto", "vida", "osm"], default="auto")
    args = ap.parse_args()

    if args.buildings == "vida" or (args.buildings == "auto" and BLD_VIDA.exists()):
        bld, bld_source = BLD_VIDA, "VIDA Google+Microsoft+OSM Open Buildings (source.coop)"
    else:
        bld, bld_source = BLD_OSM, "OpenStreetMap buildings (Geofabrik PBF)"

    missing = [p for p in (ROAD_CELLS, bld, POP, MINIMARKETS) if not p.exists()]
    if missing:
        sys.exit(
            "missing inputs:\n  "
            + "\n  ".join(str(p) for p in missing)
            + "\n\nrebuild them with reports/05-road-access/run.py,"
            " scripts/extract_buildings_vida.py,"
            " scripts/download_population.py, scripts/download_osm.py --poi-only"
        )

    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("install h3 from community; load h3;")
    con.execute("set preserve_insertion_order=false")

    print("=== building /periksa/ cell indexes ===")
    print(f"  buildings from: {bld_source}\n")
    man = {}
    p10 = PARENT_RES["r10"]
    p8 = PARENT_RES["r8"]

    man["road"] = copy_sorted(
        con,
        f"select h3, h3_cell_to_parent(h3, {p10}) as p, non_track "
        f"from read_parquet('{ROAD_CELLS.as_posix()}')",
        OUT / "road_r10.parquet",
        "roads r10",
    )
    # Only the id is shipped: /periksa/ asks "is there a building cell here",
    # and the per-cell counts and source flags stay server-side in the report.
    man["building"] = copy_sorted(
        con,
        f"select h3, h3_cell_to_parent(h3, {p10}) as p "
        f"from read_parquet('{bld.as_posix()}')",
        OUT / "building_r10.parquet",
        "buildings r10",
    )
    # Kontur ships the id as hex text; the browser side compares against
    # h3-js output converted to BigInt, so store it as the integer it is.
    man["population"] = copy_sorted(
        con,
        f"select ('0x'||h3)::UBIGINT as h3, "
        f"h3_cell_to_parent(('0x'||h3)::UBIGINT, {p8}) as p, population "
        f"from read_parquet('{POP.as_posix()}')",
        OUT / "pop_r8.parquet",
        "population r8",
    )
    man["minimarket"] = build_minimarkets(con, OUT / "minimarket.parquet")

    man.update(
        {
            "built": date.today().isoformat(),
            "resolutions": {"road": 10, "building": 10, "population": 8},
            "parent_res": {"road": p10, "building": p10, "population": p8},
            "km_per_ring_r10": 0.132,
            "row_group_size": ROW_GROUP,
            "sources": {
                "road": "OpenStreetMap via Geofabrik (reports/05-road-access)",
                "building": bld_source,
                "population": "Kontur Population Density 400m (H3 r8)",
                "minimarket": "OpenStreetMap Overpass, tier-1 only (reports/06)",
            },
        }
    )
    (OUT / "cells_manifest.json").write_text(json.dumps(man, indent=2), encoding="utf-8")
    total = sum(v["bytes"] for v in man.values() if isinstance(v, dict) and "bytes" in v)
    print(f"\n  total committed: {total/1e6:.1f} MB")
    print(f"  -> {OUT.relative_to(ROOT)}/cells_manifest.json")


if __name__ == "__main__":
    main()
