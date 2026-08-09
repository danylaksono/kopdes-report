#!/usr/bin/env python3
"""
05-road-access - how far is each KDMP from the nearest road?

Tests the *tidak bisa diakses* half of the placement critique with the most
legible variable available: straight-line distance to the nearest mapped road.
More interpretable in a write-up than slope, and it is the thing a reader
pictures when they hear "you can't get there".

Method - H3 line rasterisation, no geometry engine
--------------------------------------------------
Nearest-neighbour search against 4.5M LineStrings would normally mean an
R-tree over ~85M vertices. Instead the road network is *rasterised into H3
cells* once, and proximity becomes ring arithmetic on cell ids:

  1. read data/osm/indonesia_roads.gpkg in chunks
  2. densify each LineString to <=55 m segments (shapely.segmentize) so no
     cell is skipped between two distant vertices - an r10 cell is only ~76 m
     across, and a straight 500 m segment with two vertices would otherwise
     leave a false gap in the middle
  3. H3-index every vertex at r10 in DuckDB (vectorised C++, not a Python loop)
  4. keep the distinct cells -> ~19M rows, tens of MB of parquet

Then for each cooperative, expand H3 rings outward until one hits a road cell.
The ring index k converts to distance: adjacent r10 cell centres are ~132 m
apart, so distance ~= k * 132 m. That is a band, not a metric - see Caveats.

`track` is reported separately from the rest. A track is evidence of *some*
access; it is not a road you drive a delivery van down, and conflating the two
would understate the finding.

First run builds the cell index and caches it to data/osm/road_cells_h3r10.parquet
(measured: 129 s for all 4.5M LineStrings -> 9.05M distinct cells, 34 MB).
Later runs load the parquet and finish in seconds.

Usage:
  python reports/05-road-access/run.py
  python reports/05-road-access/run.py --rebuild-index
"""

import argparse
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd
import pyogrio
import shapely

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.common import RAW, ROOT, out_dir, write_csv  # noqa: E402

OUT = out_dir(__file__)
ROADS_GPKG = ROOT / "data" / "osm" / "indonesia_roads.gpkg"
CELL_INDEX = ROOT / "data" / "osm" / "road_cells_h3r10.parquet"

RES = 10                    # ~76 m edge, ~0.13 km2
SEG_DEG = 0.0005            # ~55 m densification, comfortably below the cell edge
KM_PER_RING = 0.132         # adjacent r10 cell centres, approx
CHUNK = 200_000

# Everything in this gpkg is already vehicular (the extractor filtered out
# footway/path/cycleway). `track` is the one class that is not a made road.
NON_ROAD_CLASSES = {"track"}

# k -> label. Ring counts chosen so the labels land on round-ish distances.
BANDS = [
    (0, "on a road cell (<70 m)"),
    (2, "< ~260 m"),
    (4, "< ~530 m"),
    (8, "< ~1 km"),
    (15, "< ~2 km"),
    (38, "< ~5 km"),
]


def build_cell_index(con):
    print(f"building road cell index at H3 r{RES} (one time, ~10-15 min)")
    info = pyogrio.read_info(ROADS_GPKG)
    total = info["features"]
    con.execute("create or replace table road_cells (h3 UBIGINT, non_track BOOLEAN)")

    t0 = time.time()
    for start in range(0, total, CHUNK):
        df = pyogrio.read_dataframe(
            ROADS_GPKG, columns=["highway"], skip_features=start, max_features=CHUNK
        )
        if df.empty:
            break
        # Densify so consecutive vertices are never more than one cell apart.
        geoms = shapely.segmentize(df.geometry.values, max_segment_length=SEG_DEG)
        coords = shapely.get_coordinates(geoms)
        # get_coordinates flattens; map each coordinate back to its LineString
        # so the track/road distinction survives.
        counts = shapely.get_num_coordinates(geoms)
        non_track = (~df.highway.isin(NON_ROAD_CLASSES)).values.repeat(counts)

        chunk = pd.DataFrame(
            {"lon": coords[:, 0], "lat": coords[:, 1], "non_track": non_track}
        )
        con.register("chunk", chunk)
        con.execute(
            f"""insert into road_cells
                select h3_latlng_to_cell(lat, lon, {RES}) as h3, bool_or(non_track)
                from chunk group by 1"""
        )
        con.unregister("chunk")
        done = min(start + CHUNK, total)
        print(f"    {done:>9,}/{total:,} features  ({time.time()-t0:.0f}s)")

    con.execute(
        """create or replace table road_cells_d as
           select h3, bool_or(non_track) as non_track from road_cells group by 1"""
    )
    n, nt = con.execute(
        "select count(*), count(*) filter (where non_track) from road_cells_d"
    ).fetchone()
    con.execute(f"copy road_cells_d to '{CELL_INDEX.as_posix()}' (format parquet, compression zstd)")
    print(f"  {n:,} distinct cells ({nt:,} with a non-track road) "
          f"-> {CELL_INDEX.stat().st_size/1e6:.0f} MB, {time.time()-t0:.0f}s total")


def nearest_ring(con, table, road_filter, label):
    """
    Staged outward ring search. Most cooperatives resolve at k=0..2, so growing
    the disk only for the unresolved ones keeps the join small - a flat
    grid_disk(38) over 83k points would be 4.5 billion rows.
    """
    con.execute(f"create or replace table roads_f as select h3 from road_cells_d where {road_filter}")
    con.execute(f"create or replace table unresolved as select cooperative_id, h3 from {table}")
    con.execute("create or replace table hits (cooperative_id BIGINT, k INTEGER)")

    # One ring at a time, cheapest first: h3_grid_disk_distances returns a
    # list-of-lists whose outer index is the ring number, and flattening that
    # while keeping the index is awkward in SQL. grid_ring(k) is the same
    # information one shell at a time, and lets us drop resolved rows as we go.
    prev = 0
    for k, _ in BANDS:
        t0 = time.time()
        for kk in range(prev, k + 1):
            con.execute(
                f"""insert into hits
                    select u.cooperative_id, {kk}
                    from unresolved u
                    where exists (
                        select 1 from unnest(h3_grid_ring(u.h3, {kk})) as c(cell)
                        join roads_f r on r.h3 = c.cell
                    )"""
            )
            con.execute(
                """delete from unresolved
                   where cooperative_id in (select cooperative_id from hits)"""
            )
        left = con.execute("select count(*) from unresolved").fetchone()[0]
        print(f"    {label}: k<={k:>2} ({k*KM_PER_RING:4.2f} km) -> {left:>6,} still unresolved "
              f"({time.time()-t0:.0f}s)")
        prev = k + 1
        if left == 0:
            break

    return con.execute("select cooperative_id, k from hits").fetchdf()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild-index", action="store_true")
    args = ap.parse_args()

    if not ROADS_GPKG.exists():
        sys.exit(f"missing {ROADS_GPKG}\n  run: python scripts/download_osm.py --roads-only")

    con = duckdb.connect()
    con.execute("install h3 from community; load h3;")

    if CELL_INDEX.exists() and not args.rebuild_index:
        con.execute(f"create table road_cells_d as select * from read_parquet('{CELL_INDEX.as_posix()}')")
        n = con.execute("select count(*) from road_cells_d").fetchone()[0]
        print(f"road cell index: {n:,} H3 r{RES} cells (cached)")
    else:
        build_cell_index(con)

    loc = pd.read_csv(RAW / "kopdes_locations.csv")
    con.register("loc", loc[["cooperative_id", "province", "district", "subdistrict", "latitude", "longitude"]])
    con.execute(
        f"""create or replace table kop as
            select cooperative_id, province, district, subdistrict, latitude, longitude,
                   h3_latlng_to_cell(latitude, longitude, {RES}) as h3
            from loc"""
    )

    print("\nnearest ANY road (incl. track):")
    any_road = nearest_ring(con, "kop", "true", "any").rename(columns={"k": "k_any_road"})
    print("\nnearest NON-TRACK road:")
    real_road = nearest_ring(con, "kop", "non_track", "non-track").rename(columns={"k": "k_non_track"})

    per = (
        con.execute("select * from kop").fetchdf()
        .merge(any_road, on="cooperative_id", how="left")
        .merge(real_road, on="cooperative_id", how="left")
    )
    for col in ("k_any_road", "k_non_track"):
        per[col.replace("k_", "km_")] = (per[col] * KM_PER_RING).round(3)

    def band(k):
        if pd.isna(k):
            return "> ~5 km / none found"
        for kk, lbl in BANDS:
            if k <= kk:
                return lbl
        return "> ~5 km / none found"

    per["road_band"] = per.k_non_track.map(band)
    per["track_only"] = per.k_non_track.isna() & per.k_any_road.notna()
    write_csv(per, OUT / "kopdes_road_access.csv", "per-cooperative; joins to 03 on cooperative_id")

    order = [lbl for _, lbl in BANDS] + ["> ~5 km / none found"]
    bands = (
        per.road_band.value_counts().reindex(order).fillna(0).astype(int)
        .rename_axis("distance_to_nearest_non_track_road").reset_index(name="cooperatives")
    )
    bands["pct"] = (100 * bands.cooperatives / len(per)).round(2)
    print()
    print(bands.to_string(index=False))
    write_csv(bands, OUT / "road_access_bands.csv")

    prov = (
        per.assign(far=per.k_non_track.isna() | (per.k_non_track > 8))
        .groupby("province")
        .agg(cooperatives=("cooperative_id", "size"), far_from_road=("far", "sum"))
        .assign(pct_far=lambda d: (100 * d.far_from_road / d.cooperatives).round(2))
        .sort_values("pct_far", ascending=False)
        .reset_index()
    )
    write_csv(prov, OUT / "road_access_by_province.csv")
    print(f"\ntrack-only access (a track but no made road within ~5 km): {int(per.track_only.sum()):,}")
    print(f"no road of any kind within ~5 km: {int(per.k_any_road.isna().sum()):,}")


if __name__ == "__main__":
    main()
