#!/usr/bin/env python3
"""
extract_buildings_vida.py — building footprints for Indonesia from VIDA's
combined Google + Microsoft + OSM layer, reduced to H3 r10 cells.

Why this exists alongside extract_buildings.py
----------------------------------------------
`extract_buildings.py` reduces the Indonesia PBF to 3.59M r10 cells from ~44M
OSM buildings. That layer is the reason report 17 has to hedge every sentence:
OSM building coverage in rural Indonesia is thin, so "no mapped building within
5 km" was a lower bound of unknown looseness, biased in the direction that
flatters the programme.

VIDA's layer is the Google + Microsoft + OSM union, and the ML-derived
footprints are dense exactly where OSM is not. Indonesia alone carries
137,070,577 footprints, roughly 3x the OSM count. Swapping it in narrows the
caveat from "we cannot see rural houses" to "we can, at a stated confidence".

Source: https://source.coop/vida/google-microsoft-osm-open-buildings
License: CC-BY-4.0 (Google Open Buildings + Microsoft Building Footprints + OSM
ODbL). The ODbL share-alike obligation rides on the OSM-sourced rows, which is
why `bf_source` is carried through to the cell table rather than discarded.

What it costs
-------------
The remote file is 16.9 GB, but the geometry column is 9.6 GB of that and we do
not need it: the `bbox` struct gives xmin/ymin/xmax/ymax as plain doubles, and a
building's bbox centroid is well inside its own r10 cell (an r10 cell is ~132 m
across; Indonesian buildings are metres). Projecting bbox + bf_source +
confidence pulls ~5.7 GB instead of 16.9 GB. Measured throughput from
source.coop is ~20 MB/s, so budget 5-10 minutes plus aggregation.

The file is NOT sorted by geohash or bbox (27,414 of 27,415 row groups overlap
their neighbour), so there is no pruning to exploit; this is a full projected
scan by design. It is a one-time cost.

Output: data/osm/building_cells_vida_h3r10.parquet
  h3 UBIGINT, buildings INT, has_osm/has_google/has_ms BOOLEAN, max_conf DOUBLE

Carrying the source flags and confidence per cell means report 17 can run a
sensitivity pass (OSM-only, or Google above a confidence floor) without
re-downloading 5.7 GB.

Usage:
  python scripts/extract_buildings_vida.py
  python scripts/extract_buildings_vida.py --rebuild
"""

import argparse
import sys
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "osm" / "building_cells_vida_h3r10.parquet"
SRC = (
    "https://data.source.coop/vida/google-microsoft-osm-open-buildings"
    "/geoparquet/by_country/country_iso=IDN/IDN.parquet"
)
RES = 10  # same resolution as the OSM index, so the ring search is unchanged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true", help="overwrite an existing index")
    ap.add_argument("--memory", default="6GB", help="DuckDB memory limit")
    args = ap.parse_args()

    if OUT.exists() and not args.rebuild:
        print(f"[skip] already built: {OUT}  (use --rebuild to force)")
        return

    OUT.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("install httpfs; load httpfs;")
    con.execute("install h3 from community; load h3;")
    con.execute(f"set memory_limit='{args.memory}'")
    # Aggregating 137M rows down to tens of millions of cells will spill; give it
    # somewhere on disk to spill to rather than letting it die at the limit.
    con.execute(f"set temp_directory='{(ROOT / 'data' / 'osm' / '_duckdb_tmp').as_posix()}'")
    con.execute("set preserve_insertion_order=false")

    print("=== VIDA Indonesia buildings -> H3 r10 cells ===")
    print(f"  source: {SRC}")
    print("  projecting bbox + bf_source + confidence (~5.7 GB of 16.9 GB)")
    t0 = time.time()

    # The bbox centroid, not a corner: a corner sits on the footprint edge and
    # would bias every building consistently toward one neighbouring cell.
    con.execute(
        f"""
        create table cells as
        select
            h3_latlng_to_cell((bbox.ymin + bbox.ymax) / 2,
                              (bbox.xmin + bbox.xmax) / 2, {RES}) as h3,
            count(*)::INTEGER                                     as buildings,
            -- The labels are lowercase and short: 'osm', 'google', 'microsoft'.
            -- Guessing 'OpenStreetMap' here silently produced an all-false
            -- has_osm on the first run, which would have understated the ODbL
            -- share of the layer. Verified against the column statistics.
            bool_or(bf_source = 'osm')                            as has_osm,
            bool_or(bf_source = 'google')                         as has_google,
            bool_or(bf_source = 'microsoft')                      as has_ms,
            max(confidence)                                       as max_conf
        from read_parquet('{SRC}')
        group by 1
        """
    )
    n_cells, n_bld = con.execute(
        "select count(*), sum(buildings) from cells"
    ).fetchone()
    print(f"  {n_bld:,} buildings -> {n_cells:,} distinct r10 cells "
          f"({time.time()-t0:.0f}s)")

    print("\n  source mix (cells touched by each provider):")
    for label, col in (("OpenStreetMap", "has_osm"), ("Google", "has_google"),
                       ("Microsoft", "has_ms")):
        c = con.execute(f"select count(*) from cells where {col}").fetchone()[0]
        print(f"    {label:<14} {c:>12,}  ({100*c/n_cells:5.1f}% of cells)")

    # Sorted on write: H3 ids sort hierarchically, so a sorted file both
    # compresses far better (delta encoding on near-consecutive uint64s) and
    # lets row-group statistics prune a k-ring lookup down to a couple of row
    # groups. scripts/build_cell_indexes.py depends on this ordering.
    con.execute(
        f"copy (select * from cells order by h3) to '{OUT.as_posix()}' "
        f"(format parquet, compression zstd, row_group_size 20000)"
    )
    print(f"\n  -> {OUT.name} ({OUT.stat().st_size/1e6:.1f} MB) in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    sys.exit(main())
