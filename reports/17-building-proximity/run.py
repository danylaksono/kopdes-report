#!/usr/bin/env python3
"""
17-building-proximity - how far is each KDMP from the nearest building?

Tests the "no houses around" half of the placement critique with the most
direct variable available: distance to the nearest OSM building footprint. The
population grid (03) and road distance (05) both approximate this; neither
measures it. A cooperative with no mapped building within a kilometre is a
stronger, more visual claim than "in a low-population cell".

Method - same as 05, points instead of lines
--------------------------------------------
  1. A building layer has already been reduced to the DISTINCT H3 r10 cells
     that contain >=1 building centroid (see --buildings below).
  2. For each cooperative, expand H3 rings outward until one hits a building
     cell. Ring k converts to distance the same way as roads: adjacent r10 cell
     centres are ~132 m apart, so distance ~= k * 132 m. A band, not a metric.
  3. Because the bands are the same k's as 05, "far from a road" and "no house
     nearby" are directly comparable at the same cell scale.

Which building layer (2026-08-14)
---------------------------------
This report originally ran on OSM buildings alone (~44M footprints -> 3.59M r10
cells), and every sentence in it had to hedge: OSM's rural coverage in Indonesia
is thin, so "no mapped building within 5 km" was a lower bound of unknown
looseness, biased toward flattering the programme.

It now defaults to VIDA's combined Google + Microsoft + OSM layer
(137,070,577 Indonesian footprints -> 10,477,049 r10 cells, 2.9x the coverage),
built by scripts/extract_buildings_vida.py. `--buildings osm` still runs the old
layer, which is how the two are compared in the README.

The caveat is narrowed, not removed: ML-derived footprints miss buildings too,
and "no mapped building within X" remains a LOWER BOUND. Write "no *mapped*
house", never "no house". The cross-tab with the Kontur population grid (03) and
the confirmed farmland set (07) is what keeps this honest.

Usage:
  python reports/17-building-proximity/run.py
  python reports/17-building-proximity/run.py --buildings osm
"""

import argparse
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.common import RAW, ROOT, out_dir, write_csv  # noqa: E402

OUT = out_dir(__file__)
CELLS_OSM = ROOT / "data" / "osm" / "building_cells_h3r10.parquet"
CELLS_VIDA = ROOT / "data" / "osm" / "building_cells_vida_h3r10.parquet"
RES = 10
KM_PER_RING = 0.132  # adjacent r10 cell centres, approx - same as 05

NONE_BAND = "> ~5 km / none found"

# Same k's as 05 so road and building distances compose.
BANDS = [
    (0, "on a building cell (<70 m)"),
    (2, "< ~260 m"),
    (4, "< ~530 m"),
    (8, "< ~1 km"),
    (15, "< ~2 km"),
    (38, "< ~5 km"),
]


def nearest_ring(con, table, label):
    con.execute(f"create or replace table unresolved as select cooperative_id, h3 from {table}")
    con.execute("create or replace table hits (cooperative_id BIGINT, k INTEGER)")
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
                        join bld b on b.h3 = c.cell
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
    ap.add_argument("--buildings", choices=["vida", "osm"], default="vida",
                    help="which building layer to measure against (default: vida)")
    args = ap.parse_args()

    cells = CELLS_VIDA if args.buildings == "vida" else CELLS_OSM
    if not cells.exists():
        hint = ("python scripts/extract_buildings_vida.py" if args.buildings == "vida"
                else "python scripts/extract_buildings.py")
        sys.exit(f"missing {cells}\n  run: {hint}")

    loc = pd.read_csv(RAW / "kopdes_locations.csv")
    print(f"loaded {len(loc):,} cooperatives")
    print(f"building layer: {args.buildings} ({cells.name})\n")

    con = duckdb.connect()
    con.execute("install h3 from community; load h3;")
    con.execute(f"create table bld as select h3 from read_parquet('{cells.as_posix()}')")
    n_bld = con.execute("select count(*) from bld").fetchone()[0]
    print(f"building cells: {n_bld:,} distinct H3 r10 cells\n")

    con.register("loc", loc[["cooperative_id", "latitude", "longitude"]])
    con.execute(
        "create table kop as select cooperative_id, "
        f"h3_latlng_to_cell(latitude, longitude, {RES}) as h3 from loc"
    )

    print("nearest building, staged outward rings:")
    hits = nearest_ring(con, "kop", "building")

    # --- band assignment ----------------------------------------------------
    # A THRESHOLD WALK, not a lookup keyed on the band's own k. The ring search
    # returns whatever k it stopped at - any integer 0..38 - while BANDS names
    # only six of them. `hits.k.map(dict(BANDS))` therefore returned NaN for
    # every cooperative whose nearest building sat on an off-key ring (1, 3, 5,
    # 6, 7, 9-14, 16-37), and the .fillna() below it swept all of them into
    # "none found". That is how a true 13.7% was published as 62.6% between
    # 2026-08-13 and 2026-08-14. Report 05 always did this correctly; only this
    # report used the dict. Do not reintroduce it.
    def band(k):
        if k is None or pd.isna(k):
            return NONE_BAND
        for kk, label in BANDS:
            if k <= kk:
                return label
        return NONE_BAND

    per = loc.merge(hits[["cooperative_id", "k"]], on="cooperative_id", how="left")
    per["building_k"] = per.k
    # Continuous distance alongside the band, the same way 05 reports both. A
    # null here means "not found within the ring cap", never "zero".
    per["km_to_building"] = (per.k * KM_PER_RING).round(3)
    per["building_band"] = per.k.map(band)
    per = per.drop(columns=["k"])

    # --- outputs ------------------------------------------------------------
    band_counts = per.building_band.value_counts().rename_axis("building_band").reset_index(name="cooperatives")
    band_counts["pct"] = (100 * band_counts.cooperatives / len(per)).round(2)
    write_csv(band_counts, OUT / "building_access_bands.csv", "per-cooperative band")
    print("\nbuilding_access_bands:")
    print(band_counts.to_string(index=False))

    by_prov = (per.groupby("province").size().rename("cooperatives").to_frame()
               .join(per[per.building_band.isin([NONE_BAND])].groupby("province").size()
                     .rename("no_building_5km").fillna(0).astype(int)))
    by_prov["pct_no_building_5km"] = (100 * by_prov.no_building_5km / by_prov.cooperatives).round(2)
    write_csv(by_prov.reset_index(), OUT / "building_access_by_province.csv")
    write_csv(per, OUT / "kopdes_building_access.csv", "per-cooperative; joins on cooperative_id")

    # --- cross-tabs ---------------------------------------------------------
    no1 = int(per.building_band.isin([NONE_BAND, "< ~2 km", "< ~5 km"]).sum())
    no5 = int((per.building_band == NONE_BAND).sum())
    print(f"\nno building within ~1 km: {no1:,} ({100*no1/len(per):.2f}%)")
    print(f"no building within ~5 km: {no5:,} ({100*no5/len(per):.2f}%)")

    # overlap with roadless (05), isolated (03), farmland (07)
    road = pd.read_csv(ROOT / "reports" / "05-road-access" / "kopdes_road_access.csv")
    remot = pd.read_csv(ROOT / "reports" / "03-population-coverage" / "kopdes_remoteness.csv")
    land = pd.read_csv(ROOT / "reports" / "07-landuse-polygons" / "kopdes_landuse_context.csv")

    m = per.merge(road[["cooperative_id", "km_non_track"]], on="cooperative_id", how="left") \
           .merge(remot[["cooperative_id", "remoteness_band"]], on="cooperative_id", how="left") \
           .merge(land[["cooperative_id", "in_farmland"]], on="cooperative_id", how="left")

    m["roadless"] = m.km_non_track.isna()
    m["isolated"] = m.remoteness_band == "nobody within 5km"
    m["no_bld_1km"] = m.building_band.isin([NONE_BAND, "< ~2 km", "< ~5 km"])
    m["no_bld_5km"] = m.building_band == NONE_BAND

    cross = {
        "on a building cell (<70 m)": int((m.building_band == "on a building cell (<70 m)").sum()),
        "no mapped building within 1 km": int(m.no_bld_1km.sum()),
        "  ... but people nearby per Kontur (within 5 km)": int((m.no_bld_1km & ~m.isolated).sum()),
        "  ... and isolated (Kontur: nobody within 5 km)": int((m.no_bld_1km & m.isolated).sum()),
        "  ... and isolated + roadless": int((m.no_bld_1km & m.isolated & m.roadless).sum()),
        "  ... and isolated + recorded in farmland": int((m.no_bld_1km & m.isolated & m.in_farmland).sum()),
        "  ... and isolated + roadless + farmland": int((m.no_bld_1km & m.isolated & m.roadless & m.in_farmland).sum()),
        "no mapped building within 5 km": int(m.no_bld_5km.sum()),
        "  ... and isolated (5 km set)": int((m.no_bld_5km & m.isolated).sum()),
        "  ... and roadless (5 km set)": int((m.no_bld_5km & m.roadless).sum()),
        "  ... and recorded in farmland": int((m.no_bld_5km & m.in_farmland).sum()),
    }
    print("\ncross-tabs (no mapped building):")
    for k, v in cross.items():
        print(f"  {k}: {v:,}")
    write_csv(pd.DataFrame(list(cross.items()), columns=["case", "n"]),
              OUT / "building_overlap.csv", "no-mapped-building cases vs roadless/isolated/farmland")

    print(f"\nwrote outputs to {OUT}")


if __name__ == "__main__":
    main()
