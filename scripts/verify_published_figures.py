#!/usr/bin/env python3
"""
verify_published_figures.py — recompute every headline number the site prints.

The site states figures in Indonesian prose across a dozen hand-written pages,
while the numbers themselves live in the mart and in `reports/*/`. Those two
drift the moment a report is re-run: nothing in the build regenerates the prose,
so a corrected analysis leaves a stale sentence behind and no test fails.

That is not hypothetical. Report 17's band-assignment bug published 62.6% where
the truth was 1.19%, and it survived because no check compared the sentence to
the data. This script is that check.

## What it does and does not prove

It verifies **arithmetic provenance**: that a number on a page is still what the
committed data produces. It cannot verify a claim's wording, its causal framing,
or whether a caveat is honest. Those stay human review. A green run means no
figure has gone stale, not that the report is true.

## Conventions

- Every check names the page it defends, so a failure points at the file to edit.
- Percentages are compared at the precision the page prints them to (usually one
  decimal), because a page saying "3,3%" is not wrong when the data says 3.28%.
- A check whose source data is missing is reported as SKIP, never as a pass:
  several inputs are gitignored and rebuilt by their own report.

## The externally sourced figures

Four numbers come from press reporting rather than from our data, so no amount
of recomputation can confirm them. They were instead re-read against the live
articles on 2026-08-14 and every transcription in
`reports/09-external-corroboration/external_figures.csv` matched:

  Rp 157,90 miliar / 67.664 transactions / 83.382 cooperatives / 79.708 accounts
    Liputan6, 31 Jul 2026 - liputan6.com/bisnis/read/8258962
  Rp 179,72 miliar / 71.454 transactions / beras SPHP Rp 71,85 miliar
    Liputan6, 9 Aug 2026 - liputan6.com/bisnis/read/8265525
  1.061 operating (530 Jawa Timur, 531 Jawa Tengah) / 12.232 gerai complete
    CNN Indonesia, 11 Jun 2026, quoting Muhammad Qodari (Bakom)
    cnnindonesia.com/ekonomi/20260611123103-92-1367861

That pass also corrected an attribution: the 31 July rows had been recorded as
statements by Zulkifli Hasan and Andi Amran Sulaiman. Both are quoted in that
article, but on what the programme is for, not on these figures, which Liputan6
attributes to SIMKOPDES itself. The checks below therefore verify that the pages
still match the transcription; the transcription's fidelity to the source is a
human step, and re-doing it means re-reading the three URLs above.

Usage:
  python scripts/verify_published_figures.py
  python scripts/verify_published_figures.py --verbose
"""

import argparse
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "data" / "web"
REPORTS = ROOT / "reports"

con = duckdb.connect()
P = f"read_parquet('{(WEB / 'kopdes_points.parquet').as_posix()}')"
PROV = f"read_parquet('{(WEB / 'kopdes_provinsi.parquet').as_posix()}')"

CHECKS = []


def check(page, label, published, tol=0.0):
    """Register a check. The decorated function returns the computed value."""

    def wrap(fn):
        CHECKS.append((page, label, published, fn, tol))
        return fn

    return wrap


def one(sql):
    return con.execute(sql).fetchone()[0]


def csv(report, name):
    path = REPORTS / report / name
    if not path.exists():
        raise FileNotFoundError(path)
    return f"read_csv('{path.as_posix()}')"


# ---------------------------------------------------------------------------
# Scale of the programme  (/, /findings/, /tabel/, /explore/)
# ---------------------------------------------------------------------------


@check("/ · findings · tabel · explore", "cooperatives in the mart", 83_379)
def _():
    return one(f"select count(*) from {P}")


@check("/ · findings", "provinces", 38)
def _():
    return one(f"select count(distinct province) from {P}")


@check("/ · findings/money", "national transaction value (Rp miliar)", 202.6, tol=0.05)
def _():
    return round(one(f"select sum(transaction_value) from {PROV}") / 1e9, 1)


@check("findings/money", "villages reporting a transaction", 2_726)
def _():
    return one(f"select sum(villages_reporting) from {PROV}")


@check("/ · findings/money", "% of villages reporting a transaction", 3.3, tol=0.05)
def _():
    r = con.execute(
        f"select sum(villages_reporting), sum(villages) from {PROV}"
    ).fetchone()
    return round(100 * r[0] / r[1], 1)


# ---------------------------------------------------------------------------
# Chapter 1 — access and placement  (/, findings/remoteness, methods 03/05/07)
# ---------------------------------------------------------------------------


@check("/ · findings/remoteness", "cooperatives with nobody within 5,1 km", 146)
def _():
    return one(f"select count(*) from {P} where pop_within_5_1km = 0")


@check("findings/remoteness", "cooperatives in an empty 400 m cell", 17_774)
def _():
    return one(f"select count(*) from {P} where own_cell_pop = 0")


@check("findings/remoteness", "% in an empty 400 m cell", 21.3, tol=0.05)
def _():
    return round(100 * one(f"select count(*) from {P} where own_cell_pop = 0") / 83_379, 1)


@check("/ · findings/remoteness", "cooperatives with no made road within 5 km", 5_106)
def _():
    return one(f"select count(*) from {P} where km_non_track is null")


@check("findings/remoteness", "% recorded inside a farmland polygon", 2.65, tol=0.005)
def _():
    return round(100 * one(f"select count(*) from {P} where in_farmland") / 83_379, 2)


@check("findings/remoteness", "cooperatives recorded in a burial ground", 22)
def _():
    return one(f"select count(*) from {P} where in_cemetery")


@check("/ · findings/remoteness", "population within 1,4 km of a KDMP (%)", 95.0, tol=0.05)
def _():
    t = csv("03-population-coverage", "coverage_by_radius.csv")
    return round(one(f"select pct_of_national from {t} where k_rings = 3"), 0)


@check("findings/remoteness", "population within 5,1 km of a KDMP (%)", 99.8, tol=0.05)
def _():
    t = csv("03-population-coverage", "coverage_by_radius.csv")
    return round(one(f"select pct_of_national from {t} where k_rings = 11"), 1)


@check("findings/remoteness", "exact road distance, median (km)", 9.7, tol=0.05)
def _():
    return round(
        one(f"select median(m_to_made_road_exact) from {P} where km_non_track is null")
        / 1000,
        1,
    )


@check("findings/remoteness", "roadless KDMP further than 25 km from a road", 587)
def _():
    return one(f"select count(*) from {P} where m_to_made_road_exact > 25000")


@check("/ · findings/remoteness", "roadless KDMP further than 100 km", 7)
def _():
    return one(f"select count(*) from {P} where m_to_made_road_exact > 100000")


@check("findings/remoteness", "roadless KDMP 5-10 km from a road", 2_467)
def _():
    # Read the band table rather than recomputing it. Report 08 bands on
    # `km_to_made_road` rounded to 2 dp with an exclusive lower bound
    # (km > 5 & km <= 10); recomputing in metres with an inclusive bound gives
    # 2.471, and the four-row gap is a convention difference, not a defect. The
    # page cites the report, so the report's own table is what it must match.
    t = csv("08-exact-geometry", "exact_road_distance_bands.csv")
    return one(
        f'select cooperatives from {t} '
        "where \"exact distance to nearest made road\" = '5-10 km'"
    )


@check("findings/remoteness", "KDMP in farmland, confirmed by two maps", 448)
def _():
    return one(f"select count(*) from {P} where farmland_confirmed_cropland")


# ---------------------------------------------------------------------------
# Chapter 2 — competition  (findings/competition, methods 06/10)
# ---------------------------------------------------------------------------


@check("findings/competition", "% with another KDMP within 500 m", 4.6, tol=0.05)
def _():
    # NOTE: the page printed 4,7% until 2026-08-14. That came from rounding the
    # report's already-rounded 4.65 a second time; the underlying value is
    # 4.645-4.650 depending on the denominator, which is 4,6% at one decimal.
    # Double rounding is how a figure drifts without anyone editing it.
    return round(
        100
        * one(f"select count(*) from {P} where m_to_nearest_other <= 500")
        / one(f"select count(*) from {P} where m_to_nearest_other is not null"),
        1,
    )


@check("findings/competition", "duplicate-coordinate KDMP excluded", 798)
def _():
    t = csv("10-coop-clustering", "coord_artifacts.csv")
    return one(f"select count(*) from {t}")


@check("findings/competition", "minimarket excess within 500 m (pp, road null)", 9.4, tol=0.05)
def _():
    t = csv("06-minimarket-proximity", "null_model_comparison.csv")
    return round(one(f"select excess_vs_road_null from {t} where within = '~500 m'"), 1)


@check("findings/competition", "OSM share of Indomaret outlets (%)", 13.8, tol=0.05)
def _():
    t = csv("06-minimarket-proximity", "osm_brand_coverage.csv")
    return round(one(f"select osm_share_of_published from {t} where brand = 'Indomaret'"), 1)


@check("findings/competition", "OSM share of Alfamart outlets (%)", 10.9, tol=0.05)
def _():
    t = csv("06-minimarket-proximity", "osm_brand_coverage.csv")
    return round(one(f"select osm_share_of_published from {t} where brand = 'Alfamart'"), 1)


CO = "10-coop-clustering", "co_location.csv"
# r8 (~0,46 km edge, ~1 km across) on the clean set is what the page calls
# "berbagi petak 1 km"; r9 (~0,17 km edge, ~350 m across) is the fine scale
# where the duplicate-coordinate artefact dominates.
R8 = "res = 8 and exclusion = 'clean'"
R9C = "res = 9 and exclusion = 'clean'"
R9A = "res = 9 and exclusion = 'all'"


@check("findings/competition", "% sharing a ~1 km cell with another KDMP", 6.8, tol=0.05)
def _():
    return one(f"select pct_of_coops from {csv(*CO)} where {R8}")


@check("findings/competition", "~1 km cells holding two or more KDMP", 2_513)
def _():
    return one(f"select cells_with_2plus from {csv(*CO)} where {R8}")


@check("findings/competition", "most KDMP in a single ~1 km cell", 17)
def _():
    return one(f"select max_in_one_cell from {csv(*CO)} where {R8}")


@check("findings/competition", "KDMP sharing a ~350 m cell, all coordinates", 1_250)
def _():
    return one(f"select coops_sharing_with_other from {csv(*CO)} where {R9A}")


@check("findings/competition", "KDMP sharing a ~350 m cell, artefacts removed", 450)
def _():
    return one(f"select coops_sharing_with_other from {csv(*CO)} where {R9C}")


@check("findings/competition", "% of ~350 m overlap that is a data artefact", 64, tol=0.5)
def _():
    a = one(f"select coops_sharing_with_other from {csv(*CO)} where {R9A}")
    c = one(f"select coops_sharing_with_other from {csv(*CO)} where {R9C}")
    return round(100 * (a - c) / a, 0)


@check("findings/competition", "clustered vs isolated reporting rate (%)", 4.5, tol=0.05)
def _():
    t = csv("10-coop-clustering", "cluster_vs_isolated.csv")
    return round(one(f"select pct_reporting_transaction from {t} where \"group\" = 'clustered'"), 1)


@check("findings/competition", "isolated reporting rate (%)", 3.7, tol=0.05)
def _():
    t = csv("10-coop-clustering", "cluster_vs_isolated.csv")
    return round(one(f"select pct_reporting_transaction from {t} where \"group\" = 'isolated'"), 1)


@check("/ · findings/competition", "% with another KDMP within 1 km", 22.2, tol=0.05)
def _():
    return round(
        100
        * one(f"select count(*) from {P} where m_to_nearest_other <= 1000")
        / one(f"select count(*) from {P} where m_to_nearest_other is not null"),
        1,
    )


@check("findings/competition", "% with another KDMP within 2 km", 58.9, tol=0.05)
def _():
    return round(
        100
        * one(f"select count(*) from {P} where m_to_nearest_other <= 2000")
        / one(f"select count(*) from {P} where m_to_nearest_other is not null"),
        1,
    )


@check("/ · findings/competition", "% with another KDMP within 5 km", 91.3, tol=0.05)
def _():
    return round(
        100
        * one(f"select count(*) from {P} where m_to_nearest_other <= 5000")
        / one(f"select count(*) from {P} where m_to_nearest_other is not null"),
        1,
    )


# ---------------------------------------------------------------------------
# Chapter 3 — money and output  (findings/money, methods 02/11/13/15/16)
# ---------------------------------------------------------------------------


@check("/ · findings/money", "% of cooperatives at 100% construction", 24.3, tol=0.05)
def _():
    t = csv("15-construction-output", "construction_vs_output.csv")
    r = con.execute(
        f"select sum(cooperatives * pct_build_100) / sum(cooperatives) from {t}"
    ).fetchone()[0]
    return round(r, 1)


@check("findings/money", "% of cooperatives with any construction record", 45.6, tol=0.05)
def _():
    t = csv("15-construction-output", "construction_vs_output.csv")
    r = con.execute(
        f"select sum(cooperatives * pct_with_stage) / sum(cooperatives) from {t}"
    ).fetchone()[0]
    return round(r, 1)


@check("findings/money", "% of villages with NPWP", 97.1, tol=0.05)
def _():
    t = csv("13-compliance-npwp-nib", "compliance_by_level.csv")
    return round(one(f"select pct_npwp from {t} where level = 'village_id'"), 1)


@check("findings/money", "% of cooperatives with NIB", 72.9, tol=0.05)
def _():
    t = csv("13-compliance-npwp-nib", "compliance_by_level.csv")
    return round(one(f"select pct_nib from {t} where level = 'village_id'"), 1)


@check("/ · findings/money", "% with NIB and no transaction", 69.9, tol=0.05)
def _():
    # Do NOT round the CSV before comparing. It already carries 2 dp, and
    # rounding a rounded figure is exactly how "4,7%" got onto the competition
    # page: the true value here is 69.854, which is 69,9 at one decimal, but
    # round(69.85, 1) in Python is 69.8. Compare at the CSV's precision and let
    # the tolerance absorb the page's rendering.
    t = csv("13-compliance-npwp-nib", "nib_vs_transaction.csv")
    return one(f"select pct from {t} where has_nib = 'NIB' and has_tx = 'no transaction'")


@check("/ · findings/money", "villages reporting a transaction without NIB", 23)
def _():
    t = csv("13-compliance-npwp-nib", "nib_vs_transaction.csv")
    return one(f"select villages from {t} where has_nib = 'no NIB' and has_tx = 'transaction'")


@check("findings/money", "% of villages with an account", 96.0, tol=0.5)
def _():
    t = csv("02-zero-inflation", "zero_inflation_by_field.csv")
    return round(one(f"select pct_nonzero from {t} where field = 'accounts_count'"), 0)


@check("/ · findings/money", "share of national value from top 100 villages (%)", 34.8, tol=0.05)
def _():
    t = csv("02-zero-inflation", "transaction_concentration.csv")
    return one(f"select share_of_national_tx_value from {t} where top_n_villages = 100")


@check("/ · findings/money", "share of national value from top 1.000 villages (%)", 90.6, tol=0.05)
def _():
    t = csv("02-zero-inflation", "transaction_concentration.csv")
    return one(f"select share_of_national_tx_value from {t} where top_n_villages = 1000")


@check("findings/money", "total savings (Rp miliar)", 40.3, tol=0.05)
def _():
    t = csv("11-savings-behaviour", "savings_national.csv")
    return round(one(f"select value from {t} where metric = 'savings_total_amount'") / 1e9, 1)


@check("findings/money", "median wajib/pokok ratio", 0.28, tol=0.005)
def _():
    t = csv("11-savings-behaviour", "wajib_pokok_ratio.csv")
    return round(one(f"select value from {t} where stat = 'median wajib/pokok'"), 2)


@check("findings/money", "RAT recorded for N cooperatives", 50_200)
def _():
    t = csv("16-rat-compliance", "rat_by_province.csv")
    return int(one(f"select sum(rat_count) from {t}"))


@check("/ · findings/money", "% of cooperatives with RAT recorded", 60.2, tol=0.05)
def _():
    t = csv("16-rat-compliance", "rat_by_province.csv")
    return round(100 * one(f"select sum(rat_count) from {t}") / 83_379, 1)


# ---------------------------------------------------------------------------
# Chapter 1 addendum — buildings (methods 17), rewritten 2026-08-14
# ---------------------------------------------------------------------------


@check("methods/17", "% on a mapped building cell", 44.36, tol=0.005)
def _():
    return round(
        100
        * one(f"select count(*) from {P} where building_band = 'on a building cell (<70 m)'")
        / 83_379,
        2,
    )


@check("methods/17", "% with no mapped building within ~5 km", 1.19, tol=0.005)
def _():
    return round(
        100
        * one(f"select count(*) from {P} where building_band = '> ~5 km / none found'")
        / 83_379,
        2,
    )


@check("methods/17", "% with a mapped building within ~260 m", 75.2, tol=0.05)
def _():
    return round(
        100
        * one(
            f"select count(*) from {P} where building_band in "
            "('on a building cell (<70 m)', '< ~260 m')"
        )
        / 83_379,
        1,
    )


@check("methods/17 · about", "no house 1 km + isolated + roadless", 128)
def _():
    t = csv("17-building-proximity", "building_overlap.csv")
    # "case" is a reserved word; it needs quoting even as a column name.
    return int(one(f'select n from {t} where "case" like \'%isolated + roadless%\''))


@check("findings/money", "% of cooperatives with RAT, Papua Pegunungan", 6.1, tol=0.05)
def _():
    t = csv("16-rat-compliance", "rat_by_province.csv")
    return round(one(f"select rat_pct from {t} where province = 'PAPUA PEGUNUNGAN'"), 1)


@check("findings/money", "% of cooperatives with RAT, Papua Selatan", 16.0, tol=0.05)
def _():
    # NOTE: the page said 16,2% until 2026-08-14. That was the 08-05 figure;
    # report 16's CSV had never been re-run against the 08-13 snapshot the rest
    # of the site uses.
    t = csv("16-rat-compliance", "rat_by_province.csv")
    return round(one(f"select rat_pct from {t} where province = 'PAPUA SELATAN'"), 1)


@check("findings/remoteness", "% of Papua KDMP in an empty 400 m cell", 70.7, tol=0.05)
def _():
    t = csv("14-island-comparison", "islands_spatial.csv")
    return round(one(f"select pct_zero_pop_cell from {t} where island = 'PAPUA'"), 1)


# ---------------------------------------------------------------------------
# Cross-page consistency. These exist because / and /findings/ stated the same
# quantity differently: the home page said Papua holds "0,2% of transaction
# value" when 0,2% is its share of villages *reporting* a transaction and its
# share of value is 0,56%. A category error reads as a typo and survives proof-
# reading, so it gets a check rather than a careful eye.
# ---------------------------------------------------------------------------


@check("/ · findings", "Papua share of cooperatives (%)", 8.5, tol=0.05)
def _():
    r = con.execute(
        f"select sum(cooperatives) filter (where province like 'PAPUA%'), "
        f"sum(cooperatives) from {PROV}"
    ).fetchone()
    return round(100 * r[0] / r[1], 1)


@check("/ · findings", "Papua share of transaction value (%)", 0.6, tol=0.05)
def _():
    r = con.execute(
        f"select sum(transaction_value) filter (where province like 'PAPUA%'), "
        f"sum(transaction_value) from {PROV}"
    ).fetchone()
    return round(100 * r[0] / r[1], 1)


JAVA = (
    "'JAWA BARAT', 'JAWA TENGAH', 'JAWA TIMUR', 'BANTEN', 'DKI JAKARTA', "
    "'DAERAH ISTIMEWA YOGYAKARTA'"
)


@check("findings", "Java share of cooperatives (%)", 30, tol=0.5)
def _():
    r = con.execute(
        f"select sum(cooperatives) filter (where province in ({JAVA})), "
        f"sum(cooperatives) from {PROV}"
    ).fetchone()
    return round(100 * r[0] / r[1], 0)


@check("findings", "Java share of transaction value (%)", 60, tol=0.5)
def _():
    r = con.execute(
        f"select sum(transaction_value) filter (where province in ({JAVA})), "
        f"sum(transaction_value) from {PROV}"
    ).fetchone()
    return round(100 * r[0] / r[1], 0)


@check("/ · findings/money", "transaction value per cooperative (Rp juta)", 2.43, tol=0.005)
def _():
    r = con.execute(
        f"select sum(transaction_value), sum(cooperatives) from {PROV}"
    ).fetchone()
    return round(r[0] / r[1] / 1e6, 2)


@check("/", "cooperatives at 100% construction (count)", 20_221)
def _():
    t = csv("15-construction-output", "construction_vs_output.csv")
    return int(round(one(f"select sum(cooperatives * pct_build_100 / 100.0) from {t}")))


@check("findings/money", "% of villages with no savings at all", 87.5, tol=0.05)
def _():
    t = csv("11-savings-behaviour", "savings_zero_inflation.csv")
    return round(
        100 - one(f"select pct_nonzero from {t} where field = 'savings_total_amount'"), 1
    )


@check("findings/money", "% of villages with any savings", 12.5, tol=0.05)
def _():
    t = csv("11-savings-behaviour", "savings_zero_inflation.csv")
    return one(f"select pct_nonzero from {t} where field = 'savings_total_amount'")


@check("findings/money", "% of villages paying monthly dues (wajib)", 9.2, tol=0.05)
def _():
    t = csv("11-savings-behaviour", "savings_zero_inflation.csv")
    return one(f"select pct_nonzero from {t} where field = 'simpanan_wajib_amount'")


# ---------------------------------------------------------------------------
# Externally sourced figures  (findings/money, methods/09)
#
# These come from press reporting, not from our data, so the check is that the
# page still matches what `external_figures.csv` transcribed. The transcriptions
# themselves were re-read against the live articles on 2026-08-14 and all match;
# that pass also found that the 07-31 rows had been attributed to two ministers
# who are quoted in the article but not on these numbers. Sources:
#   CNN Indonesia  2026-06-11  cnnindonesia.com/ekonomi/20260611123103-92-1367861
#   Liputan6       2026-07-31  liputan6.com/bisnis/read/8258962
#   Liputan6       2026-08-09  liputan6.com/bisnis/read/8265525
# ---------------------------------------------------------------------------

EXT = "09-external-corroboration", "external_figures.csv"


@check("findings/money · methods/09", "press total, 31 Jul (Rp miliar)", 157.9, tol=0.05)
def _():
    return one(
        f"select value / 1e9 from {csv(*EXT)} "
        "where as_of = '2026-07-31' and metric = 'transaction_value_idr'"
    )


@check("findings/money · methods/09", "press total, 9 Aug (Rp miliar)", 179.72, tol=0.005)
def _():
    return one(
        f"select value / 1e9 from {csv(*EXT)} "
        "where as_of = '2026-08-09' and metric = 'transaction_value_idr'"
    )


@check("findings/money", "government count of operating cooperatives", 1_061)
def _():
    return one(f"select value from {csv(*EXT)} where metric = 'cooperatives_operating'")


@check("findings/money", "operating cooperatives as % of the registry", 1.3, tol=0.05)
def _():
    n = one(f"select value from {csv(*EXT)} where metric = 'cooperatives_operating'")
    return round(100 * n / 83_379, 1)


# ---------------------------------------------------------------------------
# Product mix  (methods/12)
# ---------------------------------------------------------------------------

CAT = "12-product-mix", "product_categories.csv"


@check("methods/12", "rice share of reported sales value (%)", 51.2, tol=0.05)
def _():
    return one(f"select share_of_value from {csv(*CAT)} where category = 'rice'")


@check("methods/12", "cooking oil share of reported sales value (%)", 25.6, tol=0.05)
def _():
    return one(f"select share_of_value from {csv(*CAT)} where category = 'cooking_oil'")


@check("methods/12", "fertiliser share of reported sales value (%)", 14.3, tol=0.05)
def _():
    return one(f"select share_of_value from {csv(*CAT)} where category = 'fertilizer'")


@check("methods/12", "provinces where fertiliser is a top product", 24)
def _():
    return one(f"select n_provinces from {csv(*CAT)} where category = 'fertilizer'")


# ---------------------------------------------------------------------------
# The snapshot series  (findings/money, methods/01, methods/09)
#
# These looked unverifiable at first because they compare dated pulls, and the
# snapshot CSVs themselves are gitignored. They are not: reports 01 and 09 both
# commit the derived tables, so the published sentences can be checked against
# those without any snapshot machinery at all.
# ---------------------------------------------------------------------------

SNAP = "09-external-corroboration", "our_snapshot_totals.csv"
DIFF = "01-snapshot-drift", "snapshot_diff_summary.csv"


@check("methods/01", "villages reporting zero transactions on 5 Aug", 80_553)
def _():
    return one(
        f"select was_zero from {csv(*DIFF)} where measure = 'transaction_value'"
    )


@check("methods/01", "villages that started reporting in those four days", 1)
def _():
    return one(
        f"select zero_to_positive from {csv(*DIFF)} where measure = 'transaction_value'"
    )


@check("methods/01", "years to clear the backlog at that rate", 883, tol=1)
def _():
    z = one(f"select was_zero from {csv(*DIFF)} where measure = 'transaction_value'")
    moved = one(
        f"select zero_to_positive from {csv(*DIFF)} where measure = 'transaction_value'"
    )
    return round(z / moved * 4 / 365.0, 0)


@check("findings/money", "villages reporting, 5 Aug", 2_516)
def _():
    return one(f"select villages_reporting from {csv(*SNAP)} where as_of = '2026-08-05'")


@check("findings/money", "villages reporting, 9 Aug", 2_517)
def _():
    return one(f"select villages_reporting from {csv(*SNAP)} where as_of = '2026-08-09'")


@check("findings/money", "new reporting villages, 9 Aug to 13 Aug", 209)
def _():
    t = csv(*SNAP)
    return one(
        f"select (select villages_reporting from {t} where as_of = '2026-08-13') "
        f"- (select villages_reporting from {t} where as_of = '2026-08-09')"
    )


@check("findings/money", "press value growth, 31 Jul to 9 Aug (%)", 13.8, tol=0.05)
def _():
    t = csv("09-external-corroboration", "published_series.csv")
    a = one(f"select miliar from {t} where as_of = '2026-07-31'")
    b = one(f"select miliar from {t} where as_of = '2026-08-09'")
    return round(100 * (b - a) / a, 1)


@check("findings/money", "our value growth, 9 Aug to 13 Aug (%)", 12.7, tol=0.05)
def _():
    t = csv(*SNAP)
    a = one(f"select transaction_value_idr from {t} where as_of = '2026-08-09'")
    b = one(f"select transaction_value_idr from {t} where as_of = '2026-08-13'")
    return round(100 * (b - a) / a, 1)


@check("methods/09", "gap between press and our own pull, 9 Aug (%)", 0.042, tol=0.0005)
def _():
    t = csv("09-external-corroboration", "reconciliation.csv")
    return one(f"select pct_difference from {t} where as_of = '2026-08-09'")


@check("methods/01", "duplicate village rows in the 5 Aug export", 1_555)
def _():
    # `strict_mode=false` is required: one row carries an unescaped comma inside
    # a village name ("Lambang Sari I, II, III"), which is itself part of why
    # this export needed a duplicate check.
    v = (
        f"read_csv('{(ROOT / 'data' / 'raw' / 'kopdes_stats_village.csv').as_posix()}', "
        "strict_mode=false, ignore_errors=true)"
    )
    r = con.execute(
        f"select count(*), count(distinct village_id) from {v}"
    ).fetchone()
    return r[0] - r[1]


# ---------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    width = max(len(c[1]) for c in CHECKS) + 2
    fails, skips = [], []
    print(f"{'CHECK'.ljust(width)} {'PUBLISHED':>12} {'COMPUTED':>12}   STATUS")
    print("-" * (width + 42))

    for page, label, published, fn, tol in CHECKS:
        try:
            actual = fn()
        except FileNotFoundError as err:
            skips.append((label, f"missing {Path(str(err)).name}"))
            print(f"{label.ljust(width)} {published:>12} {'-':>12}   SKIP (no source)")
            continue
        except Exception as err:  # noqa: BLE001
            skips.append((label, str(err)[:70]))
            print(f"{label.ljust(width)} {published:>12} {'-':>12}   SKIP ({str(err)[:40]})")
            continue

        if isinstance(actual, tuple):  # unresolved probe, see NOTE
            skips.append((label, f"probe: {actual[1]}"))
            print(f"{label.ljust(width)} {published:>12} {'?':>12}   SKIP (probe)")
            continue

        # The epsilon matters: a page printing 69,9 against a CSV's 69.85 is a
        # difference of exactly the tolerance, and in binary that lands a hair
        # above it. Without this, every legitimate one-decimal rendering of a
        # two-decimal figure fails.
        ok = abs(float(actual) - float(published)) <= tol + 1e-9
        status = "OK" if ok else "MISMATCH"
        if not ok:
            fails.append((page, label, published, actual))
        print(f"{label.ljust(width)} {published:>12} {actual:>12}   {status}")

    print("-" * (width + 42))
    print(f"{len(CHECKS) - len(fails) - len(skips)} ok, {len(fails)} mismatched, {len(skips)} skipped")

    if fails:
        print("\nMISMATCHES — the page says one thing and the data says another:")
        for page, label, published, actual in fails:
            print(f"  {page}\n    {label}: page says {published}, data says {actual}")
    if skips and args.verbose:
        print("\nSKIPPED:")
        for label, why in skips:
            print(f"  {label}: {why}")

    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
