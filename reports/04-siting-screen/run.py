#!/usr/bin/env python3
"""
04-siting-screen - find KDMP that look physically implausible as village shops.

The public critique ("built on a graveyard / in the middle of a paddy field /
on top of a hill") is an existence claim, not a distributional one. A handful
of well-evidenced cases makes the point; a national average does not. So this
is a *screening* tool: it ranks 83k cooperatives by how implausible their
surroundings look, so that a human only has to eyeball the top of the list.

Two stages, because the cheap signal is free and the expensive one is not:

  Stage A (free, offline, all 83k): population in the cell and its neighbours,
      from reports/03-population-coverage/kopdes_remoteness.csv.
  Stage B (cloud rasters, shortlist only): elevation, local relief and land
      cover, point-sampled straight out of Copernicus GLO-30 and ESA
      WorldCover COGs on S3. No nationwide download - GDAL issues HTTP range
      requests for the few KB around each point.

Stage B is why "nationwide terrain analysis" is not the huge task it sounds
like: you never process a raster, you sample it. Restricting it to a shortlist
keeps it to minutes rather than hours.

*** These are candidates, not findings. ***
A flag means "the surroundings are not what a village shop should look like",
which has two causes that this script cannot distinguish: genuinely bad siting,
or a wrong coordinate in SIMKOPDES. Both are worth reporting - they are
different stories - but each case needs eyeballing against imagery before it is
written up. The output carries a maps link per row for exactly that.

Usage:
  python reports/04-siting-screen/run.py              # top 500 shortlist
  python reports/04-siting-screen/run.py --top 3000   # wider net, slower
  python reports/04-siting-screen/run.py --skip-rasters   # stage A only
"""

import argparse
import math
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.common import RAW, ROOT, out_dir, write_csv  # noqa: E402

OUT = out_dir(__file__)
REMOTENESS = ROOT / "reports" / "03-population-coverage" / "kopdes_remoteness.csv"

os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")

WORLDCOVER = {
    10: "Tree cover", 20: "Shrubland", 30: "Grassland", 40: "Cropland",
    50: "Built-up", 60: "Bare / sparse", 70: "Snow & ice", 80: "Water",
    90: "Herbaceous wetland", 95: "Mangrove", 100: "Moss & lichen",
}
# What a village cooperative shop should be sitting on. Anything else is a
# question worth asking - Cropland most of all, since that is the "dibangun di
# tengah sawah" claim.
PLAUSIBLE_COVER = {50}                      # Built-up
QUESTIONABLE_COVER = {40, 30, 20}           # Cropland, grass, shrub
IMPLAUSIBLE_COVER = {10, 60, 80, 90, 95}    # forest, bare, water, wetland, mangrove


def dem_url(lat, lon):
    ns, ew = ("N", "S")[lat < 0], ("E", "W")[lon < 0]
    la = int(math.floor(abs(lat))) if lat >= 0 else int(math.ceil(abs(lat)))
    lo = int(math.floor(abs(lon))) if lon >= 0 else int(math.ceil(abs(lon)))
    if lat < 0:
        la = int(math.ceil(abs(lat)))
    name = f"Copernicus_DSM_COG_10_{ns}{la:02d}_00_{ew}{lo:03d}_00_DEM"
    return f"/vsicurl/https://copernicus-dem-30m.s3.amazonaws.com/{name}/{name}.tif"


def cover_url(lat, lon):
    la, lo = math.floor(lat / 3) * 3, math.floor(lon / 3) * 3
    ns, ew = ("N", "S")[la < 0], ("E", "W")[lo < 0]
    name = f"ESA_WorldCover_10m_2021_v200_{ns}{abs(la):02d}{ew}{abs(lo):03d}_Map"
    return f"https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/{name}.tif"


def dem_key(lat, lon):
    return (math.ceil(lat) if lat < 0 else math.floor(lat), math.floor(lon))


def cover_key(lat, lon):
    return (math.floor(lat / 3) * 3, math.floor(lon / 3) * 3)


def sample_tile(url, points, window_px):
    """
    Sample one raster tile at many points.

    `points` is [(idx, lon, lat), ...]. Returns {idx: (centre_value, relief)}
    where relief is max-min over a small window - the cheap "is this a slope or
    a hilltop" proxy. Reading a window rather than a pixel costs the same one
    HTTP range request.
    """
    import rasterio

    got = {}
    try:
        with rasterio.open(url) as ds:
            half = window_px // 2
            for idx, lon, lat in points:
                try:
                    row, col = ds.index(lon, lat)
                    win = rasterio.windows.Window(col - half, row - half, window_px, window_px)
                    arr = ds.read(1, window=win, boundless=True, fill_value=ds.nodata or 0)
                    if arr.size == 0:
                        continue
                    centre = arr[half, half] if arr.shape[0] > half and arr.shape[1] > half else arr.flat[0]
                    got[idx] = (float(centre), float(np.nanmax(arr) - np.nanmin(arr)))
                except Exception:
                    continue
    except Exception:
        pass
    return got


def sample_all(df, url_fn, key_fn, window_px, label, workers=8):
    groups = defaultdict(list)
    for idx, lon, lat in zip(df.index, df.longitude, df.latitude):
        groups[key_fn(lat, lon)].append((idx, lon, lat))
    print(f"  {label}: {len(df):,} points across {len(groups)} tiles")

    results = {}
    done = 0

    def work(item):
        (klat, klon), pts = item
        lat, lon = pts[0][2], pts[0][1]
        return sample_tile(url_fn(lat, lon), pts, window_px)

    with ThreadPoolExecutor(workers) as pool:
        for got in pool.map(work, groups.items()):
            results.update(got)
            done += 1
            if done % 25 == 0:
                print(f"    {done}/{len(groups)} tiles, {len(results):,} points sampled")
    print(f"    done: {len(results):,}/{len(df):,} points resolved")
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=500, help="shortlist size for raster sampling")
    ap.add_argument("--skip-rasters", action="store_true")
    args = ap.parse_args()

    if not REMOTENESS.exists():
        sys.exit(f"missing {REMOTENESS}\n  run: python reports/03-population-coverage/run.py")

    per = pd.read_csv(REMOTENESS)
    popcol = next(c for c in per.columns if c.startswith("pop_within_1"))
    far_col = next(c for c in per.columns if c.startswith("pop_within_5"))

    # --- Stage A: free signal, everybody -------------------------------------
    per["isolation_score"] = (
        (per.own_cell_pop == 0).astype(int) * 2
        + (per[popcol].fillna(0) < 100).astype(int) * 2
        + (per[far_col].fillna(0) < 1000).astype(int)
    )
    stage_a = (
        per.groupby("isolation_score")
        .size()
        .rename("cooperatives")
        .reset_index()
        .sort_values("isolation_score", ascending=False)
    )
    print("Stage A - isolation score (free, all cooperatives)\n")
    print(stage_a.to_string(index=False))
    write_csv(stage_a, OUT / "stage_a_isolation_distribution.csv")

    # Land-asset status is the other half of the story: a cooperative whose
    # land was signed off as "Terverifikasi" while sitting in open water is a
    # much sharper finding than an unverified one. The only join key between
    # locations and land assets is the cooperative name (see
    # analytics-plan-review.md §1.5), so pull the name back in first.
    names = pd.read_csv(RAW / "kopdes_locations.csv")[["cooperative_id", "name"]]
    assets = pd.read_csv(RAW / "kopdes_land_assets.csv").drop_duplicates("cooperative")
    per = per.merge(names, on="cooperative_id", how="left").merge(
        assets[["cooperative", "village", "status", "surveyor"]].rename(
            columns={"status": "land_status", "surveyor": "land_surveyor"}
        ),
        left_on="name", right_on="cooperative", how="left",
    ).drop(columns=["cooperative"])

    shortlist = per.sort_values(
        ["isolation_score", "own_cell_pop", popcol], ascending=[False, True, True]
    ).head(args.top).copy()

    if args.skip_rasters:
        write_csv(shortlist, OUT / "candidates.csv", "stage A only, no raster attributes")
        return

    # --- Stage B: cloud rasters, shortlist only ------------------------------
    print(f"\nStage B - sampling cloud rasters for the top {len(shortlist):,}\n")
    dem = sample_all(shortlist, dem_url, dem_key, window_px=7, label="Copernicus GLO-30 DEM")
    cov = sample_all(shortlist, lambda a, b: cover_url(a, b), cover_key, window_px=5,
                     label="ESA WorldCover 10m")

    shortlist["elevation_m"] = [dem.get(i, (np.nan, np.nan))[0] for i in shortlist.index]
    shortlist["relief_200m_m"] = [dem.get(i, (np.nan, np.nan))[1] for i in shortlist.index]
    shortlist["landcover_code"] = [int(cov[i][0]) if i in cov else np.nan for i in shortlist.index]
    shortlist["landcover"] = shortlist.landcover_code.map(WORLDCOVER)

    shortlist["flag_no_population"] = shortlist.own_cell_pop == 0
    shortlist["flag_implausible_cover"] = shortlist.landcover_code.isin(IMPLAUSIBLE_COVER)
    shortlist["flag_cropland"] = shortlist.landcover_code == 40
    shortlist["flag_steep"] = shortlist.relief_200m_m > 60          # >60 m over ~200 m
    shortlist["flag_not_builtup"] = ~shortlist.landcover_code.isin(PLAUSIBLE_COVER)
    flags = [c for c in shortlist.columns if c.startswith("flag_")]
    shortlist["n_flags"] = shortlist[flags].sum(axis=1)

    shortlist["imagery_url"] = [
        f"https://www.google.com/maps/@{lat},{lon},250m/data=!3m1!1e3"
        for lat, lon in zip(shortlist.latitude, shortlist.longitude)
    ]
    shortlist = shortlist.sort_values(["n_flags", "isolation_score"], ascending=False)

    write_csv(shortlist, OUT / "candidates.csv", "ranked; verify against imagery before citing")

    print("\nland cover of the shortlist:")
    print(shortlist.landcover.value_counts(dropna=False).to_string())
    print("\nflag counts:")
    print(shortlist[flags].sum().sort_values(ascending=False).to_string())
    summary = pd.DataFrame(
        {"flag": flags, "cooperatives": [int(shortlist[f].sum()) for f in flags]}
    ).sort_values("cooperatives", ascending=False)
    write_csv(summary, OUT / "flag_summary.csv")


if __name__ == "__main__":
    main()
