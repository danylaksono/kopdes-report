#!/usr/bin/env python3
"""
03-population-coverage - how much of Indonesia is within reach of a KDMP, and
which KDMP sit nowhere near anyone?

Uses the DuckDB + H3-parquet pattern: Kontur's 400m population grid is already
H3 (resolution 8), so dropping its geometry turns a 172 MB GPKG into a ~3 MB
parquet and every spatial question becomes a hash join on the cell id. No
PostGIS, no geometry, no raster.

Two numbers come out of this that pull in opposite directions:
  - coverage:   what share of the population has a KDMP nearby (very high)
  - remoteness: how many KDMP have nobody near them (the placement critique)

Requires data/population/kontur_population_ID.gpkg (gitignored - see
scripts/download_population.py). Writes population_h3.parquet next to it on
first run, so subsequent runs skip the GPKG entirely.

Usage: python reports/03-population-coverage/run.py
"""

import sys
import time
from pathlib import Path

import duckdb
import h3
import pandas as pd
import pyogrio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.common import RAW, ROOT, out_dir, write_csv  # noqa: E402

OUT = out_dir(__file__)
GPKG = ROOT / "data" / "population" / "kontur_population_ID.gpkg"
PARQUET = ROOT / "data" / "population" / "population_h3.parquet"

RES = 8  # Kontur 400m IS H3 r8 - do not resample, it only loses precision

# k-ring radius -> approximate ground distance. An r8 cell is ~0.46 km across,
# so k rings reach roughly 0.46*k km from the centre cell.
RINGS = [(0, 0.2), (1, 0.5), (3, 1.4), (6, 2.8), (11, 5.1)]


def ensure_parquet():
    if PARQUET.exists():
        return
    if not GPKG.exists():
        sys.exit(f"missing {GPKG}\n  run: python scripts/download_population.py")
    print(f"converting {GPKG.name} -> {PARQUET.name} (one time)...")
    pop = pyogrio.read_dataframe(GPKG, read_geometry=False)
    pop.to_parquet(PARQUET, index=False, compression="zstd")
    print(f"  {GPKG.stat().st_size/1e6:.1f} MB gpkg -> {PARQUET.stat().st_size/1e6:.1f} MB parquet")


def main():
    ensure_parquet()

    con = duckdb.connect()
    con.execute(f"create table pop as select * from read_parquet('{PARQUET.as_posix()}')")
    total_pop, n_cells = con.execute("select sum(population), count(*) from pop").fetchone()
    print(f"population grid: {n_cells:,} H3 r{RES} cells, {total_pop:,.0f} people\n")

    loc = pd.read_csv(RAW / "kopdes_locations.csv")
    loc["h3_8"] = [h3.latlng_to_cell(a, b, RES) for a, b in zip(loc.latitude, loc.longitude)]
    con.register("kop", loc[["cooperative_id", "province", "district", "subdistrict", "h3_8"]])

    # --- coverage: union of catchments. Catchments overlap heavily, so this
    # MUST be a distinct union - summing per-cooperative catchment populations
    # double-counts by more than an order of magnitude.
    rows = []
    for k, km in RINGS:
        t0 = time.time()
        cells = {c for cell in loc.h3_8 for c in (h3.grid_disk(cell, k) if k else [cell])}
        con.register("cov", pd.DataFrame({"h3": list(cells)}))
        covered = con.execute("select sum(p.population) from pop p join cov c using (h3)").fetchone()[0]
        rows.append(
            {
                "k_rings": k,
                "approx_km": km,
                "union_cells": len(cells),
                "population_covered": round(covered),
                "pct_of_national": round(100 * covered / total_pop, 2),
                "seconds": round(time.time() - t0, 1),
            }
        )
        print(f"  within ~{km:4.1f} km: {covered:>13,.0f}  = {100*covered/total_pop:5.1f}%")
    write_csv(pd.DataFrame(rows), OUT / "coverage_by_radius.csv")

    # --- remoteness: per-cooperative own-cell population and catchment
    # population. This one legitimately double-counts across cooperatives -
    # never sum the column.
    print("\ncomputing per-cooperative remoteness...")
    per = loc[["cooperative_id", "province", "district", "subdistrict", "latitude", "longitude", "h3_8"]].copy()
    own = con.execute("select h3 as h3_8, population as own_cell_pop from pop").fetchdf()
    per = per.merge(own, on="h3_8", how="left")
    per["own_cell_pop"] = per.own_cell_pop.fillna(0)

    for k, km in [(3, 1.4), (11, 5.1)]:
        rings = pd.DataFrame(
            [(cid, c) for cid, cell in zip(per.cooperative_id, per.h3_8) for c in h3.grid_disk(cell, k)],
            columns=["cooperative_id", "h3"],
        )
        con.register("rings", rings)
        agg = con.execute(
            "select r.cooperative_id, sum(p.population) as pop from rings r "
            "join pop p using (h3) group by 1"
        ).fetchdf()
        per = per.merge(agg.rename(columns={"pop": f"pop_within_{str(km).replace('.','_')}km"}),
                        on="cooperative_id", how="left")

    popcol = [c for c in per.columns if c.startswith("pop_within_5")][0]
    per[popcol] = per[popcol].fillna(0)
    per["remoteness_band"] = pd.cut(
        per[popcol],
        [-1, 0, 500, 2000, 10000, float("inf")],
        labels=["nobody within 5km", "<500", "500-2k", "2k-10k", ">10k"],
    )
    write_csv(per, OUT / "kopdes_remoteness.csv", "per-cooperative; feeds the screengrid views")

    band = (
        per.groupby("remoteness_band", observed=True)
        .agg(cooperatives=("cooperative_id", "size"))
        .assign(pct=lambda d: (100 * d.cooperatives / len(per)).round(2))
        .reset_index()
    )
    print()
    print(band.to_string(index=False))
    write_csv(band, OUT / "remoteness_bands.csv")

    zero = int((per.own_cell_pop == 0).sum())
    print(f"\nKDMP whose own 400m cell has zero recorded population: {zero:,} ({100*zero/len(per):.1f}%)")
    print(f"median own-cell population for the rest: {per.loc[per.own_cell_pop>0,'own_cell_pop'].median():,.0f}")


if __name__ == "__main__":
    main()
