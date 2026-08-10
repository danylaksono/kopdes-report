#!/usr/bin/env python3
"""
08-exact-geometry - replace the H3 ring bands of 05 and 06 with true distances.

Reports 05 and 06 rasterise roads and shops into H3 cells and grow rings
outward. That is the right way to sort 83,342 cooperatives into bands quickly,
and the wrong thing to put in a sentence about a named village. Ring distance is
hex-grid distance: quantised to ~132 m, with directional error, and capped at
whatever k the search stopped at. A narrative needs "the nearest road is 7.4 km
away", not "in the >5 km band".

So: **H3 to rank, exact geometry to report.**

Three parts
-----------
A. **Roads, for the shortlist that matters.** 05's headline set - cooperatives
   with no made road within ~5 km - gets a real number. Nearest-neighbour
   against 4.5M LineStrings is avoided the same way 05 avoided it, but in
   reverse: the cached r10 road-cell index is rolled up to r6 (35,036 cells),
   an STRtree over those centres gives each point a *bound* on how far its
   nearest road can be, and that bound sizes a bbox-filtered read of the
   GeoPackage. Only a few hundred LineStrings are ever in memory at once.

B. **Retail, for everybody.** Minimarkets are 10,580 points in a 1.7 MB file, so
   there is no reason to approximate at all: one STRtree, exact distance for all
   83,342 cooperatives. This removes 06's ~5 km search cap entirely - 66,846
   cooperatives had a null there, meaning "further than 5 km", and now have a
   number.

C. **How wrong was the ring approximation?** Both parts above overlap with
   published band figures, so the error is measurable rather than assumed. If
   the bands hold up, 05 and 06 can be cited as they stand; if they do not, this
   report is the correction.

On distance, precisely
----------------------
- The bbox is a *fetch window*, not a buffer. It is computed in degrees (with a
  cos-latitude correction on longitude) and deliberately generous, because its
  only job is to be large enough. Nothing is measured in degrees.
- Every reported distance is **geodesic** (`pyproj.Geod`, WGS84) from the point
  to the nearest point on the actual geometry, via `shapely.shortest_line`.
- **Do not over-promise.** OSM road geometry is good to roughly 5-15 m and worse
  for rural tracks, so metres are meaningful and centimetres are theatre.
  Everything is rounded to 1 m and should be quoted to the nearest 100 m.

Requires data/osm/indonesia_roads.gpkg, data/osm/indonesia_minimarkets.gpkg and
the r10 cell index cached by 05.

Usage:
  python reports/08-exact-geometry/run.py
  python reports/08-exact-geometry/run.py --sample 800   # ring-vs-exact check size
  python reports/08-exact-geometry/run.py --skip-roads   # part B and C-retail only
"""

import argparse
import math
import sys
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pyogrio
import shapely
from pyproj import Geod
from shapely import STRtree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.common import RAW, ROOT, out_dir, write_csv  # noqa: E402

OUT = out_dir(__file__)
ROADS_GPKG = ROOT / "data" / "osm" / "indonesia_roads.gpkg"
MINIMARKETS = ROOT / "data" / "osm" / "indonesia_minimarkets.gpkg"
CELL_INDEX = ROOT / "data" / "osm" / "road_cells_h3r10.parquet"
ROAD_ACCESS = ROOT / "reports" / "05-road-access" / "kopdes_road_access.csv"
RETAIL = ROOT / "reports" / "06-minimarket-proximity" / "kopdes_minimarket_distance.csv"

GEOD = Geod(ellps="WGS84")
NON_ROAD_CLASSES = {"track"}

# Indonesia's envelope, generously drawn. Only used to *find* impossible
# coordinates, never to clip anything.
ID_BBOX = (94.5, -11.5, 141.5, 6.5)

# An r6 cell is ~3.2 km edge, so its centre can be ~3.7 km from anything inside
# it. Two cells of slack plus a kilometre covers the worst case comfortably.
R6_SLACK_KM = 8.0
MAX_RADIUS_KM = 250.0     # beyond this the bbox read stops being worth it


def geodesic_to(pts, lon, lat, targets):
    """
    True metres from each point to the nearest point on its target geometry.

    `shapely.shortest_line` is vectorised and returns the connecting segment;
    its far end is the nearest point on the target, which Geod then measures on
    the ellipsoid. (07 carries an inline twin of this; if a third report needs
    it, it belongs in reports/_lib.)
    """
    lines = shapely.shortest_line(pts, targets)
    ok = shapely.get_num_coordinates(lines) == 2
    dist = np.full(len(pts), np.nan)
    if ok.any():
        far = shapely.get_coordinates(lines[ok])[1::2]
        dist[ok] = GEOD.inv(lon[ok], lat[ok], far[:, 0], far[:, 1])[2]
    return np.abs(dist)


def load_06_tiering():
    """
    Reuse 06's retail tiering instead of re-deriving it.

    06 does not measure "any shop": it repairs brand spellings the extractor
    missed, splits off traditional warung, and keeps only tier-1
    convenience/minimarket POIs - 7,617 of the 10,580 in the GeoPackage.
    Measuring against all 10,580 here would produce numbers that look like a
    correction to 06 while actually answering a different question.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "minimarket_proximity", ROOT / "reports" / "06-minimarket-proximity" / "run.py"
    )
    mod = importlib.util.module_from_spec(spec)
    saved, sys.argv = sys.argv, ["run"]
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.argv = saved
    return mod


def check_coordinates(loc):
    """
    Find coordinates that cannot be where they claim to be, and test the obvious
    explanation.

    Anything outside Indonesia's envelope is impossible by definition. For each,
    compare the distance to its own claimed province centroid as recorded
    against the distance with the latitude sign flipped. If flipping moves it
    from the other side of the planet to inside its own province, the record is
    a sign error, not a mystery.
    """
    prov = pd.read_csv(RAW / "kopdes_stats_province.csv")[
        ["province", "latitude", "longitude"]].rename(
        columns={"latitude": "plat", "longitude": "plon"})
    lo, la, hi_lo, hi_la = ID_BBOX
    bad = loc[~loc.longitude.between(lo, hi_lo) | ~loc.latitude.between(la, hi_la)].copy()
    bad = bad.merge(prov, on="province", how="left")
    bad["km_as_recorded"] = np.round(
        GEOD.inv(bad.longitude, bad.latitude, bad.plon, bad.plat)[2] / 1000)
    bad["km_if_latitude_flipped"] = np.round(
        GEOD.inv(bad.longitude, -bad.latitude, bad.plon, bad.plat)[2] / 1000)
    # A flip that lands within 500 km of a province centroid is a flip; province
    # centroids are coarse, so this threshold is deliberately loose.
    bad["diagnosis"] = np.where(
        (bad.km_if_latitude_flipped < bad.km_as_recorded) & (bad.km_if_latitude_flipped < 500),
        "latitude sign flipped", "unexplained - coordinate is garbage")
    return bad


def bbox_for(lat, lon, radius_km):
    """Fetch window in degrees. Longitude is scaled by cos(latitude)."""
    dlat = radius_km / 111.32
    dlon = radius_km / (111.32 * max(math.cos(math.radians(lat)), 0.2))
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def radius_bounds(con, df):
    """
    Per-point upper bound on the distance to the nearest road, from the H3 index.

    The r10 road cells are rolled up to r6 and their centres put in an STRtree.
    The nearest r6 centre plus two cells of slack is guaranteed to enclose at
    least one road, which is exactly what the bbox needs to be big enough to do.
    Non-track cells are used, because that is the harder of the two searches; any
    road is a superset and is therefore also inside the window.
    """
    cells = con.execute(f"""
        select distinct h3_cell_to_parent(h3, 6) as c
        from read_parquet('{CELL_INDEX.as_posix()}') where non_track
    """).fetchdf()
    con.register("cells_v", cells)
    ll = con.execute(
        "select h3_cell_to_lat(c) as lat, h3_cell_to_lng(c) as lon from cells_v"
    ).fetchdf()
    print(f"  bound grid: {len(ll):,} r6 cells carrying a non-track road")

    tree = STRtree(shapely.points(ll.lon.to_numpy(), ll.lat.to_numpy()))
    pts = shapely.points(df.longitude.to_numpy(), df.latitude.to_numpy())
    res = np.atleast_2d(tree.query_nearest(pts, all_matches=False))
    idx = np.full(len(df), -1, dtype=np.int64)
    idx[res[0]] = res[1]
    d = geodesic_to(pts, df.longitude.to_numpy(), df.latitude.to_numpy(),
                    shapely.points(ll.lon.to_numpy(), ll.lat.to_numpy())[idx])
    return np.minimum(d / 1000.0 + R6_SLACK_KM, MAX_RADIUS_KM)


def exact_road_distance(df, radius_km, label):
    """
    One bbox-filtered read per point, then exact geodesic distance to the
    nearest LineString - reported separately for any road and for made roads.

    The window doubles and retries if it comes back empty, which happens when
    the H3 bound was optimistic (a cell can hold a road that is still outside a
    tight window).
    """
    out = {}
    t0 = time.time()
    for n, (i, row) in enumerate(df.iterrows(), 1):
        r = float(radius_km[n - 1])
        got = None
        for _ in range(4):
            local = pyogrio.read_dataframe(
                ROADS_GPKG, columns=["highway"], bbox=bbox_for(row.latitude, row.longitude, r)
            )
            if len(local):
                got = local
                break
            r = min(r * 2, MAX_RADIUS_KM)
            if r >= MAX_RADIUS_KM:
                break
        if got is None or not len(got):
            continue
        pt = shapely.points([row.longitude], [row.latitude])
        lon = np.array([row.longitude]); lat = np.array([row.latitude])
        geoms = got.geometry.to_numpy()

        def nearest(sel):
            if not sel.any():
                return np.nan
            sub = geoms[sel]
            t = STRtree(sub)
            j = np.atleast_2d(t.query_nearest(pt, all_matches=False))[1][0]
            return float(geodesic_to(pt, lon, lat, np.array([sub[j]]))[0])

        made = (~got.highway.isin(NON_ROAD_CLASSES)).to_numpy()
        out[i] = (nearest(np.ones(len(geoms), bool)), nearest(made), r)
        if n % 250 == 0:
            print(f"    {label}: {n:>5,}/{len(df):,}  ({time.time()-t0:.0f}s)")
    print(f"    {label}: done {len(out):,}/{len(df):,} in {time.time()-t0:.0f}s")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=800,
                    help="how many band-resolved points to re-measure for part C")
    ap.add_argument("--skip-roads", action="store_true")
    args = ap.parse_args()

    for p in (ROADS_GPKG, MINIMARKETS, CELL_INDEX):
        if not p.exists() and not (args.skip_roads and p is not MINIMARKETS):
            sys.exit(f"missing {p}\n  see reports/05-road-access/run.py and scripts/download_osm.py")

    loc = pd.read_csv(RAW / "kopdes_locations.csv")
    con = duckdb.connect()
    con.execute("install h3 from community; load h3;")

    # ---------------------------------------------------------------- part D --
    # Coordinate validity, first, because it decides which rows may appear in
    # any summary below.
    suspect = check_coordinates(loc)
    print(f"part D - coordinate validity: {len(suspect)} cooperatives are outside "
          f"Indonesia entirely")
    print(suspect.diagnosis.value_counts().to_string())
    write_csv(suspect[["cooperative_id", "name", "province", "district", "subdistrict",
                       "latitude", "longitude", "km_as_recorded",
                       "km_if_latitude_flipped", "diagnosis"]],
              OUT / "suspect_coordinates.csv", "impossible coordinates and their diagnosis")
    bad_ids = set(suspect.cooperative_id)

    # ---------------------------------------------------------------- part B --
    # Retail: exact for everybody and costs nothing.
    print("\npart B - exact distance to the nearest mapped minimarket, all cooperatives")
    s06 = load_06_tiering()
    mm = pyogrio.read_dataframe(MINIMARKETS)
    mm = mm[mm.geometry.geom_type == "Point"]
    mm = s06.reclassify(mm)
    mm = mm[mm.tier == s06.TIER_CONVENIENCE].reset_index(drop=True)
    print(f"  {len(mm):,} tier-1 convenience/minimarket POIs (06's definition, not all "
          f"shops - see load_06_tiering)")
    mtree = STRtree(mm.geometry.to_numpy())
    pts = shapely.points(loc.longitude.to_numpy(), loc.latitude.to_numpy())
    res = np.atleast_2d(mtree.query_nearest(pts, all_matches=False))
    idx = np.full(len(loc), -1, dtype=np.int64)
    idx[res[0]] = res[1]
    dist = geodesic_to(pts, loc.longitude.to_numpy(), loc.latitude.to_numpy(),
                       mm.geometry.to_numpy()[idx])
    retail = loc[["cooperative_id", "province", "district", "subdistrict",
                  "latitude", "longitude"]].copy()
    retail["m_to_minimarket"] = np.round(dist, 1)
    retail["nearest_minimarket"] = mm.name.to_numpy()[idx]
    retail["nearest_brand"] = mm.brand_label.to_numpy()[idx]
    retail["coordinate_suspect"] = retail.cooperative_id.isin(bad_ids)
    write_csv(retail, OUT / "exact_minimarket_distance.csv",
              "all 83,342; supersedes 06's capped ring distance")

    # Every summary below excludes the impossible coordinates. Leaving them in
    # would put a 9,000 km maximum in a table about village shops.
    clean = retail[~retail.coordinate_suspect]
    cd = clean.m_to_minimarket.to_numpy()
    print(f"  median {np.median(cd)/1000:.2f} km, max {np.max(cd)/1000:.0f} km "
          f"({len(retail)-len(clean)} impossible coordinates excluded)")

    bands = pd.DataFrame({
        "within": ["100 m", "250 m", "500 m", "1 km", "2 km", "5 km", "10 km", "beyond 10 km"],
        "cooperatives": [
            int((cd <= t).sum()) for t in (100, 250, 500, 1000, 2000, 5000, 10000)
        ] + [int((cd > 10000).sum())],
    })
    bands["pct"] = (100 * bands.cooperatives / len(clean)).round(2)
    print(bands.to_string(index=False))
    write_csv(bands, OUT / "exact_minimarket_bands.csv")

    # ---------------------------------------------------------------- part C --
    # Retail half of the validation, free: 06 resolved 16,496 within its cap.
    checks = []
    if RETAIL.exists():
        ring = pd.read_csv(RETAIL).rename(columns={"id": "cooperative_id"})
        cmp = clean.merge(ring[["cooperative_id", "km_to_minimarket"]], on="cooperative_id")
        cmp = cmp[cmp.km_to_minimarket.notna()].copy()
        cmp["ring_m"] = cmp.km_to_minimarket * 1000
        cmp["error_m"] = cmp.ring_m - cmp.m_to_minimarket
        checks.append({
            "comparison": "06 minimarket ring vs exact",
            "points": len(cmp),
            "median_exact_m": round(float(cmp.m_to_minimarket.median()), 1),
            "median_error_m": round(float(cmp.error_m.median()), 1),
            "median_abs_error_m": round(float(cmp.error_m.abs().median()), 1),
            "p90_abs_error_m": round(float(cmp.error_m.abs().quantile(0.9)), 1),
            "pct_within_132m": round(100 * float((cmp.error_m.abs() <= 132).mean()), 1),
        })
        print(f"\npart C - 06 ring vs exact on {len(cmp):,} resolved points: "
              f"median abs error {cmp.error_m.abs().median():.0f} m")
    else:
        print(f"\n  note: {RETAIL.name} missing - skipping the retail validation")

    if args.skip_roads:
        write_csv(pd.DataFrame(checks), OUT / "ring_vs_exact_agreement.csv")
        return

    # ---------------------------------------------------------------- part A --
    if not ROAD_ACCESS.exists():
        sys.exit(f"missing {ROAD_ACCESS}\n  run: python reports/05-road-access/run.py")
    road = pd.read_csv(ROAD_ACCESS)
    far = road[road.km_non_track.isna()].copy()          # no made road within ~5 km
    print(f"\npart A - exact road distance for the {len(far):,} with no made road "
          f"within ~5 km (05's headline set)")
    bound = radius_bounds(con, far)
    print(f"  bbox radius: median {np.median(bound):.0f} km, max {np.max(bound):.0f} km")
    got = exact_road_distance(far, bound, "far set")

    far["m_to_any_road"] = [got.get(i, (np.nan,) * 3)[0] for i in far.index]
    far["m_to_made_road"] = [got.get(i, (np.nan,) * 3)[1] for i in far.index]
    far["km_to_made_road"] = (far.m_to_made_road / 1000).round(2)
    far = far.sort_values("m_to_made_road", ascending=False)
    write_csv(far, OUT / "exact_road_distance_far_set.csv",
              "exact geodesic distance for 05's no-made-road set")

    ok = far.m_to_made_road.notna()
    print(f"\n  resolved {int(ok.sum()):,}/{len(far):,}")
    print(f"  median exact distance to a made road: {far.loc[ok,'km_to_made_road'].median():.1f} km")
    print(f"  90th percentile: {far.loc[ok,'km_to_made_road'].quantile(0.9):.1f} km, "
          f"max {far.loc[ok,'km_to_made_road'].max():.0f} km")
    dist_bands = pd.DataFrame({
        "exact distance to nearest made road": ["5-10 km", "10-25 km", "25-50 km",
                                                "50-100 km", "over 100 km"],
        "cooperatives": [
            int(((far.km_to_made_road > 5) & (far.km_to_made_road <= 10)).sum()),
            int(((far.km_to_made_road > 10) & (far.km_to_made_road <= 25)).sum()),
            int(((far.km_to_made_road > 25) & (far.km_to_made_road <= 50)).sum()),
            int(((far.km_to_made_road > 50) & (far.km_to_made_road <= 100)).sum()),
            int((far.km_to_made_road > 100).sum()),
        ],
    })
    print()
    print(dist_bands.to_string(index=False))
    write_csv(dist_bands, OUT / "exact_road_distance_bands.csv")

    # Roads half of the validation: re-measure a random sample whose ring band
    # 05 did resolve, and see whether k * 132 m was telling the truth.
    resolved = road[road.km_non_track.notna()]
    samp = resolved.sample(min(args.sample, len(resolved)), random_state=20260810).copy()
    print(f"\npart C - re-measuring {len(samp):,} band-resolved points against exact geometry")
    sb = np.minimum(samp.km_non_track.to_numpy() + 3.0, MAX_RADIUS_KM)
    sgot = exact_road_distance(samp, sb, "sample")
    samp["m_to_made_road"] = [sgot.get(i, (np.nan,) * 3)[1] for i in samp.index]
    s = samp[samp.m_to_made_road.notna()].copy()
    s["ring_m"] = s.km_non_track * 1000
    s["error_m"] = s.ring_m - s.m_to_made_road
    checks.append({
        "comparison": "05 road ring vs exact",
        "points": len(s),
        "median_exact_m": round(float(s.m_to_made_road.median()), 1),
        "median_error_m": round(float(s.error_m.median()), 1),
        "median_abs_error_m": round(float(s.error_m.abs().median()), 1),
        "p90_abs_error_m": round(float(s.error_m.abs().quantile(0.9)), 1),
        "pct_within_132m": round(100 * float((s.error_m.abs() <= 132).mean()), 1),
    })
    write_csv(s[["cooperative_id", "province", "district", "km_non_track",
                 "m_to_made_road", "error_m"]], OUT / "ring_vs_exact_sample.csv")

    agree = pd.DataFrame(checks)
    print()
    print(agree.to_string(index=False))
    write_csv(agree, OUT / "ring_vs_exact_agreement.csv")


if __name__ == "__main__":
    main()
