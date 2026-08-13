#!/usr/bin/env python3
"""
extract_buildings.py — one-time extraction of OSM building footprints from the
Indonesia PBF, reduced to H3 r10 cells.

Report 17 needs "how far is each cooperative from the nearest building" — the
"no houses around" measure. The PBF (data/osm/indonesia-latest.osm.pbf) carries
~44M building-tagged ways. Buildings are points for our purposes (a house is
~one r10 cell), so this script:

  1. streams the PBF with osmium, computes each building way's centroid
     (arithmetic mean of its vertices), and writes lon,lat to a temp CSV
  2. H3-indexes every centroid at r10 in DuckDB and keeps the DISTINCT cells
     -> data/osm/building_cells_h3r10.parquet
  3. keeps the centroids parquet as provenance, deletes the temp CSV

The cells parquet is what reports/17-building-proximity reads (same shape as
road_cells_h3r10.parquet from report 05, so the ring-search code is identical).
OSM building coverage is incomplete in rural Indonesia — a missing cell is a
"no *mapped* house", never "no house". State it that way.

Usage:
  python scripts/extract_buildings.py
"""

import csv
import sys
import time
from pathlib import Path

import duckdb

try:
    import osmium
except ImportError:
    print("[error] pip install osmium")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
PBF = ROOT / "data" / "osm" / "indonesia-latest.osm.pbf"
CENTROIDS_CSV = ROOT / "data" / "osm" / "indonesia_buildings.csv"
CENTROIDS_PARQUET = ROOT / "data" / "osm" / "indonesia_buildings.parquet"
CELLS_PARQUET = ROOT / "data" / "osm" / "building_cells_h3r10.parquet"
RES = 10  # ~76 m edge; adjacent cell centres ~132 m — same as report 05


class BuildingHandler(osmium.SimpleHandler):
    def __init__(self, out_path):
        super().__init__()
        self.f = open(out_path, "w", newline="", encoding="utf-8")
        self.w = csv.writer(self.f)
        self.count = 0

    def way(self, w):
        # A way is a building if it carries a `building` tag. Skip building:part
        # (they are fragments of a single building and would double-count).
        if "building" not in w.tags:
            return
        lon_sum = lat_sum = 0.0
        n = 0
        for ref in w.nodes:
            loc = ref.location
            if loc.valid():
                lon_sum += loc.lon
                lat_sum += loc.lat
                n += 1
        if n < 3:
            return
        self.w.writerow((w.id, round(lon_sum / n, 7), round(lat_sum / n, 7)))
        self.count += 1
        if self.count % 1_000_000 == 0:
            print(f"  ... {self.count:,} building centroids")

    def close(self):
        self.f.close()


def main():
    if not PBF.exists():
        sys.exit(f"missing {PBF}")
    if CELLS_PARQUET.exists():
        print(f"[skip] building cells already built: {CELLS_PARQUET}")
        return

    print("=== Extracting building footprints (one time, ~15-30 min) ===")
    t0 = time.time()
    handler = BuildingHandler(CENTROIDS_CSV)
    handler.apply_file(str(PBF), locations=True)
    handler.close()
    print(f"  {handler.count:,} building centroids in {time.time()-t0:.0f}s")
    print(f"  {CENTROIDS_CSV.stat().st_size/1e9:.2f} GB CSV")

    # H3-index + distinct cells in DuckDB (vectorised, same as report 05)
    print("  H3-indexing at r10 ...")
    con = duckdb.connect()
    con.execute("install h3 from community; load h3;")
    con.execute(f"create table buildings as select * from read_csv_auto('{CENTROIDS_CSV.as_posix()}', header=false, names=['osm_id','lon','lat'])")
    con.execute(f"""create table building_cells as
                    select h3_latlng_to_cell(lat, lon, {RES}) as h3 from buildings group by 1""")
    n = con.execute("select count(*) from building_cells").fetchone()[0]
    con.execute(f"copy building_cells to '{CELLS_PARQUET.as_posix()}' (format parquet, compression zstd)")
    # keep centroids parquet for provenance / future exact distances
    con.execute(f"copy buildings to '{CENTROIDS_PARQUET.as_posix()}' (format parquet, compression zstd)")
    print(f"  {n:,} distinct r10 cells -> {CELLS_PARQUET.name} ({CELLS_PARQUET.stat().st_size/1e6:.0f} MB)")
    CENTROIDS_CSV.unlink(missing_ok=True)
    print(f"  done in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
