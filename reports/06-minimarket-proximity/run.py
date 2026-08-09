#!/usr/bin/env python3
"""
06-minimarket-proximity - how close are KDMP to existing modern retail?

Tests the cannibalisation critique: KDMP built next door to an Alfamart or
Indomaret that already serves the same village.

THE CENTRAL PROBLEM, AND WHAT THIS SCRIPT DOES ABOUT IT
-------------------------------------------------------
The only retail dataset in hand is OSM, and OSM's POI coverage in rural
Indonesia is poor and *urban-biased* - mapper density tracks urbanisation,
which is the opposite of where KDMP sit. A naive "X% of KDMP are near a
minimarket" from this data would be an undercount of unknown size, biased in
the direction that **exonerates the programme**. That is the worst way to be
wrong in a critical investigation.

So this report is built around the bias rather than ignoring it:

  1. It measures the coverage deficit from the data itself (section: coverage
     diagnostics) instead of assuming it away.
  2. Every proximity number is reported as a **strict lower bound** - "at least
     N% of KDMP are within 500 m of a mapped outlet". A lower bound from an
     undercounting source is a valid one-sided claim; a point estimate is not.
  3. It adds the **reverse direction** - for each mapped minimarket, how far is
     the nearest KDMP. That statistic is conditional on the store existing, so
     it is far less sensitive to the undercount.
  4. It reports a **scope-restricted** estimate over the provinces where OSM
     retail mapping looks adequate, where the bound is tighter.

Read reports/06-minimarket-proximity/README.md before quoting any figure.

Usage: python reports/06-minimarket-proximity/run.py
"""

import re
import sys
from pathlib import Path

import duckdb
import pandas as pd
import pyogrio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.common import RAW, ROOT, out_dir, write_csv  # noqa: E402

OUT = out_dir(__file__)
MINIMARKETS = ROOT / "data" / "osm" / "indonesia_minimarkets.gpkg"
POP_PARQUET = ROOT / "data" / "population" / "population_h3.parquet"
# Optional - enables the stricter road-constrained null model. Built by
# reports/05-road-access/run.py.
ROAD_CELLS = ROOT / "data" / "osm" / "road_cells_h3r10.parquet"

RES = 10
KM_PER_RING = 0.132
BANDS = [(4, "~500 m"), (8, "~1 km"), (15, "~2 km"), (38, "~5 km")]

# Published national outlet counts, for the coverage deficit calculation.
# VERIFY AND UPDATE BEFORE PUBLICATION - these are approximate figures from
# company reporting and move every year. They are used only to state how
# incomplete OSM is; no downstream number depends on their exact value.
PUBLISHED_OUTLETS = {"Indomaret": 22000, "Alfamart": 20000}

# ---------------------------------------------------------------------------
# Competitive tiering.
#
# The source gpkg is named "minimarkets" but it is an Overpass pull of
# shop=convenience|supermarket|department_store, so 22.5% of it is not a
# minimarket at all. A Matahari or a Ramayana is not competition for a village
# cooperative selling rice and LPG, and lumping them in inflates every
# proximity figure. Tier before measuring.
# ---------------------------------------------------------------------------
SUPERMARKET_BRANDS = {
    "Super Indo", "Hypermart", "Giant", "Lotte Mart",
    "Transmart / Carrefour", "AEON", "Indogrosir",
}
DEPARTMENT_BRANDS = {"Matahari", "Ramayana", "Yogya / Toserba"}

TIER_CONVENIENCE = "1 convenience / minimarket"
TIER_SUPERMARKET = "2 supermarket (town-level)"
TIER_DEPARTMENT = "3 department store (not food retail)"

# scripts/download_osm.py's classify_brand() misses a set of spelling variants
# and regional chains, which land in "other". Recover them so the brand table
# and the tiering are both honest.
BRAND_PATTERNS = [
    ("Alfamart group", r"alfa\s*express|alfaexpress|alfa\s*midi|alfamidi|alfa\s*mart"),
    ("7-Eleven", r"7[\s-]?eleven|seven\s*eleven"),
    ("Yomart", r"yomart|yo\s*mart"),
    ("Hero", r"\bhero\b"),
    ("Bali regional chains", r"pepito|coco\s*express|\bcoco\b|popular"),
    ("fuel-station shop", r"shell select|\bbright\b"),
]
# Traditional retail. Present in OSM only as a rounding error, but it must be
# separated out rather than counted as modern retail - see README §5.
TRADITIONAL_PATTERN = r"warung|kelontong|sembako|^toko\b|\btoko "


def reclassify(mm):
    """Recover missed brands, split off traditional retail, assign a tier."""
    name = mm.name.fillna("").str.lower()
    label = mm.brand_label.copy()
    for brand, pattern in BRAND_PATTERNS:
        hit = (label == "other") & name.str.contains(pattern, regex=True, na=False)
        label = label.mask(hit, brand)
    traditional = (label == "other") & name.str.contains(TRADITIONAL_PATTERN, regex=True, na=False)
    label = label.mask(traditional, "traditional warung / toko")
    mm = mm.assign(brand_label2=label)

    def tier(row):
        if row.brand_label2 == "traditional warung / toko":
            return "0 traditional retail"
        if row.brand_label2 in DEPARTMENT_BRANDS or row.shop == "department_store":
            return TIER_DEPARTMENT
        if row.brand_label2 in SUPERMARKET_BRANDS or row.shop == "supermarket":
            return TIER_SUPERMARKET
        return TIER_CONVENIENCE

    return mm.assign(tier=mm.apply(tier, axis=1))


def rings_to_nearest(con, src_table, target_table, label):
    """Outward H3 ring search from src to target; returns {id: ring index}."""
    con.execute(f"create or replace table _unres as select id, h3 from {src_table}")
    con.execute("create or replace table _hits (id BIGINT, k INTEGER)")
    prev = 0
    for k, _ in BANDS:
        for kk in range(prev, k + 1):
            con.execute(
                f"""insert into _hits
                    select u.id, {kk} from _unres u
                    where exists (select 1 from unnest(h3_grid_ring(u.h3, {kk})) as c(cell)
                                  join {target_table} t on t.h3 = c.cell)"""
            )
            con.execute("delete from _unres where id in (select id from _hits)")
        left = con.execute("select count(*) from _unres").fetchone()[0]
        print(f"    {label}: within ~{k*KM_PER_RING:.2f} km -> {left:,} still unmatched")
        prev = k + 1
        if left == 0:
            break
    return con.execute("select id, k from _hits").fetchdf()


def main():
    if not MINIMARKETS.exists():
        sys.exit(f"missing {MINIMARKETS}\n  run: python scripts/download_osm.py --poi-only")

    con = duckdb.connect()
    con.execute("install h3 from community; load h3;")

    mm = pyogrio.read_dataframe(MINIMARKETS)
    mm["lon"], mm["lat"] = mm.geometry.x, mm.geometry.y
    mm = reclassify(mm.reset_index(drop=True))
    mm["id"] = mm.index
    loc = pd.read_csv(RAW / "kopdes_locations.csv").rename(columns={"cooperative_id": "id"})

    tiers = mm.tier.value_counts().rename_axis("tier").reset_index(name="pois")
    tiers["pct"] = (100 * tiers.pois / len(mm)).round(1)
    print("=== what is actually in this dataset ===\n")
    print(tiers.sort_values("tier").to_string(index=False))
    write_csv(tiers.sort_values("tier"), OUT / "retail_tiers.csv")

    # Everything downstream measures the competitive tier that a village
    # cooperative actually competes with. Supermarkets are reported separately;
    # department stores are dropped from proximity entirely.
    mm_all = mm
    mm = mm[mm.tier == TIER_CONVENIENCE].reset_index(drop=True)
    mm["id"] = mm.index
    print(f"\nproximity below uses the {len(mm):,} tier-1 convenience/minimarket POIs only\n")

    con.register("mm_raw", mm[["id", "lat", "lon", "brand_label"]])
    con.register("kop_raw", loc[["id", "province", "district", "subdistrict", "latitude", "longitude"]])
    con.execute(f"create table mm as select id, brand_label, h3_latlng_to_cell(lat, lon, {RES}) h3 from mm_raw")
    con.execute(f"""create table kop as select id, province, district, subdistrict,
                    h3_latlng_to_cell(latitude, longitude, {RES}) h3 from kop_raw""")

    # ---------------- coverage diagnostics -------------------------------
    print("=== coverage diagnostics ===\n")
    brands = mm_all.brand_label2.value_counts().rename_axis("brand").reset_index(name="osm_count")
    brands["published_outlets"] = brands.brand.map(PUBLISHED_OUTLETS)
    brands["osm_share_of_published"] = (
        100 * brands.osm_count / brands.published_outlets
    ).round(1)
    print(brands.head(8).to_string(index=False))
    write_csv(brands, OUT / "osm_brand_coverage.csv")

    # Where do mapped minimarkets sit, versus where KDMP sit? If OSM retail is
    # urban-biased, its POIs will fall in far more populous cells than the
    # cooperatives do. This is measured from the data, needing no external
    # benchmark.
    if POP_PARQUET.exists():
        con.execute(f"create table pop as select * from read_parquet('{POP_PARQUET.as_posix()}')")
        con.execute("create table pop10 as select h3_string_to_h3(h3) as h3_8, population from pop")
        cmp_rows = []
        for name, tbl in (("KDMP", "kop"), ("OSM minimarket", "mm")):
            df = con.execute(
                f"""select coalesce(p.population, 0) as pop
                    from {tbl} t left join pop10 p on h3_cell_to_parent(t.h3, 8) = p.h3_8"""
            ).fetchdf()
            cmp_rows.append(
                {
                    "points": name,
                    "n": len(df),
                    "median_pop_own_400m_cell": float(df["pop"].median()),
                    "pct_in_zero_pop_cell": round(100 * float((df["pop"] == 0).mean()), 1),
                }
            )
        cmp = pd.DataFrame(cmp_rows)
        print()
        print(cmp.to_string(index=False))
        write_csv(cmp, OUT / "urban_bias_diagnostic.csv")

    # Minimarkets per 100 cooperatives, by province. Province is assigned to
    # each minimarket from its nearest KDMP - cheap (10.6k points) and adequate
    # for a density diagnostic.
    print("\n  assigning minimarkets to provinces via nearest KDMP...")
    con.execute("create or replace table kop_t as select h3, province from kop")
    prov_of_mm = []
    con.execute("create or replace table _u as select id, h3 from mm")
    for k in range(0, 60):
        got = con.execute(
            f"""select u.id, any_value(t.province) as province
                from _u u, unnest(h3_grid_ring(u.h3, {k})) as c(cell)
                join kop_t t on t.h3 = c.cell group by 1"""
        ).fetchdf()
        if len(got):
            prov_of_mm.append(got)
            con.register("_g", got[["id"]])
            con.execute("delete from _u where id in (select id from _g)")
            con.unregister("_g")
        if con.execute("select count(*) from _u").fetchone()[0] == 0:
            break
    mm_prov = pd.concat(prov_of_mm) if prov_of_mm else pd.DataFrame(columns=["id", "province"])

    dens = (
        mm_prov.groupby("province").size().rename("osm_minimarkets").to_frame()
        .join(loc.groupby("province").size().rename("kdmp"), how="outer")
        .fillna(0).astype(int)
    )
    dens["minimarkets_per_100_kdmp"] = (100 * dens.osm_minimarkets / dens.kdmp).round(2)
    dens = dens.sort_values("minimarkets_per_100_kdmp", ascending=False).reset_index()
    print()
    print(dens.head(6).to_string(index=False))
    print("  ...")
    print(dens.tail(4).to_string(index=False))
    write_csv(dens, OUT / "osm_density_by_province.csv")

    # ---------------- proximity, both directions --------------------------
    print("\n=== proximity: KDMP -> nearest mapped minimarket (LOWER BOUND) ===")
    k_to_mm = rings_to_nearest(con, "kop", "mm", "KDMP->minimarket").rename(columns={"k": "k_to_minimarket"})
    print("\n=== proximity: mapped minimarket -> nearest KDMP ===")
    k_to_kop = rings_to_nearest(con, "mm", "kop", "minimarket->KDMP").rename(columns={"k": "k_to_kdmp"})

    per = loc[["id", "province", "district", "subdistrict", "latitude", "longitude"]].merge(
        k_to_mm, on="id", how="left"
    )
    per["km_to_minimarket"] = (per.k_to_minimarket * KM_PER_RING).round(3)
    write_csv(per, OUT / "kopdes_minimarket_distance.csv", "per-cooperative")

    rows = []
    for k, lbl in BANDS:
        n = int((per.k_to_minimarket <= k).sum())
        rows.append({"within": lbl, "cooperatives_at_least": n, "pct_at_least": round(100 * n / len(per), 2)})
    fwd = pd.DataFrame(rows)
    print()
    print("KDMP with a mapped minimarket within X (LOWER BOUNDS):")
    print(fwd.to_string(index=False))
    write_csv(fwd, OUT / "kdmp_near_minimarket_lower_bounds.csv")

    # Supermarkets reported separately - a town-level format with a much wider
    # catchment, so mixing it into the minimarket figure would overstate
    # village-level competition.
    sup = mm_all[mm_all.tier == TIER_SUPERMARKET].reset_index(drop=True)
    sup["id"] = sup.index
    con.register("sup_raw", sup[["id", "lat", "lon"]])
    con.execute(f"create or replace table sup as select id, h3_latlng_to_cell(lat, lon, {RES}) h3 from sup_raw")
    print(f"\n=== proximity: KDMP -> nearest SUPERMARKET ({len(sup):,} POIs) ===")
    k_to_sup = rings_to_nearest(con, "kop", "sup", "KDMP->supermarket").rename(columns={"k": "k_to_supermarket"})
    sup_fwd = per[["id"]].merge(k_to_sup, on="id", how="left")
    sup_rows = [
        {
            "within": lbl,
            "cooperatives_at_least": int((sup_fwd.k_to_supermarket <= k).sum()),
            "pct_at_least": round(100 * float((sup_fwd.k_to_supermarket <= k).mean()), 2),
        }
        for k, lbl in BANDS
    ]
    print()
    print(pd.DataFrame(sup_rows).to_string(index=False))
    write_csv(pd.DataFrame(sup_rows), OUT / "kdmp_near_supermarket_lower_bounds.csv")

    rev_rows = []
    mm_j = mm[["id", "brand_label"]].merge(k_to_kop, on="id", how="left")
    for k, lbl in BANDS:
        n = int((mm_j.k_to_kdmp <= k).sum())
        rev_rows.append({"within": lbl, "minimarkets": n, "pct": round(100 * n / len(mm_j), 2)})
    rev = pd.DataFrame(rev_rows)
    print("\nMapped minimarkets with a KDMP within X (less bias-sensitive):")
    print(rev.to_string(index=False))
    write_csv(rev, OUT / "minimarket_near_kdmp.csv")

    # ---------------- null model ------------------------------------------
    # The reverse statistic on its own proves nothing. KDMP are one-per-village
    # and cover 95% of the population within ~1.4 km (report 03), so ANY
    # populated location has a KDMP nearby almost by construction. To claim
    # minimarkets are *specially* co-located, they must be closer to a KDMP
    # than a population-weighted random point is.
    if POP_PARQUET.exists():
        print("\n=== null model: population-weighted random points ===")
        import numpy as np

        rng = np.random.default_rng(11)
        cells = con.execute("select h3, population from pop where population > 0").fetchdf()
        w = cells.population.to_numpy()
        idx = rng.choice(len(cells), size=len(mm), replace=True, p=w / w.sum())
        # Kontur is r8; drop to a random r10 child so the null points sit on the
        # same grid as everything else rather than on r8 centroids.
        import h3 as h3py

        null_cells = []
        for i in idx:
            kids = h3py.cell_to_children(cells.h3.iloc[i], RES)
            null_cells.append(kids[rng.integers(len(kids))])
        null_df = pd.DataFrame({"id": range(len(null_cells)), "h3_str": null_cells})
        con.register("null_raw", null_df)
        con.execute("create or replace table nullpts as select id, h3_string_to_h3(h3_str) as h3 from null_raw")

        k_null = rings_to_nearest(con, "nullpts", "kop", "null->KDMP").rename(columns={"k": "k_to_kdmp"})
        null_j = null_df[["id"]].merge(k_null, on="id", how="left")

        # Second, stricter null: a *plausible retail site* - a cell that has a
        # road in it and sits inside a populated area. The population-weighted
        # null above places points anywhere in an r8 cell, so it cannot capture
        # sub-400 m structure; if both minimarkets and KDMP simply sit on the
        # village road, that alone would produce apparent co-location. This null
        # controls for it.
        null2_j = None
        if ROAD_CELLS.exists():
            con.execute(
                f"""create or replace table road_cells_d as
                    select h3 from read_parquet('{ROAD_CELLS.as_posix()}') where non_track"""
            )
            cand = con.execute(
                """select r.h3, p.population
                   from road_cells_d r
                   join pop10 p on h3_cell_to_parent(r.h3, 8) = p.h3_8
                   where p.population > 0"""
            ).fetchdf()
            w2 = cand.population.to_numpy()
            pick = rng.choice(len(cand), size=len(mm), replace=True, p=w2 / w2.sum())
            null2 = pd.DataFrame({"id": range(len(pick)), "h3": cand.h3.to_numpy()[pick]})
            con.register("null2_raw", null2)
            con.execute("create or replace table nullpts as select id, h3 from null2_raw")
            k_null2 = rings_to_nearest(con, "nullpts", "kop", "road-null->KDMP").rename(
                columns={"k": "k_to_kdmp"}
            )
            null2_j = null2[["id"]].merge(k_null2, on="id", how="left")

        comp = []
        for k, lbl in BANDS:
            row = {
                "within": lbl,
                "pct_minimarkets": round(100 * float((mm_j.k_to_kdmp <= k).mean()), 2),
                "pct_random_pop_weighted": round(100 * float((null_j.k_to_kdmp <= k).mean()), 2),
            }
            if null2_j is not None:
                row["pct_random_on_road_pop_weighted"] = round(
                    100 * float((null2_j.k_to_kdmp <= k).mean()), 2
                )
            comp.append(row)
        comp = pd.DataFrame(comp)
        comp["excess_vs_pop_null"] = (comp.pct_minimarkets - comp.pct_random_pop_weighted).round(2)
        if null2_j is not None:
            comp["excess_vs_road_null"] = (
                comp.pct_minimarkets - comp.pct_random_on_road_pop_weighted
            ).round(2)
        print()
        print(comp.to_string(index=False))
        write_csv(comp, OUT / "null_model_comparison.csv")

    # ---------------- scope-restricted estimate ---------------------------
    # Restrict to provinces whose OSM retail density is at least a quarter of
    # the national median - i.e. drop the provinces where OSM has essentially
    # nothing and the bound would be vacuous.
    med = dens.minimarkets_per_100_kdmp.median()
    keep = set(dens.loc[dens.minimarkets_per_100_kdmp >= 0.25 * med, "province"])
    sub = per[per.province.isin(keep)]
    rows = []
    for k, lbl in BANDS:
        n = int((sub.k_to_minimarket <= k).sum())
        rows.append({"within": lbl, "cooperatives_at_least": n, "pct_at_least": round(100 * n / len(sub), 2)})
    scoped = pd.DataFrame(rows)
    scoped.insert(0, "scope", f"{len(keep)} provinces with OSM density >= 0.25x national median")
    print(f"\nScope-restricted to {len(keep)}/38 provinces ({len(sub):,} cooperatives):")
    print(scoped.to_string(index=False))
    write_csv(scoped, OUT / "scope_restricted_lower_bounds.csv")


if __name__ == "__main__":
    main()
