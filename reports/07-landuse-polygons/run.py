#!/usr/bin/env python3
"""
07-landuse-polygons - what is the KDMP actually standing on?

Tests the two specific public accusations that raster land cover cannot reach:

  "dibangun di tanah kuburan"  - built on burial ground. ESA WorldCover has no
      cemetery class, so this is structurally invisible to 04. OSM has the
      polygons.
  "dibangun di tengah sawah"   - built in the middle of a paddy field. 04 found
      exactly 1 cropland case out of 2,500 because it ranks by *isolation*, and
      a shop in a paddy field sits next to a village by construction. This
      screen has no isolation term at all, so it can see them.

It also measures distance to the nearest village centre, place of worship and
marketplace - the first two as an "is this even in a village?" check that does
not depend on Kontur population, the third as groundwork for 08.

Method - point-in-polygon, not raster sampling
----------------------------------------------
Different machinery from 04. These are vector polygons, so:

  1. one pass over the Indonesia PBF with a C++-side TagFilter, assembling
     closed ways and multipolygon relations into areas (~5 min, cached to
     data/osm/indonesia_landuse.parquet - see the AGENTS.md performance note:
     never iterate tags in a Python callback)
  2. an STRtree per class; `query(predicate="within")` answers "is this KDMP
     inside a cemetery?" for all 83k points at once
  3. nearest-neighbour for the misses, refined to true metres

Distances are computed in two steps on purpose. The tree ranks candidates in
degree space, which near the equator is within ~2% of isotropic - fine for
"which polygon is closest", useless as a published number. The winner is then
re-measured geodesically with pyproj.Geod against the actual nearest point on
the geometry. Never buffer in degrees: 0.01 deg is a different distance in Aceh
than in Papua.

*** The asymmetry rule applies to everything here. ***
A hit is strong evidence. A miss is no evidence. OSM maps ~9,200 burial grounds
against ~83,000 desa, so most cemeteries in Indonesia are simply not drawn. This
script can tell you a cooperative IS on a mapped graveyard; it can never tell you
one is not on a graveyard. Every "distance to nearest X" column is an upper
bound on the truth.

Usage:
  python reports/07-landuse-polygons/run.py
  python reports/07-landuse-polygons/run.py --rebuild-index
  python reports/07-landuse-polygons/run.py --skip-rasters   # fully offline
"""

import argparse
import importlib.util
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from pyproj import Geod
from shapely import STRtree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.common import RAW, ROOT, out_dir, write_csv  # noqa: E402

OUT = out_dir(__file__)
PBF = ROOT / "data" / "osm" / "indonesia-latest.osm.pbf"
INDEX = ROOT / "data" / "osm" / "indonesia_landuse.parquet"
REMOTENESS = ROOT / "reports" / "03-population-coverage" / "kopdes_remoteness.csv"
ROAD_ACCESS = ROOT / "reports" / "05-road-access" / "kopdes_road_access.csv"
MINIMARKETS = ROOT / "data" / "osm" / "indonesia_minimarkets.gpkg"

GEOD = Geod(ellps="WGS84")

# tag -> class. Two tags map to `cemetery`: OSM uses landuse=cemetery for the
# grounds and amenity=grave_yard for the (usually smaller) plot beside a place
# of worship. Both are burial ground for our purposes.
TAG_CLASS = {
    ("landuse", "cemetery"): "cemetery",
    ("amenity", "grave_yard"): "cemetery",
    ("landuse", "farmland"): "farmland",
    ("amenity", "marketplace"): "marketplace",
    ("place", "village"): "village",
    ("amenity", "place_of_worship"): "worship",
}
CLASSES = ["cemetery", "farmland", "marketplace", "village", "worship"]

# Classes where "inside the polygon" is the question being asked. A place of
# worship or a village node is a *reference point*, not something you can be
# inside of in any meaningful sense.
PIP_CLASSES = ["cemetery", "farmland", "marketplace"]

# A cooperative counts as "not in a village" if the nearest village centre and
# the nearest place of worship are both further than this. 800 m is a generous
# radius for an Indonesian desa core - most are far tighter.
VILLAGE_CORE_M = 800

# How far inside a farmland polygon a point has to be before "in the middle of
# a field" is a fair description rather than "on the edge of one".
DEEP_IN_FIELD_M = 100

# A farmland polygon containing this many OSM village nodes is not a field, it
# is a coarsely-drawn agricultural *area* with settlements inside it. Depth
# inside such a polygon means nothing, so those hits are marked and excluded
# from the candidate list.
COARSE_POLYGON_VILLAGES = 2


# ---------------------------------------------------------------------------
# Stage 1 - extract the polygons from the PBF (cached)
# ---------------------------------------------------------------------------

def build_index():
    """
    One pass over the 1.73 GB PBF, assembling areas.

    Filtering happens on the C++ side twice: `with_areas(TagFilter)` picks the
    relation candidates during the first pass, `with_filter(TagFilter)` trims
    the output stream. Closed ways come back as both a Way and an Area, so the
    Ways are dropped - the Area carries the assembled geometry.
    """
    import osmium

    if not PBF.exists():
        sys.exit(f"missing {PBF}\n  run: python scripts/download_osm.py --roads-only")

    print(f"extracting land-use features from {PBF.name} (one time, ~5 min)")
    tags = list(TAG_CLASS)
    fp = (
        osmium.FileProcessor(PBF)
        .with_areas(osmium.filter.TagFilter(*tags))
        .with_filter(osmium.filter.TagFilter(*tags))
    )
    fab = osmium.geom.WKBFactory()

    rows, geoms, bad = [], [], 0
    t0 = time.time()
    for obj in fp:
        kind = type(obj).__name__
        if kind == "Way":
            continue  # comes back as an Area with real geometry
        klass = next((c for kv, c in TAG_CLASS.items() if obj.tags.get(kv[0]) == kv[1]), None)
        if klass is None:
            continue
        try:
            if kind == "Area":
                geom = shapely.from_wkb(bytes.fromhex(fab.create_multipolygon(obj)))
                osm_type = "way" if obj.from_way() else "relation"
                osm_id = obj.orig_id()
            elif kind == "Node":
                geom = shapely.Point(obj.location.lon, obj.location.lat)
                osm_type, osm_id = "node", obj.id
            else:
                continue
        except Exception:
            bad += 1
            continue
        rows.append((osm_id, osm_type, klass, obj.tags.get("name") or ""))
        geoms.append(geom)
        if len(rows) % 50_000 == 0:
            print(f"    {len(rows):>7,} features  ({time.time()-t0:.0f}s)")

    gdf = gpd.GeoDataFrame(
        pd.DataFrame(rows, columns=["osm_id", "osm_type", "class", "name"]),
        geometry=geoms,
        crs="EPSG:4326",
    )
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_parquet(INDEX, index=False, compression="zstd")
    print(f"  {len(gdf):,} features ({bad} unbuildable geometries skipped) "
          f"-> {INDEX.stat().st_size/1e6:.0f} MB, {time.time()-t0:.0f}s")
    return gdf


# ---------------------------------------------------------------------------
# Stage 2 - point-in-polygon and exact nearest distance
# ---------------------------------------------------------------------------

def nearest_index(tree, pts):
    """
    Index of the nearest tree geometry for each point, as a plain 1-D array.

    STRtree.query_nearest returns (input_idx, tree_idx) pairs for array input,
    and the pairs are not guaranteed to be in input order, so scatter them back.
    """
    res = tree.query_nearest(pts, all_matches=False)
    res = np.atleast_2d(res)
    out = np.full(len(pts), -1, dtype=np.int64)
    out[res[0]] = res[1]
    return out


def geodesic_to(pts, lon, lat, targets):
    """
    True metres from each point to the nearest point on its target geometry.

    shapely.shortest_line is vectorised and gives the connecting segment; its
    far end is the nearest point on the target. Geod.inv then measures that on
    the ellipsoid. Points that fall inside a polygon get a degenerate segment
    and correctly measure 0.
    """
    lines = shapely.shortest_line(pts, targets)
    ok = shapely.get_num_coordinates(lines) == 2
    far = np.full((len(pts), 2), np.nan)
    if ok.any():
        far[ok] = shapely.get_coordinates(lines[ok])[1::2]
    dist = np.full(len(pts), np.nan)
    m = ok & np.isfinite(far[:, 0])
    if m.any():
        dist[m] = GEOD.inv(lon[m], lat[m], far[m, 0], far[m, 1])[2]
    return np.abs(dist)


def annotate(lon, lat, layers, label):
    """
    For every point: is it inside a polygon of each class, and how far is the
    nearest feature of each class in metres.

    Returns a dict of column -> array, so it can be run over the cooperatives
    and over the null-model points with identical code.
    """
    pts = shapely.points(lon, lat)
    cols = {}
    for klass, (tree, geoms, poly_tree, poly_geoms, poly_meta) in layers.items():
        t0 = time.time()
        if poly_tree is not None:
            inside = np.zeros(len(pts), dtype=bool)
            hit_poly = np.full(len(pts), -1, dtype=np.int64)
            pairs = poly_tree.query(pts, predicate="within")
            inside[pairs[0]] = True
            hit_poly[pairs[0]] = pairs[1]
            cols[f"in_{klass}"] = inside
            cols[f"_{klass}_poly_idx"] = hit_poly  # dropped before writing
            if poly_meta is not None:
                name = np.array([""] * len(pts), dtype=object)
                got = hit_poly >= 0
                name[got] = poly_meta["name"].to_numpy()[hit_poly[got]]
                cols[f"{klass}_name"] = name
                oid = np.full(len(pts), -1, dtype=np.int64)
                oid[got] = poly_meta["osm_id"].to_numpy()[hit_poly[got]]
                cols[f"{klass}_osm_id"] = oid
                # How far inside? Distance to the polygon edge separates "in the
                # middle of a field" from "on the verge of one".
                depth = np.full(len(pts), np.nan)
                if got.any():
                    edges = shapely.boundary(poly_geoms[hit_poly[got]])
                    depth[got] = geodesic_to(pts[got], lon[got], lat[got], edges)
                cols[f"{klass}_depth_m"] = np.round(depth, 1)

        idx = nearest_index(tree, pts)
        found = idx >= 0
        dist = np.full(len(pts), np.nan)
        if found.any():
            dist[found] = geodesic_to(pts[found], lon[found], lat[found], geoms[idx[found]])
        cols[f"dist_{klass}_m"] = np.round(dist, 1)
        n_in = int(cols.get(f"in_{klass}", np.zeros(1, bool)).sum())
        print(f"    {label} / {klass:11} nearest median {np.nanmedian(dist):8,.0f} m"
              f"   inside: {n_in:>6,}   ({time.time()-t0:.0f}s)")
    return cols


def polygon_quality(poly_geoms, hit_idx, village_pts):
    """
    Is the containing polygon a field, or a whole landscape someone drew in one
    go?

    A 4.8 km "depth inside farmland" is only meaningful if that polygon really
    is farmland throughout. Some OSM contributors trace an entire agricultural
    plain as a single `landuse=farmland` way, settlements and all - and a point
    deep inside one of those is not in a field, it is in a village that happens
    to sit within a sloppy polygon. Two cheap tells: the polygon's true
    (geodesic) area, and how many OSM village nodes fall inside it.
    """
    uniq = np.unique(hit_idx[hit_idx >= 0])
    area_km2, n_villages = {}, {}
    vtree = STRtree(village_pts)
    for i in uniq:
        g = poly_geoms[i]
        area_km2[i] = abs(GEOD.geometry_area_perimeter(g)[0]) / 1e6
        n_villages[i] = len(vtree.query(g, predicate="contains"))
    return (
        np.array([area_km2.get(i, np.nan) for i in hit_idx]),
        np.array([n_villages.get(i, -1) for i in hit_idx]),
    )


def load_04_sampler():
    """
    Reuse 04's cloud-raster sampler rather than copy 80 lines of it.

    04/run.py is a script, not a module - it takes its shortlist size from argv
    and guards main() behind __main__, so neutralising argv is enough to import
    it. Importing it also sets the GDAL/vsicurl environment defaults it needs.
    """
    spec = importlib.util.spec_from_file_location(
        "siting_screen", ROOT / "reports" / "04-siting-screen" / "run.py"
    )
    mod = importlib.util.module_from_spec(spec)
    saved, sys.argv = sys.argv, ["run"]
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.argv = saved
    return mod


def build_layers(gdf):
    """One STRtree per class for distance, plus a polygon-only tree for PIP."""
    layers = {}
    for klass in CLASSES:
        sub = gdf[gdf["class"] == klass]
        geoms = sub.geometry.to_numpy()
        polys = sub[sub.geom_type.isin(["Polygon", "MultiPolygon"])]
        if klass in PIP_CLASSES and len(polys):
            layers[klass] = (
                STRtree(geoms), geoms,
                STRtree(polys.geometry.to_numpy()), polys.geometry.to_numpy(),
                polys[["osm_id", "name"]].reset_index(drop=True),
            )
        else:
            layers[klass] = (STRtree(geoms), geoms, None, None, None)
        print(f"  {klass:11} {len(sub):>7,} features "
              f"({len(polys):,} polygons, {len(sub)-len(polys):,} points)")
    return layers


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild-index", action="store_true")
    ap.add_argument("--skip-rasters", action="store_true",
                    help="skip the WorldCover cross-check (the only network step)")
    args = ap.parse_args()

    if INDEX.exists() and not args.rebuild_index:
        gdf = gpd.read_parquet(INDEX)
        print(f"land-use index: {len(gdf):,} OSM features (cached)")
    else:
        gdf = build_index()

    print()
    layers = build_layers(gdf)

    # --- the cooperatives -----------------------------------------------------
    loc = pd.read_csv(RAW / "kopdes_locations.csv")
    print(f"\nscreening {len(loc):,} cooperatives")
    lon = loc.longitude.to_numpy(dtype=float)
    lat = loc.latitude.to_numpy(dtype=float)
    per = loc[["cooperative_id", "name", "province", "district", "subdistrict",
               "latitude", "longitude"]].rename(columns={"name": "cooperative"})
    cols = annotate(lon, lat, layers, "kdmp")
    farmland_idx = cols.pop("_farmland_poly_idx")
    for col, val in cols.items():
        if not col.startswith("_"):
            per[col] = val

    # Is the containing farmland polygon a field or a whole plain? Without this
    # the depth column reads as precision it does not have.
    village_pts = gdf[(gdf["class"] == "village") & (gdf.geom_type == "Point")].geometry.to_numpy()
    farm_polys = gdf[(gdf["class"] == "farmland")
                     & gdf.geom_type.isin(["Polygon", "MultiPolygon"])].geometry.to_numpy()
    area_km2, n_vil = polygon_quality(farm_polys, farmland_idx, village_pts)
    per["farmland_polygon_km2"] = np.round(area_km2, 3)
    per["farmland_polygon_villages"] = n_vil
    per["farmland_polygon_coarse"] = n_vil >= COARSE_POLYGON_VILLAGES

    # Nearest *village core* proxy: whichever of the two independent references
    # is closer. Kontur is not involved, so this is a genuinely separate check
    # on 03's population-based remoteness.
    per["dist_village_core_m"] = per[["dist_village_m", "dist_worship_m"]].min(axis=1)
    per["outside_village_core"] = per.dist_village_core_m > VILLAGE_CORE_M

    # Land-asset status, joined by name - the only key there is (see
    # analytics-plan-review.md 1.5). A verified land asset inside a graveyard
    # is a far sharper finding than an unverified one.
    assets = pd.read_csv(RAW / "kopdes_land_assets.csv").drop_duplicates("cooperative")
    per = per.merge(
        assets[["cooperative", "status", "surveyor"]].rename(
            columns={"status": "land_status", "surveyor": "land_surveyor"}),
        on="cooperative", how="left",
    )

    if REMOTENESS.exists():
        rem = pd.read_csv(REMOTENESS)
        popcol = next(c for c in rem.columns if c.startswith("pop_within_1"))
        per = per.merge(rem[["cooperative_id", "own_cell_pop", popcol]],
                        on="cooperative_id", how="left")
        per = per.rename(columns={popcol: "pop_within_1_4km"})
    else:
        print(f"  note: {REMOTENESS.name} missing - skipping the population join")
        per["own_cell_pop"] = np.nan
        per["pop_within_1_4km"] = np.nan

    # Road distance from 05. This is the sharpest available discriminator
    # between the two things a farmland hit can mean: a building stands next to
    # a road, a desa centroid does not have to. A point 3 km deep in a field and
    # 30 m from a road is a real roadside place; one 3 km deep and 1.5 km from
    # any road is far more likely to be a coordinate that was never a building.
    if ROAD_ACCESS.exists():
        road = pd.read_csv(ROAD_ACCESS)[["cooperative_id", "km_non_track", "km_any_road"]]
        per = per.merge(road, on="cooperative_id", how="left")
        per["roadside"] = per.km_any_road <= 0.14   # within one H3 r10 ring
    else:
        print(f"  note: {ROAD_ACCESS.name} missing - skipping the road-access join")
        per["km_non_track"] = np.nan
        per["km_any_road"] = np.nan
        per["roadside"] = pd.NA

    per["imagery_url"] = [
        f"https://www.google.com/maps/@{a},{b},250m/data=!3m1!1e3"
        for a, b in zip(per.latitude, per.longitude)
    ]
    write_csv(per, OUT / "kopdes_landuse_context.csv",
              "per-cooperative; joins to 03/05 on cooperative_id")

    # --- null model: where do village centres themselves land? ----------------
    # A raw hit rate means nothing on its own. If village institutions in
    # general sit inside mapped farmland at the same rate, "the KDMP is in a
    # field" is a statement about how OSM draws Indonesia, not about the KDMP.
    # OSM's own village nodes are the natural comparator: they are what "the
    # right place for a village institution" looks like, drawn by people with
    # no stake in this argument.
    vil = gdf[(gdf["class"] == "village") & (gdf.geom_type == "Point")]
    vlon = shapely.get_x(vil.geometry.to_numpy())
    vlat = shapely.get_y(vil.geometry.to_numpy())
    print(f"\nnull model: {len(vil):,} OSM village-centre nodes through the same screen")
    null_layers = {k: v for k, v in layers.items() if k in PIP_CLASSES}
    null_cols = annotate(vlon, vlat, null_layers, "village")

    rows = [
        {"class": k, "group": "kdmp", "points": len(per),
         "inside": int(per[f"in_{k}"].sum()),
         "pct": round(100 * per[f"in_{k}"].mean(), 3)}
        for k in PIP_CLASSES
    ] + [
        {"class": k, "group": "osm_village_node", "points": len(vil),
         "inside": int(null_cols[f"in_{k}"].sum()),
         "pct": round(100 * null_cols[f"in_{k}"].mean(), 3)}
        for k in PIP_CLASSES
    ]

    # Second comparator: mapped minimarkets. These are sited by companies whose
    # only interest is footfall, so they are the closest thing available to
    # "where a shop that has to survive commercially actually goes".
    #
    # The confound is geographic, not subtle: OSM minimarkets are concentrated in
    # Java and in towns (see 06), where there is little farmland to stand in,
    # while KDMP are spread one per desa nationwide. Comparing the raw rates
    # would credit the KDMP programme with Papua's geography. So the KDMP rate is
    # also reported re-weighted to the minimarkets' own province distribution -
    # the like-for-like number, and the only one worth quoting.
    if MINIMARKETS.exists():
        import pyogrio

        mm = pyogrio.read_dataframe(MINIMARKETS)
        mm = mm[mm.geometry.geom_type == "Point"]
        mlon, mlat = shapely.get_x(mm.geometry.values), shapely.get_y(mm.geometry.values)
        print(f"\nsecond comparator: {len(mm):,} OSM minimarkets through the same screen")
        mm_cols = annotate(mlon, mlat, null_layers, "minimarket")

        # Province label per minimarket = province of the nearest cooperative.
        # KDMP are one per desa nationwide, so the nearest one is a reliable
        # province lookup and costs one tree query.
        ktree = STRtree(shapely.points(lon, lat))
        near_k = nearest_index(ktree, shapely.points(mlon, mlat))
        mm_prov = per.province.to_numpy()[near_k]
        w = pd.Series(mm_prov).value_counts(normalize=True)

        for k in PIP_CLASSES:
            rows.append({"class": k, "group": "osm_minimarket", "points": len(mm),
                         "inside": int(mm_cols[f"in_{k}"].sum()),
                         "pct": round(100 * mm_cols[f"in_{k}"].mean(), 3)})
            rate = per.groupby("province")[f"in_{k}"].mean()
            ww = w.reindex(rate.index).fillna(0)
            rows.append({"class": k, "group": "kdmp_reweighted_to_minimarket_provinces",
                         "points": len(per), "inside": pd.NA,
                         "pct": round(100 * float((rate * ww).sum() / ww.sum()), 3)})
    else:
        print(f"\n  note: {MINIMARKETS.name} missing - skipping the minimarket comparator")

    null = pd.DataFrame(rows).sort_values(["class", "group"]).reset_index(drop=True)
    print()
    print(null.to_string(index=False))
    write_csv(null, OUT / "null_comparison.csv",
              "compare kdmp against the reweighted row, not the raw minimarket row")

    # --- summary --------------------------------------------------------------
    summary = []
    for k in CLASSES:
        row = {"class": k, "osm_features": int((gdf["class"] == k).sum())}
        if f"in_{k}" in per:
            row["kdmp_inside_polygon"] = int(per[f"in_{k}"].sum())
        for m in (100, 250, 500, 1000):
            row[f"kdmp_within_{m}m"] = int((per[f"dist_{k}_m"] <= m).sum())
        row["median_dist_m"] = round(float(per[f"dist_{k}_m"].median()), 1)
        summary.append(row)
    summary = pd.DataFrame(summary)
    print()
    print(summary.to_string(index=False))
    write_csv(summary, OUT / "landuse_pip_summary.csv")

    # --- the burial-ground candidates ----------------------------------------
    cem = per[per.in_cemetery].sort_values("cemetery_depth_m", ascending=False)
    write_csv(cem, OUT / "cemetery_candidates.csv", "verify against imagery before citing")
    print(f"\nKDMP inside a mapped burial ground: {len(cem):,} "
          f"({int((cem.land_status == 'Terverifikasi').sum())} land-verified)")

    # --- the paddy-field candidates ------------------------------------------
    # The screen 04 structurally cannot run: inside a field, but NOT isolated -
    # people live nearby, which is exactly why 04's isolation ranking misses it.
    farm = per[per.in_farmland].copy()
    farm["near_people"] = farm.pop_within_1_4km.fillna(0) >= 100
    farm["deep_in_field"] = farm.farmland_depth_m >= DEEP_IN_FIELD_M
    keep = farm.near_people & farm.deep_in_field & ~farm.farmland_polygon_coarse
    cand = farm[keep].sort_values(["farmland_depth_m", "dist_village_core_m"], ascending=False)

    funnel = pd.DataFrame([
        ("inside a mapped farmland polygon", int(len(farm))),
        (f">= {DEEP_IN_FIELD_M} m from the field edge", int(farm.deep_in_field.sum())),
        ("... and >= 100 people within 1.4 km", int((farm.deep_in_field & farm.near_people).sum())),
        (f"... and polygon has < {COARSE_POLYGON_VILLAGES} villages inside it", int(keep.sum())),
    ], columns=["step", "cooperatives"])
    print()
    print(funnel.to_string(index=False))
    write_csv(funnel, OUT / "farmland_funnel.csv")

    # Independent confirmation. The OSM polygon is one person's tracing; ESA
    # WorldCover is a 10 m satellite classification produced with no knowledge of
    # OSM. Where both agree the point is agricultural, the finding no longer
    # rests on a single source - the same two-independent-sources argument that
    # carries 05. Sampling reuses 04's COG range-request sampler.
    if not args.skip_rasters and len(cand):
        print(f"\nconfirming {len(cand):,} candidates against ESA WorldCover 10 m")
        s04 = load_04_sampler()
        cover = s04.sample_all(cand, lambda a, b: s04.cover_url(a, b), s04.cover_key,
                               window_px=5, label="ESA WorldCover 10m")
        cand["landcover_code"] = [int(cover[i][0]) if i in cover else np.nan for i in cand.index]
        cand["landcover"] = cand.landcover_code.map(s04.WORLDCOVER)
        cand["confirmed_agricultural"] = cand.landcover_code == 40
        print("\nland cover at the candidate points:")
        print(cand.landcover.value_counts(dropna=False).to_string())
        agree = int(cand.confirmed_agricultural.sum())
        print(f"\nboth sources agree it is cropland: {agree:,} of {len(cand):,} "
              f"({100*agree/len(cand):.1f}%)")

    write_csv(cand, OUT / "farmland_candidates.csv",
              f">= {DEEP_IN_FIELD_M} m inside a non-coarse field, people within 1.4 km")
    if "roadside" in cand and cand.roadside.notna().any():
        print(f"of those, within ~140 m of a mapped road: {int(cand.roadside.sum()):,} "
              f"(the rest are likelier to be coordinates that were never a building)")
    print(f"KDMP outside any village core (> {VILLAGE_CORE_M} m from both a village "
          f"node and a place of worship): {int(per.outside_village_core.sum()):,}")

    # --- coverage diagnostic --------------------------------------------------
    # Which provinces have the layer drawn at all. Without this the distance
    # columns get read as facts about Indonesia rather than facts about OSM.
    cov = per.groupby("province").agg(
        cooperatives=("cooperative_id", "size"),
        in_cemetery=("in_cemetery", "sum"),
        in_farmland=("in_farmland", "sum"),
        cemetery_within_2km=("dist_cemetery_m", lambda s: int((s <= 2000).sum())),
        farmland_within_2km=("dist_farmland_m", lambda s: int((s <= 2000).sum())),
        village_node_within_2km=("dist_village_m", lambda s: int((s <= 2000).sum())),
    )
    for c in ("cemetery", "farmland", "village_node"):
        cov[f"pct_{c}_within_2km"] = (100 * cov[f"{c}_within_2km"] / cov.cooperatives).round(1)
    cov = cov.sort_values("pct_cemetery_within_2km").reset_index()
    write_csv(cov, OUT / "osm_landuse_coverage_by_province.csv",
              "read this before reading any absence as evidence")
    print("\nthinnest OSM burial-ground coverage (share of KDMP with one within 2 km):")
    print(cov[["province", "cooperatives", "pct_cemetery_within_2km"]].head(8).to_string(index=False))


if __name__ == "__main__":
    main()
