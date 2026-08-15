#!/usr/bin/env python3
"""
Build the analysis mart: one rich row per cooperative, plus the same measures
rolled up to kecamatan, kabupaten and provinsi.

This is the data layer the visual analytics app reads. Every finding produced in
reports/ is per-cooperative and lives in its own directory; a glyph renderer
needs them side by side, on one row, with a stable schema. That is all this
script does - it computes nothing new and it must not. If a number here
disagrees with a report, the report is right and this is broken.

One deliberate exception: user-contributed coordinate corrections. Rows in
`data/corrections/user_coordinates.csv` with `status = 'applied'` override the
SIMKOPDES latitude/longitude on the points table. That is not a computed
number; it is a decision to trust a verified correction over the export, and
provenance is preserved (`official_lat`/`official_lon` keep the SIMKOPDES
point, `coordinate_source` says which one is live). In v1 the override is
display-level only; H3 and the derived proximity measures still reflect the
SIMKOPDES coordinate (see AGENTS.md for the v2 recompute plan).

Four levels, for gradual aggregation in the app:

  data/web/kopdes_points.parquet      83,342 rows - one cooperative (~= one desa)
  data/web/kopdes_kecamatan.parquet    7,273 rows - subdistrict
  data/web/kopdes_kabupaten.parquet      514 rows - district
  data/web/kopdes_provinsi.parquet        38 rows - province

Every aggregate level carries the SAME measure names as the level below, so one
glyph specification works at all four zoom levels without a per-level special
case. Each aggregate row also carries an `anchor_lat`/`anchor_lon` - the median
position of its member cooperatives - which is what screengrid binds a feature
to when it is not drawing points.

Keys, and why they are what they are
------------------------------------
`kopdes_locations.csv` has no village name and no admin ids, only names. So:

  * **Admin ids** come from joining (province, district, subdistrict) names
    against `kopdes_stats_subdistrict.csv`, which carries all three ids.
    **99.91%** of cooperatives match. The 0.09% that do not are kept in the
    points table with null ids and are absent from every aggregate.
  * **Village-level economics** need a second hop, because nothing links a
    cooperative to a village directly: cooperative name -> `kopdes_land_assets`
    (which has a `village`) -> `kopdes_stats_village`. Hop 2 is essentially
    lossless (100.0%); hop 1 is not, because 21% of cooperatives have no
    land-asset record at all. **End-to-end 79.1%** - see analytics-plan-review
    section 1.5. Treat `has_village_stats` as a filter, never assume the join.
  * **Aggregate economics do not use that hop.** `kopdes_stats_village.csv`
    carries every admin id natively, so kecamatan/kabupaten/provinsi totals are
    grouped straight off it and are complete.

Two hard rules inherited from the reports:
  * **Deduplicate on the id before summing anything.** The 2026-08-05 export has
    1,555 duplicate village rows, 148 subdistricts, 5 districts.
  * **A zero transaction is "has not reported", not "is inactive"** (see
    reports/01-snapshot-drift). Column names say `reported` for that reason.

H3 cell ids are stored as **UBIGINT**, not hex strings - smaller, and joinable
by integer equality. `h3_h3_to_string(h3_r8)` converts in DuckDB / DuckDB-wasm
when a string is genuinely needed.

Inputs from reports/ are per-cooperative tables that are gitignored (6-28 MB
each). If one is missing, its columns are filled with nulls and the script says
so rather than failing - but the mart is then incomplete, so rebuild the report.

Usage:
  python scripts/build_analysis_mart.py
  python scripts/build_analysis_mart.py --out data/web
"""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
# Defaults to the committed 08-05 baseline; set KOPDES_RAW to a snapshot dir to
# rebuild the mart from a newer pull (reports/ must be re-run against the same
# snapshot first):
#   $env:KOPDES_RAW='data/snapshots/2026-08-13'; python scripts/build_analysis_mart.py
RAW = Path(os.environ["KOPDES_RAW"]) if os.environ.get("KOPDES_RAW") else ROOT / "data" / "raw"
REPORTS = ROOT / "reports"


def source_snapshot() -> str:
    """Name the pull this mart was built from, for the manifest.

    This used to be the hardcoded string "data/raw (SIMKOPDES export
    2026-08-05)". It stopped being true the first time the mart was rebuilt
    with KOPDES_RAW pointing at a snapshot: the parquet carried the 08-13
    figures (Rp 202,6 miliar) while the manifest still announced the 08-05
    export (Rp 179,6 miliar). A caveat that has to be edited by hand to stay
    true eventually stops being true, so it is derived now.
    """
    manifest = RAW / "_manifest.json"
    if manifest.exists():
        date_ = json.loads(manifest.read_text(encoding="utf-8")).get(
            "snapshot_date", RAW.name
        )
    else:
        date_ = "2026-08-05"  # data/raw ships without a manifest
    try:
        where = RAW.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        where = RAW.as_posix()
    return f"{where} (SIMKOPDES export {date_})"

# User-contributed coordinate corrections (see import_coordinate_corrections.py).
# Only `status = applied` rows override the SIMKOPDES point. Committed: it is
# part of the app's data layer, like the mart itself.
CORRECTIONS = ROOT / "data" / "corrections" / "user_coordinates.csv"

# H3 resolutions written onto every point. r8 is Kontur's native 400 m grid (03);
# the coarser ones let the app pre-aggregate without recomputing from lat/lon.
H3_RES = [5, 6, 7, 8, 9]

# Per-cooperative report outputs. `key` is that file's name for cooperative_id.
SOURCES = {
    "remoteness": (REPORTS / "03-population-coverage" / "kopdes_remoteness.csv",
                   "cooperative_id", "python reports/03-population-coverage/run.py"),
    "siting": (REPORTS / "04-siting-screen" / "candidates.csv",
               "cooperative_id", "python reports/04-siting-screen/run.py --top 2500"),
    "road": (REPORTS / "05-road-access" / "kopdes_road_access.csv",
             "cooperative_id", "python reports/05-road-access/run.py"),
    "retail": (REPORTS / "06-minimarket-proximity" / "kopdes_minimarket_distance.csv",
               "id", "python reports/06-minimarket-proximity/run.py"),
    "landuse": (REPORTS / "07-landuse-polygons" / "kopdes_landuse_context.csv",
                "cooperative_id", "python reports/07-landuse-polygons/run.py"),
    "farmcand": (REPORTS / "07-landuse-polygons" / "farmland_candidates.csv",
                 "cooperative_id", "python reports/07-landuse-polygons/run.py"),
    "retail_exact": (REPORTS / "08-exact-geometry" / "exact_minimarket_distance.csv",
                     "cooperative_id", "python reports/08-exact-geometry/run.py"),
    "road_exact": (REPORTS / "08-exact-geometry" / "exact_road_distance_far_set.csv",
                   "cooperative_id", "python reports/08-exact-geometry/run.py"),
    "suspect": (REPORTS / "08-exact-geometry" / "suspect_coordinates.csv",
                "cooperative_id", "python reports/08-exact-geometry/run.py"),
    "clustering": (REPORTS / "10-coop-clustering" / "nn_distances.csv",
                    "cooperative_id", "python reports/10-coop-clustering/run.py"),
    "building": (REPORTS / "17-building-proximity" / "kopdes_building_access.csv",
                  "cooperative_id", "python reports/17-building-proximity/run.py"),
    "landcover": (REPORTS / "19-land-cover" / "kopdes_landcover.csv",
                   "cooperative_id", "python reports/19-land-cover/run.py"),
}


# Ordered four-class collapses of the report bands, for the explorer's
# composition glyph. The reports' own bands are the right resolution for a
# table (`road_band` has seven) and the wrong one for a 40-pixel glyph, so each
# gets folded to four classes ordered worst -> best.
#
# These live here, on the points table, rather than in the app, because the
# aggregate share columns below are computed from the very same expressions.
# Deriving the collapse a second time in JavaScript is how a grid cell and a
# kecamatan glyph start disagreeing about what "near a road" means.
#
# Class order for stacking, per family (worst first):
#   road_class  over_5km  < under_5km < under_500m < on_road
#   pop_class   empty     < under_500 < under_10k  < over_10k
#   nn_class    under_1km < 1_2km     < 2_5km      < over_5km   (proximity, not quality)
#   landcover   categorical (not a severity ramp): WorldCover code order, 19
CLASS_COLUMNS = """
            case rd.road_band
                when 'on a road cell (<70 m)'  then 'on_road'
                when '< ~260 m'                then 'under_500m'
                when '< ~530 m'                then 'under_500m'
                when '< ~1 km'                 then 'under_5km'
                when '< ~2 km'                 then 'under_5km'
                when '< ~5 km'                 then 'under_5km'
                when '> ~5 km / none found'    then 'over_5km'
            end                                     as road_class,

            case r.remoteness_band
                when 'nobody within 5km'       then 'empty'
                when '<500'                    then 'under_500'
                when '500-2k'                  then 'under_10k'
                when '2k-10k'                  then 'under_10k'
                when '>10k'                    then 'over_10k'
            end                                     as pop_class,

            case cl.nn_band
                when '<500m'                   then 'under_1km'
                when '500m-1km'                then 'under_1km'
                when '1-2km'                   then '1_2km'
                when '2-5km'                   then '2_5km'
                when '>5km'                    then 'over_5km'
            end                                     as nn_class,

            case bd.building_band
                when 'on a building cell (<70 m)' then 'on_road'
                when '< ~260 m'                then 'under_500m'
                when '< ~530 m'                then 'under_500m'
                when '< ~1 km'                 then 'under_5km'
                when '< ~2 km'                 then 'under_5km'
                when '< ~5 km'                 then 'under_5km'
                when '> ~5 km / none found'    then 'over_5km'
            end                                     as building_class,

            -- 19 land cover: compact keys for the WorldCover labels so the
            -- share columns below get names without spaces.
            case lc.landcover
                when 'Tree cover'         then 'tree'
                when 'Shrubland'          then 'shrub'
                when 'Grassland'          then 'grass'
                when 'Cropland'           then 'crop'
                when 'Built-up'           then 'built'
                when 'Bare / sparse'      then 'bare'
                when 'Water'              then 'water'
                when 'Herbaceous wetland' then 'wetland'
                when 'Mangrove'           then 'mangrove'
            end                                 as landcover_class"""


def class_shares(family: str, classes: list[str]) -> str:
    """Percent-of-known share columns for one `<family>_class` collapse.

    The denominator is the non-null count, not the row count: a cooperative
    with no `road_band` is unmeasured, not "far from a road", and folding those
    into the denominator would quietly deflate every share in the family.
    """
    return ",\n".join(
        f"    round(100.0 * count(*) filter (where {family}_class = '{cls}')\n"
        f"          / nullif(count({family}_class), 0), 2)"
        f"{'':{max(1, 24 - len(family) - len(cls))}}as {family}_share_{cls}"
        for cls in classes
    )


def csv(path: Path) -> str:
    return f"read_csv_auto('{path.as_posix()}', header=true, sample_size=-1)"


def register_sources(con):
    """Create one view per report output; empty stand-in if the file is absent."""
    missing = []
    for name, (path, key, how) in SOURCES.items():
        if path.exists():
            con.execute(f"create or replace view src_{name} as "
                        f"select * rename ({key} as cooperative_id) from {csv(path)}"
                        if key != "cooperative_id" else
                        f"create or replace view src_{name} as select * from {csv(path)}")
        else:
            con.execute(f"create or replace view src_{name} as "
                        f"select null::bigint as cooperative_id where false")
            missing.append((name, path, how))
    if missing:
        print("  WARNING - missing report outputs, their columns will be null:")
        for name, path, how in missing:
            print(f"    {name:10} {path.relative_to(ROOT)}\n{'':15}rebuild: {how}")
    return {n for n, _, _ in missing}


def build_points(con, missing):
    """One row per cooperative, every report's attributes joined on."""
    h3_cols = ",\n            ".join(
        f"h3_latlng_to_cell(l.latitude, l.longitude, {r}) as h3_r{r}" for r in H3_RES
    )

    # Admin ids via the subdistrict name triple. Deduplicated first: the export
    # repeats 148 subdistricts, and joining against the raw file would duplicate
    # cooperatives.
    con.execute(f"""
        create or replace table admin as
        select * exclude (rn) from (
            select province_id, district_id, subdistrict_id,
                   upper(trim(province)) as p, upper(trim(district)) as d,
                   upper(trim(subdistrict)) as s,
                   row_number() over (partition by subdistrict_id order by province_id) as rn
            from {csv(RAW / 'kopdes_stats_subdistrict.csv')}
        ) where rn = 1
    """)

    # Village statistics, deduplicated on village_id. This is the complete
    # economic picture (every admin id is native to this file) and it is the
    # source for all aggregate totals. The two-hop join below is only ever used
    # to put a value on an individual cooperative.
    con.execute(f"""
        create or replace table village_stats as
        select * exclude (rn) from (
            select village_id, subdistrict_id, district_id, province_id,
                   upper(trim(province)) as p, upper(trim(district)) as d,
                   upper(trim(subdistrict)) as s, upper(trim(village)) as v,
                   village, accounts_count, npwp_count, nib_count, rat_count,
                   transaction_volume, transaction_value, savings_total_amount,
                   row_number() over (partition by village_id order by village) as rn
            from {csv(RAW / 'kopdes_stats_village.csv')}
        ) where rn = 1
    """)

    # The two-hop village link. Land assets carry the village name that
    # locations lacks; village stats are then keyed on the full name path.
    con.execute(f"""
        create or replace table village_link as
        with la as (
            select * exclude (rn) from (
                select cooperative, upper(trim(province)) as p, upper(trim(district)) as d,
                       upper(trim(subdistrict)) as s, upper(trim(village)) as v,
                       status as land_status, surveyor as land_surveyor,
                       row_number() over (partition by cooperative order by asset_id) as rn
                from {csv(RAW / 'kopdes_land_assets.csv')}
            ) where rn = 1
        )
        select la.cooperative, la.land_status, la.land_surveyor,
               vs.village_id, vs.village, vs.accounts_count, vs.npwp_count, vs.nib_count,
               vs.rat_count, vs.transaction_volume, vs.transaction_value,
               vs.savings_total_amount
        from la left join village_stats vs
               on la.p = vs.p and la.d = vs.d and la.s = vs.s and la.v = vs.v
    """)

    # User-contributed coordinate corrections. Only `applied` rows override;
    # deduplicated by cooperative_id (latest submitted_at wins) so the join
    # below cannot fan out. v1 note: this overrides the display coordinates
    # (latitude/longitude, imagery link, aggregate anchors) only; H3 and the
    # derived proximity measures still come from the SIMKOPDES point.
    if CORRECTIONS.exists():
        con.execute(f"""
            create or replace table usr_corr as
            select * exclude (rn) from (
                select
                    cooperative_id::int   as cooperative_id,
                    user_latitude::double as user_latitude,
                    user_longitude::double as user_longitude,
                    source_issue,
                    submitted_at,
                    row_number() over (partition by cooperative_id
                                       order by submitted_at desc) as rn
                from {csv(CORRECTIONS)}
                where lower(status) = 'applied'
            ) where rn = 1
        """)
    else:
        con.execute("""create or replace table usr_corr as
                       select null::int as cooperative_id,
                              null::double as user_latitude,
                              null::double as user_longitude,
                              null::varchar as source_issue,
                              null::varchar as submitted_at where false""")

    con.execute(f"""
        create or replace table points as
        select
            l.cooperative_id,
            l.name                                  as cooperative,
            a.province_id, a.district_id, a.subdistrict_id,
            l.province, l.district, l.subdistrict,
            vl.village_id, vl.village,
            coalesce(uc.user_latitude, l.latitude)        as latitude,
            coalesce(uc.user_longitude, l.longitude)      as longitude,
            case when uc.cooperative_id is not null then 'user'
                 else 'simkopdes' end                     as coordinate_source,
            uc.source_issue                               as coordinate_source_issue,
            uc.submitted_at                               as coordinate_corrected_at,
            l.latitude                                    as official_lat,
            l.longitude                                   as official_lon,
            {h3_cols},

            -- 02 zero-inflation / the outcome variable, where the two-hop join
            -- reached. NULL means "not linked", 0 means "linked and reported
            -- nothing" - these must never be conflated.
            (vl.village_id is not null)             as has_village_stats,
            vl.transaction_value, vl.transaction_volume, vl.savings_total_amount,
            vl.accounts_count, vl.npwp_count, vl.nib_count, vl.rat_count,
            case when vl.village_id is null then null
                 else vl.transaction_value > 0 end  as has_reported_transaction,

            -- 03 population coverage
            r.own_cell_pop, r.pop_within_1_4km, r.pop_within_5_1km, r.remoteness_band,
            -- 04's Stage A score, recomputed here for ALL cooperatives (the
            -- report only writes out its shortlist).
            (case when r.own_cell_pop = 0 then 2 else 0 end
             + case when coalesce(r.pop_within_1_4km, 0) < 100 then 2 else 0 end
             + case when coalesce(r.pop_within_5_1km, 0) < 1000 then 1 else 0 end)
                                                    as isolation_score,

            -- 04 siting screen: shortlist only, null elsewhere by design
            (s.cooperative_id is not null)          as in_siting_shortlist,
            s.elevation_m, s.relief_200m_m, s.landcover as siting_landcover,
            s.flag_steep, s.flag_implausible_cover, s.n_flags as siting_n_flags,

            -- 05 road access
            rd.km_any_road, rd.km_non_track, rd.road_band, rd.track_only,

            -- 17 building proximity (nearest mapped building footprint, H3 r10).
            -- Since 2026-08-14 the layer is VIDA's Google+Microsoft+OSM union,
            -- not OSM alone: 10.5M r10 cells against 3.59M. `km_to_building` is
            -- the ring distance k*0.132 and is null when nothing was found
            -- inside the ~5 km cap, which is not a zero.
            bd.building_band, bd.km_to_building,

            -- 06 modern retail (ring bands) and 08 (exact geodesic, all points).
            -- Prefer the exact column: 08 showed the ring version overstates
            -- distance by ~169 m and is capped at ~5 km.
            rt.km_to_minimarket,
            rx.m_to_minimarket                      as m_to_minimarket_exact,
            rx.nearest_brand                        as nearest_minimarket_brand,

            -- 08 exact road distance. Present only for 05's roadless set - for
            -- everyone else the ring distance is accurate to ~34 m and there was
            -- nothing to refine.
            dx.m_to_made_road                       as m_to_made_road_exact,

            -- 10 KDMP-to-KDMP clustering (exact geodesic nearest-neighbour).
            -- NULL m_to_nearest_other = one of the 821 coordinate artifacts the
            -- report set aside (see its coord_artifacts.csv) - filter, don't
            -- impute. nn_band / cluster_* are the same-cell r8 definitions.
            cl.m_to_nearest_other,
            cl.nn_band,
            cl.cluster_id,
            cl.cluster_size,

            -- 08 coordinate validity. TRUE means the point is outside Indonesia
            -- entirely; `coordinate_diagnosis` says whether flipping the
            -- latitude sign explains it. FILTER THESE OUT of any map or
            -- distance statistic.
            (sc.cooperative_id is not null
             and uc.cooperative_id is null)         as coordinate_suspect,
            sc.diagnosis                            as coordinate_diagnosis,

            -- 07 land use
            lu.in_farmland, lu.farmland_depth_m, lu.farmland_polygon_coarse,
            lu.in_cemetery, lu.cemetery_depth_m, lu.dist_cemetery_m,
            lu.dist_marketplace_m, lu.dist_village_core_m, lu.outside_village_core,
            (fc.cooperative_id is not null)         as farmland_candidate,
            fc.confirmed_agricultural               as farmland_confirmed_cropland,

            -- 19 land cover (ESA WorldCover 10m, sampled at every coordinate)
            lc.landcover                            as land_cover,
            lc.landcover_code                       as land_cover_code,

            -- land assets (name join; see the module docstring)
            vl.land_status, vl.land_surveyor,
            (vl.land_status = 'Terverifikasi')       as land_verified,

            {CLASS_COLUMNS},

            'https://www.google.com/maps/@' || coalesce(uc.user_latitude, l.latitude)
                || ',' || coalesce(uc.user_longitude, l.longitude)
                || ',250m/data=!3m1!1e3'            as imagery_url
        from {csv(RAW / 'kopdes_locations.csv')} l
        left join admin a
               on a.p = upper(trim(l.province)) and a.d = upper(trim(l.district))
              and a.s = upper(trim(l.subdistrict))
        left join village_link vl on vl.cooperative = l.name
        left join src_remoteness r using (cooperative_id)
        left join src_siting     s using (cooperative_id)
        left join src_road      rd using (cooperative_id)
        left join src_retail    rt using (cooperative_id)
        left join src_landuse   lu using (cooperative_id)
        left join src_farmcand  fc using (cooperative_id)
        left join src_landcover lc using (cooperative_id)
        left join src_retail_exact rx using (cooperative_id)
        left join src_road_exact   dx using (cooperative_id)
        left join src_suspect      sc using (cooperative_id)
        left join src_clustering   cl using (cooperative_id)
        left join src_building     bd using (cooperative_id)
        left join usr_corr         uc on uc.cooperative_id = l.cooperative_id
    """)

    n, = con.execute("select count(*) from points").fetchone()
    base, = con.execute(f"select count(*) from {csv(RAW / 'kopdes_locations.csv')}").fetchone()
    if n != base:
        sys.exit(f"FATAL: points has {n:,} rows against {base:,} cooperatives - a join fanned out")
    return n


# Spatial measures, aggregated from the points table. Identical names at every
# level, written once here so the four tables cannot drift apart.
#
# Economics are deliberately NOT in this list. Summing them over points would
# only reach the 79% of cooperatives whose village link resolved - which carry
# 88% of national transaction value, so the totals would be wrong AND biased.
# They come from ECON_MEASURES below instead, off the complete village file.
AGG_MEASURES = f"""
    count(*)                                                as cooperatives,
    -- Anchors ignore the 19 impossible coordinates (08). A median is robust to
    -- them nationally, but a kecamatan with few members could be dragged into
    -- the sea by one.
    median(latitude)  filter (where not coordinate_suspect) as anchor_lat,
    median(longitude) filter (where not coordinate_suspect) as anchor_lon,
    count(*) filter (where coordinate_suspect)              as coordinate_suspect,
    count(*) filter (where has_village_stats)               as cooperatives_village_linked,

    round(100.0 * count(*) filter (where own_cell_pop = 0)
          / nullif(count(*) filter (where own_cell_pop is not null), 0), 2)
                                                            as pct_zero_population_cell,
    median(pop_within_1_4km)                                as median_pop_within_1_4km,
    round(avg(isolation_score), 2)                          as mean_isolation_score,

    round(100.0 * count(*) filter (where km_non_track is null or km_non_track > 5)
          / nullif(count(*) filter (where km_any_road is not null
                                       or km_non_track is not null), 0), 2)
                                                            as pct_no_road_within_5km,
    median(km_non_track)                                    as median_km_to_road,
    -- Exact (08), not the capped ring version, so this is defined everywhere.
    round(median(m_to_minimarket_exact) / 1000.0, 3)        as median_km_to_minimarket,
    round(100.0 * count(*) filter (where m_to_minimarket_exact <= 500)
          / nullif(count(*) filter (where m_to_minimarket_exact is not null), 0), 2)
                                                            as pct_minimarket_within_500m,

    count(*) filter (where in_farmland)                     as in_farmland,
    count(*) filter (where farmland_candidate)              as farmland_candidates,
    count(*) filter (where in_cemetery)                     as in_cemetery,
    median(dist_marketplace_m)                              as median_m_to_marketplace,
    median(dist_village_core_m)                             as median_m_to_village_core,

    count(*) filter (where land_verified)                   as land_verified,
    round(100.0 * count(*) filter (where land_verified)
          / nullif(count(*) filter (where land_status is not null), 0), 2)
                                                            as pct_land_verified,
    count(*) filter (where in_siting_shortlist)             as siting_shortlisted,

    -- 10 self-overlap. Distance to the nearest sibling, exact geodesic; NULL
    -- where the point is one of the 821 excluded coordinate artifacts, and the
    -- nullif keeps those out of the denominator too.
    round(median(m_to_nearest_other), 0)                    as median_m_to_nearest_other,
    round(100.0 * count(*) filter (where m_to_nearest_other <= 1000)
          / nullif(count(*) filter (where m_to_nearest_other is not null), 0), 2)
                                                            as pct_sibling_within_1km,
    round(median(cluster_size), 0)                          as median_cluster_size,

    -- Class composition, for the explorer's stacked glyph. A median tells you
    -- where the middle cooperative sits; these tell you how the whole area is
    -- distributed, which is the thing a single number hides.
{class_shares('road', ['over_5km', 'under_5km', 'under_500m', 'on_road'])},
{class_shares('pop', ['empty', 'under_500', 'under_10k', 'over_10k'])},
{class_shares('nn', ['under_1km', '1_2km', '2_5km', 'over_5km'])},
{class_shares('building', ['over_5km', 'under_5km', 'under_500m', 'on_road'])},
{class_shares('landcover', ['tree', 'shrub', 'grass', 'crop', 'built', 'bare', 'water', 'wetland', 'mangrove'])}
"""


# The economic half, grouped straight off the deduplicated village file, which
# has every admin id natively. Complete at every level - no name matching and no
# two-hop join involved, so these totals reconcile exactly with the raw export.
ECON_MEASURES = """
    count(*)                                                as villages,
    count(*) filter (where transaction_value > 0)           as villages_reporting,
    round(100.0 * count(*) filter (where transaction_value > 0)
          / nullif(count(*), 0), 2)                         as pct_reported_transaction,
    sum(transaction_value)                                  as transaction_value,
    sum(transaction_volume)                                 as transaction_volume,
    sum(savings_total_amount)                               as savings_total_amount,
    sum(accounts_count)                                     as accounts_count,
    sum(npwp_count)                                         as npwp_count,
    sum(nib_count)                                          as nib_count,
    sum(rat_count)                                          as rat_count
"""


def build_aggregate(con, name, id_col, label_cols):
    """
    Roll one admin level up: spatial measures from `points`, economics from
    `village_stats`, joined on the admin id.

    Points with a null id are dropped, which is the 0.05% whose subdistrict name
    did not match. They stay in the points table; they cannot be placed in a
    hierarchy that has no id for them.
    """
    labels = ", ".join(f"any_value({c}) as {c}" for c in label_cols)
    con.execute(f"""
        create or replace table agg_{name} as
        with spatial as (
            select {id_col}, {labels}, {AGG_MEASURES}
            from points where {id_col} is not null group by {id_col}
        ), econ as (
            select {id_col}, {ECON_MEASURES}
            from village_stats where {id_col} is not null group by {id_col}
        )
        select * from spatial full outer join econ using ({id_col})
        order by {id_col}
    """)
    n, = con.execute(f"select count(*) from agg_{name}").fetchone()
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data" / "web"))
    args = ap.parse_args()
    out = Path(args.out).resolve()  # resolve so relative_to(ROOT) works in the progress prints
    out.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    con.execute("install h3 from community; load h3;")

    print("registering report outputs")
    missing = register_sources(con)

    print("\nbuilding points")
    n_points = build_points(con, missing)
    matched, = con.execute("select count(*) from points where subdistrict_id is not null").fetchone()
    linked, = con.execute("select count(*) from points where has_village_stats").fetchone()
    print(f"  {n_points:,} cooperatives")
    print(f"  admin ids resolved:      {matched:,}  ({100*matched/n_points:.2f}%)")
    print(f"  village stats linked:    {linked:,}  ({100*linked/n_points:.1f}%)")
    n_corr, = con.execute(
        "select count(*) from points where coordinate_source = 'user'").fetchone()
    if n_corr:
        print(f"  user-coordinate corrections applied: {n_corr}")

    levels = {
        "kecamatan": ("subdistrict_id", ["province_id", "district_id",
                                         "province", "district", "subdistrict"]),
        "kabupaten": ("district_id", ["province_id", "province", "district"]),
        "provinsi": ("province_id", ["province"]),
    }
    print("\nbuilding aggregates")
    counts = {"points": n_points}
    for name, (id_col, labels) in levels.items():
        counts[name] = build_aggregate(con, name, id_col, labels)
        print(f"  {name:10} {counts[name]:>6,} rows")

    # The province stats file carries health scoring that exists nowhere else.
    # Its own latitude/longitude is kept beside the computed anchor rather than
    # replacing it - analytics-plan-review 1.7 found those centroids to be the
    # likelier error for the new Papua provinces.
    con.execute(f"""
        create or replace table agg_provinsi as
        select a.*, p.health_score, p.health_status, p.average_health_index,
               p.healthy_count, p.fairly_healthy_count, p.unhealthy_count,
               p.latitude as official_lat, p.longitude as official_lon
        from agg_provinsi a
        left join (select * exclude (rn) from (
                     select *, row_number() over (partition by province_id
                                                  order by province) as rn
                     from {csv(RAW / 'kopdes_stats_province.csv')}) where rn = 1) p
               using (province_id)
        order by province_id
    """)

    print("\nwriting parquet")
    written = {}
    for table, fname in [("points", "kopdes_points"), ("agg_kecamatan", "kopdes_kecamatan"),
                         ("agg_kabupaten", "kopdes_kabupaten"), ("agg_provinsi", "kopdes_provinsi")]:
        path = out / f"{fname}.parquet"
        con.execute(f"copy {table} to '{path.as_posix()}' (format parquet, compression zstd)")
        written[fname] = path
        print(f"  {path.relative_to(ROOT)}  {path.stat().st_size/1e6:.2f} MB")

    # The manifest is what the app reads to know what it has: column names,
    # types, row counts, and which report produced each file. It also records
    # the join coverage, so a caveat cannot be silently lost between here and a
    # published chart.
    schema = {}
    for table, fname in [("points", "kopdes_points"), ("agg_kecamatan", "kopdes_kecamatan"),
                         ("agg_kabupaten", "kopdes_kabupaten"), ("agg_provinsi", "kopdes_provinsi")]:
        cols = con.execute(f"describe {table}").fetchall()
        entry = {
            "file": f"{fname}.parquet",
            "rows": con.execute(f"select count(*) from {table}").fetchone()[0],
            "columns": [{"name": c[0], "type": c[1]} for c in cols],
        }
        if table != "points":
            # Units that have villages in the statistics but no name-matched
            # cooperative. They carry economics and a null anchor, so they
            # cannot be drawn - filter on `anchor_lat is not null` to map.
            entry["rows_without_anchor"] = con.execute(
                f"select count(*) from {table} where anchor_lat is null").fetchone()[0]
        schema[fname] = entry
    manifest = {
        "built": date.today().isoformat(),
        "source_snapshot": source_snapshot(),
        "h3_resolutions": H3_RES,
        "h3_encoding": "UBIGINT; use h3_h3_to_string() for the hex form",
        "levels": ["kopdes_points", "kopdes_kecamatan", "kopdes_kabupaten", "kopdes_provinsi"],
        "anchor": "median latitude/longitude of member cooperatives",
        "coverage": {
            "cooperatives": n_points,
            "admin_ids_resolved": matched,
            "village_stats_linked": linked,
            "village_stats_linked_pct": round(100 * linked / n_points, 1),
        },
        "caveats": [
            "A zero transaction means 'has not reported', not 'is inactive' (reports/01).",
            "transaction_value is NULL where the village join failed and 0 where it "
            "succeeded and nothing was reported - do not conflate them.",
            "OSM-derived distances are upper bounds; absence is not evidence (reports/05, 07).",
            "Siting and farmland flags are candidates requiring imagery verification "
            "(reports/04, 07).",
            "Aggregate economics come from the complete village file; point-level "
            "economics reach 79% of cooperatives and carry 88% of national value, so "
            "never sum point economics to get a regional total - read the aggregate.",
            "Filter aggregates on anchor_lat is not null before mapping.",
            "A user-contributed coordinate (coordinate_source='user') overrides "
            "latitude/longitude, the imagery link and the aggregate anchors only; "
            "H3 and the derived proximity measures still reflect the SIMKOPDES "
            "coordinate until the v2 recompute (AGENTS.md).",
        ],
        # What a null MEANS, per column. This is not pedantry: several of these
        # nulls carry the finding. A glyph that renders a null
        # `km_to_minimarket` as "no data" instead of "further than 5 km" inverts
        # the meaning of report 06.
        "null_semantics": {
            "km_to_minimarket": "no mapped minimarket within ~5 km (the ring search "
                                "caps at k=38). 66,846 cooperatives. NOT unknown.",
            "km_any_road": "no mapped road of any kind within ~5 km (4,294). NOT unknown.",
            "km_non_track": "no made road within ~5 km (5,106). NOT unknown.",
            "building_band, km_to_building": "no *mapped* building within ~5 km (ring caps "
                             "at k=38). NOT unknown, and still a LOWER BOUND: since "
                             "2026-08-14 the layer is VIDA's Google+Microsoft+OSM union "
                             "rather than OSM alone, which narrows the rural undercount "
                             "but does not close it (reports/17).",
            "pop_within_1_4km": "no populated Kontur cell within the ring - read as 0.",
            "transaction_value": "the village link failed (21% of cooperatives). "
                                 "Genuinely unknown. 0 means linked and nothing reported.",
            "elevation_m, relief_200m_m, siting_landcover, flag_*": "not in 04's top-2,500 "
                                                                   "shortlist; never sampled.",
            "farmland_depth_m": "not inside a farmland polygon.",
            "cemetery_depth_m": "not inside a burial ground.",
            "land_status": "no land-asset record exists for this cooperative.",
            "m_to_made_road_exact": "not in 05's roadless set - the ring distance in "
                                    "km_non_track is accurate to ~34 m, use that (08).",
            "coordinate_diagnosis": "the coordinate is inside Indonesia and was never "
                                    "suspect.",
            "coordinate_source_issue, coordinate_corrected_at": "null: no applied user "
                                    "correction; the SIMKOPDES coordinate is in force.",
            "land_cover": "no WorldCover tile or nodata pixel at the coordinate. "
                           "The 08-13 snapshot resolves all 83,379; only the older "
                           "08-05 baseline had unresolvable points.",
        },
        "missing_sources": sorted(missing),
        "schema": schema,
    }
    (out / "mart_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"  {(out / 'mart_manifest.json').relative_to(ROOT)}")

    print("\nsanity checks")
    official, = con.execute("select sum(transaction_value) from village_stats").fetchone()
    tv_points, = con.execute("select sum(transaction_value) from points").fetchone()
    rows = con.execute(
        "select (select sum(transaction_value) from agg_kecamatan), "
        "       (select sum(transaction_value) from agg_kabupaten), "
        "       (select sum(transaction_value) from agg_provinsi)").fetchone()
    print(f"  deduplicated village file {official:>20,.0f}   <- ground truth")
    for label, v in zip(("kecamatan", "kabupaten", "provinsi"), rows):
        flag = "OK" if v == official else f"MISMATCH ({100*v/official:.2f}%)"
        print(f"  {label:>25} {v:>20,.0f}   {flag}")
    print(f"  {'points (79% linked)':>25} {tv_points:>20,.0f}   "
          f"{100*tv_points/official:.1f}% - expected, point economics are partial")
    top = con.execute(
        "select province, cooperatives, pct_reported_transaction, pct_zero_population_cell, "
        "pct_no_road_within_5km, pct_land_verified from agg_provinsi "
        "order by cooperatives desc limit 5"
    ).fetchdf()
    print()
    print(top.to_string(index=False))


if __name__ == "__main__":
    main()
