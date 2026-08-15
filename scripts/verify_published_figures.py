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
import json
import re
import sys
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Callable

import duckdb

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "data" / "web"
REPORTS = ROOT / "reports"

con = duckdb.connect()
P = f"read_parquet('{(WEB / 'kopdes_points.parquet').as_posix()}')"
PROV = f"read_parquet('{(WEB / 'kopdes_provinsi.parquet').as_posix()}')"

CHECKS = []


@dataclass
class Check:
    page: str
    label: str
    published: float
    fn: Callable
    tol: float
    key: str | None  # registry id, set on the figures bound into the prose
    fmt: str | None  # how that figure is rendered in Indonesian


def check(page, label, published, tol=0.0, key=None, fmt=None):
    """Register a check. The decorated function returns the computed value.

    Passing `key` and `fmt` additionally publishes the figure to
    `data/web/figures.json` (see --emit), which is what lets a page bind the
    number instead of restating it. A check without a key is still verified; it
    is simply not one of the figures the prose reads back.
    """

    def wrap(fn):
        CHECKS.append(Check(page, label, published, fn, tol, key, fmt))
        return fn

    return wrap


# ---------------------------------------------------------------------------
# Indonesian number rendering
#
# The registry ships the *rendered string*, not just the value, and the page
# injects that string verbatim. Formatting deliberately lives here alone: a
# second implementation in JavaScript would be a second thing to keep in step,
# and "the two formatters disagreed" is the same failure mode as the stale
# prose this whole mechanism exists to remove.
#
#   int   83.379        thousands separated with a full stop
#   dec1  202,6         decimal comma, N decimal places, no unit
#   pct1  24,3%         the same with a per-cent sign
#
# Units (Rp, miliar, km) stay in the prose. They are wording, not data, and a
# figure that changes magnitude needs a human to re-read the sentence anyway.
# ---------------------------------------------------------------------------

FMT = re.compile(r"^(int|dec(\d)|pct(\d))$")


def round_half_up(value, places):
    """Round the way a person writing the sentence rounds.

    Python rounds halves to even, so 69.85 becomes 69.8 and 14.25 becomes 14.2.
    Every page here rounds a half upward, which is why the prose says 69,9% and
    14,3%. Rendering with the built-in would have declared five correct
    sentences stale on the first run, and "the checker is wrong" is a fast way
    to teach everyone to ignore the checker.
    """
    q = Decimal(1).scaleb(-places)
    return Decimal(str(value)).quantize(q, rounding=ROUND_HALF_UP)


def render(value, fmt):
    """Render `value` the way the Indonesian prose prints it."""
    m = FMT.match(fmt or "")
    if not m:
        raise ValueError(f"unknown figure format {fmt!r}")
    if m.group(1) == "int":
        return f"{int(round_half_up(value, 0)):,}".replace(",", ".")
    places = int(m.group(2) or m.group(3))
    body = f"{round_half_up(value, places):,.{places}f}"
    body = body.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return body + ("%" if fmt.startswith("pct") else "")


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


@check("/ · findings · tabel · explore", "cooperatives in the mart", 83_379, key="coops_total", fmt="int")
def _():
    return one(f"select count(*) from {P}")


@check("/ · findings", "provinces", 38, key="provinces", fmt="int")
def _():
    return one(f"select count(distinct province) from {P}")


@check("/ · findings/money", "national transaction value (Rp miliar)", 202.6, tol=0.05, key="transaction_value_miliar", fmt="dec1")
def _():
    return round(one(f"select sum(transaction_value) from {PROV}") / 1e9, 1)


@check("findings/money", "villages reporting a transaction", 2_726, key="villages_reporting", fmt="int")
def _():
    return one(f"select sum(villages_reporting) from {PROV}")


@check("/ · findings/money", "% of villages reporting a transaction", 3.3, tol=0.05, key="villages_reporting_pct", fmt="pct1")
def _():
    r = con.execute(
        f"select sum(villages_reporting), sum(villages) from {PROV}"
    ).fetchone()
    return round(100 * r[0] / r[1], 1)


# ---------------------------------------------------------------------------
# Chapter 1 — access and placement  (/, findings/remoteness, methods 03/05/07)
# ---------------------------------------------------------------------------


@check("/ · findings/remoteness", "cooperatives with nobody within 5,1 km", 146, key="no_pop_within_5_1km", fmt="int")
def _():
    return one(f"select count(*) from {P} where pop_within_5_1km = 0")


@check("findings/remoteness", "cooperatives in an empty 400 m cell", 17_774, key="empty_cell_coops", fmt="int")
def _():
    return one(f"select count(*) from {P} where own_cell_pop = 0")


@check("findings/remoteness", "% in an empty 400 m cell", 21.3, tol=0.05, key="empty_cell_pct", fmt="pct1")
def _():
    return round(100 * one(f"select count(*) from {P} where own_cell_pop = 0") / 83_379, 1)


@check("/ · findings/remoteness", "cooperatives with no made road within 5 km", 5_106, key="no_made_road_coops", fmt="int")
def _():
    return one(f"select count(*) from {P} where km_non_track is null")


@check("findings/remoteness", "% recorded inside a farmland polygon", 2.65, tol=0.005, key="in_farmland_pct", fmt="pct2")
def _():
    return round(100 * one(f"select count(*) from {P} where in_farmland") / 83_379, 2)


@check("findings/remoteness", "cooperatives recorded in a burial ground", 22, key="in_cemetery_coops", fmt="int")
def _():
    return one(f"select count(*) from {P} where in_cemetery")


@check("/ · findings/remoteness", "population within 1,4 km of a KDMP (%)", 95.0, tol=0.05, key="pop_within_1_4km_pct", fmt="pct0")
def _():
    t = csv("03-population-coverage", "coverage_by_radius.csv")
    return round(one(f"select pct_of_national from {t} where k_rings = 3"), 0)


@check("findings/remoteness", "population within 5,1 km of a KDMP (%)", 99.8, tol=0.05, key="pop_within_5_1km_pct", fmt="pct1")
def _():
    t = csv("03-population-coverage", "coverage_by_radius.csv")
    return round(one(f"select pct_of_national from {t} where k_rings = 11"), 1)


@check("findings/remoteness", "exact road distance, median (km)", 9.7, tol=0.05, key="roadless_median_km", fmt="dec1")
def _():
    return round(
        one(f"select median(m_to_made_road_exact) from {P} where km_non_track is null")
        / 1000,
        1,
    )


@check("findings/remoteness", "roadless KDMP further than 25 km from a road", 587, key="roadless_over_25km", fmt="int")
def _():
    return one(f"select count(*) from {P} where m_to_made_road_exact > 25000")


@check("/ · findings/remoteness", "roadless KDMP further than 100 km", 7, key="roadless_over_100km", fmt="int")
def _():
    return one(f"select count(*) from {P} where m_to_made_road_exact > 100000")


@check("findings/remoteness", "roadless KDMP 5-10 km from a road", 2_467, key="roadless_5_10km", fmt="int")
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


@check("findings/remoteness", "KDMP in farmland, confirmed by two maps", 448, key="farmland_confirmed", fmt="int")
def _():
    return one(f"select count(*) from {P} where farmland_confirmed_cropland")


# Chapter 1's remaining literals, bound 2026-08-15. Every one of these was
# typed into the prose and never checked, and three of them had gone stale
# against a re-run: methods/08 was still printing 16 cooperatives beyond 100 km
# where the data says 7, and a 292 km maximum where the data says 186.
@check("findings/remoteness", "% with nobody within 5,1 km", 0.18, tol=0.005, key="no_pop_within_5_1km_pct", fmt="pct2")
def _():
    return round(100 * one(f"select count(*) from {P} where pop_within_5_1km = 0") / 83_379, 2)


@check("findings/remoteness", "% with no made road within 5 km", 6.1, tol=0.05, key="no_made_road_pct", fmt="pct1")
def _():
    return round(100 * one(f"select count(*) from {P} where km_non_track is null") / 83_379, 1)


@check("findings/remoteness", "cooperatives with no road of any kind within 5 km", 4_294, key="no_any_road_coops", fmt="int")
def _():
    return one(f"select count(*) from {P} where km_any_road is null")


# The page said 5,2%. 4.294 / 83.379 is 5,14997%, which is 5,1 at one decimal
# however you round it. A hand-typed percentage that nobody recomputed.
@check("findings/remoteness", "% with no road of any kind within 5 km", 5.1, tol=0.05, key="no_any_road_pct", fmt="pct1")
def _():
    return round(100 * one(f"select count(*) from {P} where km_any_road is null") / 83_379, 1)


@check("findings/remoteness", "roadless KDMP 10-25 km from a road", 1_872, key="roadless_10_25km", fmt="int")
def _():
    t = csv("08-exact-geometry", "exact_road_distance_bands.csv")
    return one(f'select cooperatives from {t} where "exact distance to nearest made road" = \'10-25 km\'')


@check("findings/remoteness", "roadless KDMP 25-50 km from a road", 523, key="roadless_25_50km", fmt="int")
def _():
    t = csv("08-exact-geometry", "exact_road_distance_bands.csv")
    return one(f'select cooperatives from {t} where "exact distance to nearest made road" = \'25-50 km\'')


@check("findings/remoteness", "roadless KDMP 50-100 km from a road", 57, key="roadless_50_100km", fmt="int")
def _():
    t = csv("08-exact-geometry", "exact_road_distance_bands.csv")
    return one(f'select cooperatives from {t} where "exact distance to nearest made road" = \'50-100 km\'')


@check("findings/remoteness · methods/08", "furthest KDMP from a made road (km)", 185.9, tol=0.05, key="roadless_max_km", fmt="dec1")
def _():
    return round(one(f"select max(m_to_made_road_exact) from {P}") / 1000, 1)


@check("methods/08", "90th percentile road distance, roadless set (km)", 26.4, tol=0.05, key="roadless_p90_km", fmt="dec1")
def _():
    return round(
        one(
            f"select quantile_cont(m_to_made_road_exact, 0.9) from {P} "
            "where km_non_track is null"
        )
        / 1000,
        1,
    )


@check("findings/remoteness · methods/07", "% of OSM village nodes inside farmland", 1.10, tol=0.005, key="village_node_farmland_pct", fmt="pct2")
def _():
    t = csv("07-landuse-polygons", "null_comparison.csv")
    return one(f"select pct from {t} where class = 'farmland' and \"group\" = 'osm_village_node'")


@check("findings/remoteness · methods/07", "% of OSM village nodes inside a cemetery", 0.022, tol=0.0005, key="village_node_cemetery_pct", fmt="pct3")
def _():
    t = csv("07-landuse-polygons", "null_comparison.csv")
    return one(f"select pct from {t} where class = 'cemetery' and \"group\" = 'osm_village_node'")


@check("findings/remoteness · methods/07", "% of KDMP inside a cemetery", 0.026, tol=0.0005, key="in_cemetery_pct", fmt="pct3")
def _():
    t = csv("07-landuse-polygons", "null_comparison.csv")
    return one(f"select pct from {t} where class = 'cemetery' and \"group\" = 'kdmp'")


@check("methods/07", "KDMP inside a mapped farmland polygon", 2_209, key="in_farmland_coops", fmt="int")
def _():
    t = csv("07-landuse-polygons", "farmland_funnel.csv")
    return one(f"select cooperatives from {t} where step = 'inside a mapped farmland polygon'")


@check("methods/07", "farmland candidates surviving the funnel", 538, key="farmland_candidates", fmt="int")
def _():
    t = csv("07-landuse-polygons", "farmland_funnel.csv")
    return one(f"select cooperatives from {t} where step like '%< 2 villages%'")


@check("findings/remoteness · methods/04", "most-remote 2.500: land officially verified", 384, key="remote_land_verified", fmt="int")
def _():
    t = csv("04-siting-screen", "candidates.csv")
    return one(f"select count(*) from {t} where land_status = 'Terverifikasi'")


@check("findings/remoteness · methods/04", "… and also on a steep slope", 175, key="remote_verified_steep", fmt="int")
def _():
    t = csv("04-siting-screen", "candidates.csv")
    return one(f"select count(*) from {t} where land_status = 'Terverifikasi' and flag_steep")


@check("findings/remoteness · methods/08", "impossible coordinates in the 5 Aug export", 20, key="impossible_coords", fmt="int")
def _():
    t = csv("08-exact-geometry", "corrected_coordinates_2026-08.csv")
    return one(f"select count(*) from {t}")


@check("findings/remoteness · methods/08", "… of those, latitude sign flips", 19, key="impossible_coords_signflip", fmt="int")
def _():
    t = csv("08-exact-geometry", "corrected_coordinates_2026-08.csv")
    return one(f"select count(*) from {t} where diagnosis like 'latitude sign flipped%'")


@check("findings/remoteness · methods/14", "Papua median distance to a mapped minimarket (km)", 74.4, tol=0.05, key="papua_median_km_minimarket", fmt="dec1")
def _():
    t = csv("14-island-comparison", "islands_spatial.csv")
    return round(one(f"select median_km_to_minimarket from {t} where island = 'PAPUA'"), 1)


@check("findings/remoteness · methods/14", "Java median distance to a mapped minimarket (km)", 6.7, tol=0.05, key="java_median_km_minimarket", fmt="dec1")
def _():
    t = csv("14-island-comparison", "islands_spatial.csv")
    return round(one(f"select median_km_to_minimarket from {t} where island = 'JAVA'"), 1)


@check("findings/remoteness · methods/14", "Papua share with land verified (%)", 3.1, tol=0.05, key="papua_land_verified_pct", fmt="pct1")
def _():
    t = csv("14-island-comparison", "islands_spatial.csv")
    return round(one(f"select pct_land_verified from {t} where island = 'PAPUA'"), 1)


@check("findings/remoteness · methods/14", "Java share with land verified (%)", 62.7, tol=0.05, key="java_land_verified_pct", fmt="pct1")
def _():
    t = csv("14-island-comparison", "islands_spatial.csv")
    return round(one(f"select pct_land_verified from {t} where island = 'JAVA'"), 1)


@check("findings/remoteness · methods/14", "% of Java KDMP in an empty 400 m cell", 2.6, tol=0.05, key="java_empty_cell_pct", fmt="pct1")
def _():
    t = csv("14-island-comparison", "islands_spatial.csv")
    return round(one(f"select pct_zero_pop_cell from {t} where island = 'JAVA'"), 1)


# ---------------------------------------------------------------------------
# Chapter 2 — competition  (findings/competition, methods 06/10)
# ---------------------------------------------------------------------------


@check("findings/competition", "% with another KDMP within 500 m", 4.6, tol=0.05, key="other_within_500m_pct", fmt="pct1")
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


@check("findings/competition", "duplicate-coordinate KDMP excluded", 798, key="duplicate_coord_coops", fmt="int")
def _():
    t = csv("10-coop-clustering", "coord_artifacts.csv")
    return one(f"select count(*) from {t}")


# The chapter's headline, rewritten 2026-08-15.
#
# It used to be `excess_vs_road_null`, the excess over a road+population-
# weighted null, quoted as 9,4 from a single draw. Two things were wrong with
# that. The null landed in cells of median 2,374 people against the
# minimarkets' 3,786, so it was not standing in for them on the dimension that
# drives the result; matching the distribution takes the excess from ~9,6 to
# ~6,7. And a single draw is a sample, not an estimate: redrawing the old null
# 40 times spans 8,2 to 10,4. Both figures now come from
# `null_excess_published.csv`, which carries the redraw mean and its range.
PUB = "06-minimarket-proximity", "null_excess_published.csv"


@check("findings/competition", "minimarket excess within 500 m (pp, matched null)", 6.7, tol=0.05, key="minimarket_excess_pp", fmt="dec1")
def _():
    return round(one(f"select excess_pp from {csv(*PUB)} where within = '~500 m'"), 1)


@check("findings/competition", "minimarket excess within 500 m, low end", 5.7, tol=0.05, key="minimarket_excess_lo", fmt="dec1")
def _():
    return round(one(f"select lo95 from {csv(*PUB)} where within = '~500 m'"), 1)


@check("findings/competition", "minimarket excess within 500 m, high end", 7.7, tol=0.05, key="minimarket_excess_hi", fmt="dec1")
def _():
    return round(one(f"select hi95 from {csv(*PUB)} where within = '~500 m'"), 1)


@check("findings/competition", "minimarket excess within 1 km (pp, matched null)", 3.7, tol=0.05, key="minimarket_excess_1km_pp", fmt="dec1")
def _():
    return round(one(f"select excess_pp from {csv(*PUB)} where within = '~1 km'"), 1)


@check("findings/competition", "minimarket excess within 2 km (pp, matched null)", 1.5, tol=0.05, key="minimarket_excess_2km_pp", fmt="dec1")
def _():
    return round(one(f"select excess_pp from {csv(*PUB)} where within = '~2 km'"), 1)


@check("findings/competition", "minimarket excess within 5 km (pp, matched null)", 0.2, tol=0.05, key="minimarket_excess_5km_pp", fmt="dec1")
def _():
    return round(one(f"select excess_pp from {csv(*PUB)} where within = '~5 km'"), 1)


@check("methods/06", "minimarket excess within 500 m (pp, weaker road null)", 9.6, tol=0.05, key="minimarket_excess_road_pp", fmt="dec1")
def _():
    t = csv("06-minimarket-proximity", "null_stability.csv")
    return round(
        one(f"select mean_excess_pp from {t} "
            "where \"null\" = 'road + pop-weighted' and within = '~500 m'"),
        1,
    )


@check("methods/06", "median population, minimarket cell", 3_786, key="mm_median_pop", fmt="int")
def _():
    t = csv("06-minimarket-proximity", "null_density_match.csv")
    return one(f"select median_pop_own_400m_cell from {t} where points = 'minimarket (tier 1)'")


@check("methods/06", "median population, road+pop-weighted null cell", 2_374, key="road_null_median_pop", fmt="int")
def _():
    t = csv("06-minimarket-proximity", "null_density_match.csv")
    return one(
        f"select median_pop_own_400m_cell from {t} "
        "where points = 'null: road + pop-weighted'"
    )


@check("findings/competition", "% of mapped minimarkets with a KDMP within 500 m", 43.8, tol=0.05, key="minimarket_with_kdmp_500m_pct", fmt="pct1")
def _():
    t = csv("06-minimarket-proximity", "null_model_comparison.csv")
    return one(f"select pct_minimarkets from {t} where within = '~500 m'")


@check("findings/competition", "% of matched random points with a KDMP within 500 m", 37.1, tol=0.05, key="matched_null_500m_pct", fmt="pct1")
def _():
    # The figure prints minimarkets minus excess, so it has to be the same
    # arithmetic the page states: 43,8 - 6,7. Reading the single draw's 36,71
    # here would make the diagram fail to add up.
    t = csv("06-minimarket-proximity", "null_model_comparison.csv")
    mm = one(f"select pct_minimarkets from {t} where within = '~500 m'")
    return round(mm - one(f"select excess_pp from {csv(*PUB)} where within = '~500 m'"), 1)


@check("findings/competition", "OSM share of Indomaret outlets (%)", 13.8, tol=0.05, key="osm_share_indomaret_pct", fmt="pct1")
def _():
    t = csv("06-minimarket-proximity", "osm_brand_coverage.csv")
    return round(one(f"select osm_share_of_published from {t} where brand = 'Indomaret'"), 1)


@check("findings/competition", "OSM share of Alfamart outlets (%)", 10.9, tol=0.05, key="osm_share_alfamart_pct", fmt="pct1")
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


@check("findings/competition", "% sharing a ~1 km cell with another KDMP", 6.8, tol=0.05, key="sharing_1km_cell_pct", fmt="pct1")
def _():
    return one(f"select pct_of_coops from {csv(*CO)} where {R8}")


@check("findings/competition", "~1 km cells holding two or more KDMP", 2_513, key="cells_with_2plus", fmt="int")
def _():
    return one(f"select cells_with_2plus from {csv(*CO)} where {R8}")


@check("findings/competition", "most KDMP in a single ~1 km cell", 17, key="max_in_one_cell", fmt="int")
def _():
    return one(f"select max_in_one_cell from {csv(*CO)} where {R8}")


@check("findings/competition", "KDMP sharing a ~350 m cell, all coordinates", 1_250, key="sharing_350m_all", fmt="int")
def _():
    return one(f"select coops_sharing_with_other from {csv(*CO)} where {R9A}")


@check("findings/competition", "KDMP sharing a ~350 m cell, artefacts removed", 450, key="sharing_350m_clean", fmt="int")
def _():
    return one(f"select coops_sharing_with_other from {csv(*CO)} where {R9C}")


@check("findings/competition", "% of ~350 m overlap that is a data artefact", 64, tol=0.5, key="overlap_artefact_pct", fmt="pct0")
def _():
    a = one(f"select coops_sharing_with_other from {csv(*CO)} where {R9A}")
    c = one(f"select coops_sharing_with_other from {csv(*CO)} where {R9C}")
    return round(100 * (a - c) / a, 0)


@check("findings/competition", "clustered vs isolated reporting rate (%)", 4.5, tol=0.05, key="clustered_reporting_pct", fmt="pct1")
def _():
    t = csv("10-coop-clustering", "cluster_vs_isolated.csv")
    return round(one(f"select pct_reporting_transaction from {t} where \"group\" = 'clustered'"), 1)


@check("findings/competition", "isolated reporting rate (%)", 3.7, tol=0.05, key="isolated_reporting_pct", fmt="pct1")
def _():
    t = csv("10-coop-clustering", "cluster_vs_isolated.csv")
    return round(one(f"select pct_reporting_transaction from {t} where \"group\" = 'isolated'"), 1)


@check("/ · findings/competition", "% with another KDMP within 1 km", 22.2, tol=0.05, key="other_within_1km_pct", fmt="pct1")
def _():
    return round(
        100
        * one(f"select count(*) from {P} where m_to_nearest_other <= 1000")
        / one(f"select count(*) from {P} where m_to_nearest_other is not null"),
        1,
    )


@check("findings/competition", "% with another KDMP within 2 km", 58.9, tol=0.05, key="other_within_2km_pct", fmt="pct1")
def _():
    return round(
        100
        * one(f"select count(*) from {P} where m_to_nearest_other <= 2000")
        / one(f"select count(*) from {P} where m_to_nearest_other is not null"),
        1,
    )


@check("/ · findings/competition", "% with another KDMP within 5 km", 91.3, tol=0.05, key="other_within_5km_pct", fmt="pct1")
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


@check("/ · findings/money", "% of cooperatives at 100% construction", 24.3, tol=0.05, key="build_100_pct", fmt="pct1")
def _():
    t = csv("15-construction-output", "construction_vs_output.csv")
    r = con.execute(
        f"select sum(cooperatives * pct_build_100) / sum(cooperatives) from {t}"
    ).fetchone()[0]
    return round(r, 1)


@check("findings/money", "% of cooperatives with any construction record", 45.6, tol=0.05, key="build_any_stage_pct", fmt="pct1")
def _():
    t = csv("15-construction-output", "construction_vs_output.csv")
    r = con.execute(
        f"select sum(cooperatives * pct_with_stage) / sum(cooperatives) from {t}"
    ).fetchone()[0]
    return round(r, 1)


@check("findings/money", "% of villages with NPWP", 97.1, tol=0.05, key="npwp_pct", fmt="pct1")
def _():
    t = csv("13-compliance-npwp-nib", "compliance_by_level.csv")
    return round(one(f"select pct_npwp from {t} where level = 'village_id'"), 1)


@check("findings/money", "% of cooperatives with NIB", 72.9, tol=0.05, key="nib_pct", fmt="pct1")
def _():
    t = csv("13-compliance-npwp-nib", "compliance_by_level.csv")
    return round(one(f"select pct_nib from {t} where level = 'village_id'"), 1)


@check("/ · findings/money", "% with NIB and no transaction", 69.9, tol=0.05, key="nib_no_transaction_pct", fmt="pct1")
def _():
    # Do NOT round the CSV before comparing. It already carries 2 dp, and
    # rounding a rounded figure is exactly how "4,7%" got onto the competition
    # page: the true value here is 69.854, which is 69,9 at one decimal, but
    # round(69.85, 1) in Python is 69.8. Compare at the CSV's precision and let
    # the tolerance absorb the page's rendering.
    t = csv("13-compliance-npwp-nib", "nib_vs_transaction.csv")
    return one(f"select pct from {t} where has_nib = 'NIB' and has_tx = 'no transaction'")


@check("/ · findings/money", "villages reporting a transaction without NIB", 23, key="reporting_without_nib", fmt="int")
def _():
    t = csv("13-compliance-npwp-nib", "nib_vs_transaction.csv")
    return one(f"select villages from {t} where has_nib = 'no NIB' and has_tx = 'transaction'")


@check("findings/money", "% of villages with an account", 96.0, tol=0.5, key="account_pct", fmt="pct0")
def _():
    t = csv("02-zero-inflation", "zero_inflation_by_field.csv")
    return round(one(f"select pct_nonzero from {t} where field = 'accounts_count'"), 0)


# The village-level twins of npwp_pct / nib_pct above. Report 13 counts
# documents per *cooperative*; report 02 counts villages holding at least one.
# The funnel table on findings/money is a column of village shares with a header
# that says so, and it was printing the cooperative figures in two of its six
# rows, which is also why it disagreed with methods/02 by a tenth of a point.
# Both pairs stay in the registry: the funnel binds these, the "zombie"
# paragraph binds the per-cooperative ones, and each says which it means.
@check("findings/money · methods/02", "% of villages holding an NPWP", 97.2, tol=0.05, key="npwp_villages_pct", fmt="pct1")
def _():
    t = csv("02-zero-inflation", "zero_inflation_by_field.csv")
    return one(f"select pct_nonzero from {t} where field = 'npwp_count'")


@check("findings/money · methods/02", "% of villages holding an NIB", 73.1, tol=0.05, key="nib_villages_pct", fmt="pct1")
def _():
    t = csv("02-zero-inflation", "zero_inflation_by_field.csv")
    return one(f"select pct_nonzero from {t} where field = 'nib_count'")


@check("findings/money · methods/02", "% of villages reporting founding capital", 11.9, tol=0.05, key="pokok_villages_pct", fmt="pct1")
def _():
    t = csv("11-savings-behaviour", "savings_zero_inflation.csv")
    return one(f"select pct_nonzero from {t} where field = 'simpanan_pokok_amount'")


# NOT bound into the prose, deliberately. The source CSV carries 34.85 at two
# decimals, so the true value is somewhere in 34.845-34.855 and *neither* 34,8%
# nor 34,9% is justified at one decimal: the page's "34,8%" and a half-up
# rendering's "34,9%" are both guesses about a digit report 02 did not publish.
# The registry therefore carries the figure at the precision the source
# actually has, the pages keep their own wording, and this check goes on
# verifying the value as it always did. Binding it would mean either printing
# "34,85%" in a sentence written for a general reader, or asserting a decimal
# nobody computed. Recomputing it here instead would fork report 02's
# methodology into a second implementation, which is the drift this file exists
# to prevent.
@check("/ · findings/money", "share of national value from top 100 villages (%)", 34.8, tol=0.05, key="top100_value_share_pct", fmt="pct2")
def _():
    t = csv("02-zero-inflation", "transaction_concentration.csv")
    return one(f"select share_of_national_tx_value from {t} where top_n_villages = 100")


@check("/ · findings/money", "share of national value from top 1.000 villages (%)", 90.6, tol=0.05, key="top1000_value_share_pct", fmt="pct1")
def _():
    t = csv("02-zero-inflation", "transaction_concentration.csv")
    return one(f"select share_of_national_tx_value from {t} where top_n_villages = 1000")


@check("findings/money", "total savings (Rp miliar)", 40.3, tol=0.05, key="savings_total_miliar", fmt="dec1")
def _():
    t = csv("11-savings-behaviour", "savings_national.csv")
    return round(one(f"select value from {t} where metric = 'savings_total_amount'") / 1e9, 1)


@check("findings/money", "median wajib/pokok ratio", 0.28, tol=0.005, key="wajib_pokok_ratio", fmt="dec2")
def _():
    t = csv("11-savings-behaviour", "wajib_pokok_ratio.csv")
    return round(one(f"select value from {t} where stat = 'median wajib/pokok'"), 2)


# Both of the figures below are conditioned on a village reporting *both* kinds
# of savings, which is 8,6% of villages, not all of them. The page said "hanya
# 15,8% desa", which reads as 15,8% of the country and is off by a factor of
# eleven. Publishing the base alongside the share is the fix; these two are
# bound next to each other in the sentence so the base cannot go missing again.
@check("findings/money", "villages reporting both pokok and wajib", 7_164, key="wajib_pokok_both_villages", fmt="int")
def _():
    t = csv("11-savings-behaviour", "wajib_pokok_ratio.csv")
    return one(f"select value from {t} where stat = 'villages with both pokok and wajib'")


@check("findings/money", "share of those villages where wajib exceeds pokok (%)", 15.8, tol=0.05, key="wajib_gt_pokok_pct", fmt="pct1")
def _():
    t = csv("11-savings-behaviour", "wajib_pokok_ratio.csv")
    return one(f"select value from {t} where stat = 'share with wajib > pokok (pct)'")


@check("findings/money", "RAT recorded for N cooperatives", 50_200, key="rat_recorded_coops", fmt="int")
def _():
    t = csv("16-rat-compliance", "rat_by_province.csv")
    return int(one(f"select sum(rat_count) from {t}"))


@check("/ · findings/money", "% of cooperatives with RAT recorded", 60.2, tol=0.05, key="rat_pct", fmt="pct1")
def _():
    t = csv("16-rat-compliance", "rat_by_province.csv")
    return round(100 * one(f"select sum(rat_count) from {t}") / 83_379, 1)


# ---------------------------------------------------------------------------
# Chapter 1 addendum — buildings (methods 17), rewritten 2026-08-14
# ---------------------------------------------------------------------------


@check("methods/17", "% on a mapped building cell", 44.36, tol=0.005, key="on_building_cell_pct", fmt="pct2")
def _():
    return round(
        100
        * one(f"select count(*) from {P} where building_band = 'on a building cell (<70 m)'")
        / 83_379,
        2,
    )


@check("methods/17", "% with no mapped building within ~5 km", 1.19, tol=0.005, key="no_building_5km_pct", fmt="pct2")
def _():
    return round(
        100
        * one(f"select count(*) from {P} where building_band = '> ~5 km / none found'")
        / 83_379,
        2,
    )


@check("methods/17", "% with a mapped building within ~260 m", 75.2, tol=0.05, key="building_within_260m_pct", fmt="pct1")
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


@check("methods/17 · about", "no house 1 km + isolated + roadless", 128, key="triple_isolated_coops", fmt="int")
def _():
    t = csv("17-building-proximity", "building_overlap.csv")
    # "case" is a reserved word; it needs quoting even as a column name.
    return int(one(f'select n from {t} where "case" like \'%isolated + roadless%\''))


@check("findings/money", "% of cooperatives with RAT, Papua Pegunungan", 6.1, tol=0.05, key="rat_papua_pegunungan_pct", fmt="pct1")
def _():
    t = csv("16-rat-compliance", "rat_by_province.csv")
    return round(one(f"select rat_pct from {t} where province = 'PAPUA PEGUNUNGAN'"), 1)


@check("findings/money", "% of cooperatives with RAT, Papua Selatan", 16.0, tol=0.05, key="rat_papua_selatan_pct", fmt="pct1")
def _():
    # NOTE: the page said 16,2% until 2026-08-14. That was the 08-05 figure;
    # report 16's CSV had never been re-run against the 08-13 snapshot the rest
    # of the site uses.
    t = csv("16-rat-compliance", "rat_by_province.csv")
    return round(one(f"select rat_pct from {t} where province = 'PAPUA SELATAN'"), 1)


@check("findings/remoteness", "% of Papua KDMP in an empty 400 m cell", 70.7, tol=0.05, key="papua_empty_cell_pct", fmt="pct1")
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


@check("/ · findings", "Papua share of cooperatives (%)", 8.5, tol=0.05, key="papua_coops_share_pct", fmt="pct1")
def _():
    r = con.execute(
        f"select sum(cooperatives) filter (where province like 'PAPUA%'), "
        f"sum(cooperatives) from {PROV}"
    ).fetchone()
    return round(100 * r[0] / r[1], 1)


@check("/ · findings", "Papua share of transaction value (%)", 0.6, tol=0.05, key="papua_value_share_pct", fmt="pct1")
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


@check("findings", "Java share of cooperatives (%)", 30, tol=0.5, key="java_coops_share_pct", fmt="pct0")
def _():
    r = con.execute(
        f"select sum(cooperatives) filter (where province in ({JAVA})), "
        f"sum(cooperatives) from {PROV}"
    ).fetchone()
    return round(100 * r[0] / r[1], 0)


@check("findings", "Java share of transaction value (%)", 60, tol=0.5, key="java_value_share_pct", fmt="pct0")
def _():
    r = con.execute(
        f"select sum(transaction_value) filter (where province in ({JAVA})), "
        f"sum(transaction_value) from {PROV}"
    ).fetchone()
    return round(100 * r[0] / r[1], 0)


@check("/ · findings/money", "transaction value per cooperative (Rp juta)", 2.43, tol=0.005, key="value_per_coop_juta", fmt="dec2")
def _():
    r = con.execute(
        f"select sum(transaction_value), sum(cooperatives) from {PROV}"
    ).fetchone()
    return round(r[0] / r[1] / 1e6, 2)


@check("/", "cooperatives at 100% construction (count)", 20_221, key="build_100_coops", fmt="int")
def _():
    t = csv("15-construction-output", "construction_vs_output.csv")
    return int(round(one(f"select sum(cooperatives * pct_build_100 / 100.0) from {t}")))


@check("findings/money", "% of villages with no savings at all", 87.5, tol=0.05, key="no_savings_pct", fmt="pct1")
def _():
    t = csv("11-savings-behaviour", "savings_zero_inflation.csv")
    return round(
        100 - one(f"select pct_nonzero from {t} where field = 'savings_total_amount'"), 1
    )


@check("findings/money", "% of villages with any savings", 12.5, tol=0.05, key="any_savings_pct", fmt="pct1")
def _():
    t = csv("11-savings-behaviour", "savings_zero_inflation.csv")
    return one(f"select pct_nonzero from {t} where field = 'savings_total_amount'")


@check("findings/money", "% of villages paying monthly dues (wajib)", 9.2, tol=0.05, key="wajib_paying_pct", fmt="pct1")
def _():
    t = csv("11-savings-behaviour", "savings_zero_inflation.csv")
    return one(f"select pct_nonzero from {t} where field = 'simpanan_wajib_amount'")


# The funnel table reads as a ladder, where every rung is a subset of the one
# above. For the administrative rungs it nearly is: only 23 villages report a
# transaction without an NIB, 1 without an NPWP. For savings it is not. These
# two figures are the counter-evidence to our own burden-of-proof argument, so
# they are published rather than left in the report: a village can report sales
# while reporting no member capital at all, which means the channels are
# incomplete one at a time and an empty channel proves less than it looks like.
@check("findings/money", "villages reporting a transaction but no savings", 1_471, key="tx_without_savings", fmt="int")
def _():
    t = csv("11-savings-behaviour", "savings_vs_transactions.csv")
    return one(
        f"select villages from {t} "
        "where has_sav = 'no savings' and has_tx = 'transaction'"
    )


@check("findings/money", "% of villages with any financial footprint", 14.3, tol=0.05, key="any_footprint_pct", fmt="pct1")
def _():
    t = csv("11-savings-behaviour", "savings_national.csv")
    return one(f"select value from {t} where metric = 'pct_any_financial_footprint'")


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


@check("findings/money · methods/09", "press total, 31 Jul (Rp miliar)", 157.9, tol=0.05, key="press_value_jul31_miliar", fmt="dec2")
def _():
    return one(
        f"select value / 1e9 from {csv(*EXT)} "
        "where as_of = '2026-07-31' and metric = 'transaction_value_idr'"
    )


@check("findings/money · methods/09", "press total, 9 Aug (Rp miliar)", 179.72, tol=0.005, key="press_value_aug09_miliar", fmt="dec2")
def _():
    return one(
        f"select value / 1e9 from {csv(*EXT)} "
        "where as_of = '2026-08-09' and metric = 'transaction_value_idr'"
    )


@check("findings/money", "government count of operating cooperatives", 1_061, key="operating_coops", fmt="int")
def _():
    return one(f"select value from {csv(*EXT)} where metric = 'cooperatives_operating'")


@check("findings/money · methods/09", "government count of completed outlets", 12_232, key="outlets_complete_jun", fmt="int")
def _():
    # Transcribed in June and never used on a page until now. It is the only
    # outside check we have on the construction channel: the same body that
    # said 12.232 outlets were finished on 11 June is the source SIMKOPDES's
    # own 20.221-at-100% on 13 August has to be consistent with.
    return one(f"select value from {csv(*EXT)} where metric = 'outlets_construction_complete'")


@check("findings/money", "operating cooperatives as % of the registry", 1.3, tol=0.05, key="operating_coops_pct", fmt="pct1")
def _():
    n = one(f"select value from {csv(*EXT)} where metric = 'cooperatives_operating'")
    return round(100 * n / 83_379, 1)


# The 1.061 are not spread across the country: CNN quotes Bakom saying all of
# them sit in Jawa Timur (530) and Jawa Tengah (531). The national rate above is
# therefore a two-province numerator over a national denominator, which is only
# defensible because the same quote says no other province had one operating.
# The page used to pair it with "3,3% in the same two provinces", which is the
# national reporting rate, not the two-province one. These four figures exist so
# the comparison can be stated both ways round and neither denominator can drift
# away from the sentence that uses it.
JAWA2 = "province in ('JAWA TIMUR', 'JAWA TENGAH')"


@check("findings/money · methods/09", "cooperatives in Jawa Timur + Jawa Tengah", 17_018, key="jawa2_coops", fmt="int")
def _():
    return one(f"select sum(cooperatives) from {PROV} where {JAWA2}")


@check("findings/money · methods/09", "1.061 operating as % of those two provinces", 6.2, tol=0.05, key="operating_coops_jawa2_pct", fmt="pct1")
def _():
    n = one(f"select value from {csv(*EXT)} where metric = 'cooperatives_operating'")
    return round(100 * n / one(f"select sum(cooperatives) from {PROV} where {JAWA2}"), 1)


@check("findings/money · methods/09", "villages in Jawa Timur + Jawa Tengah", 17_010, key="jawa2_villages", fmt="int")
def _():
    # Villages, not cooperatives: the two differ by 8 here, and the page prints
    # a numerator and a denominator side by side in one sentence. Mixing the
    # two units is the same defect as the 1.061 denominator this block fixes.
    return one(f"select sum(villages) from {PROV} where {JAWA2}")


@check("findings/money · methods/09", "villages reporting in those two provinces", 1_337, key="jawa2_reporting", fmt="int")
def _():
    return one(f"select sum(villages_reporting) from {PROV} where {JAWA2}")


@check("findings/money · methods/09", "% of villages reporting in those two provinces", 7.9, tol=0.05, key="jawa2_reporting_pct", fmt="pct1")
def _():
    r = con.execute(
        f"select sum(villages_reporting), sum(villages) from {PROV} where {JAWA2}"
    ).fetchone()
    return round(100 * r[0] / r[1], 1)


# ---------------------------------------------------------------------------
# Product mix  (methods/12)
# ---------------------------------------------------------------------------

CAT = "12-product-mix", "product_categories.csv"


@check("methods/12", "rice share of reported sales value (%)", 51.2, tol=0.05, key="rice_value_share_pct", fmt="pct1")
def _():
    return one(f"select share_of_value from {csv(*CAT)} where category = 'rice'")


@check("methods/12", "cooking oil share of reported sales value (%)", 25.6, tol=0.05, key="cooking_oil_value_share_pct", fmt="pct1")
def _():
    return one(f"select share_of_value from {csv(*CAT)} where category = 'cooking_oil'")


@check("methods/12", "fertiliser share of reported sales value (%)", 14.3, tol=0.05, key="fertiliser_value_share_pct", fmt="pct1")
def _():
    return one(f"select share_of_value from {csv(*CAT)} where category = 'fertilizer'")


@check("methods/12", "provinces where fertiliser is a top product", 24, key="fertiliser_top_provinces", fmt="int")
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


@check("methods/01", "villages reporting zero transactions on 5 Aug", 80_553, key="zero_villages_aug05", fmt="int")
def _():
    return one(
        f"select was_zero from {csv(*DIFF)} where measure = 'transaction_value'"
    )


@check("methods/01", "villages that started reporting in those four days", 1, key="started_reporting_4d", fmt="int")
def _():
    return one(
        f"select zero_to_positive from {csv(*DIFF)} where measure = 'transaction_value'"
    )


@check("methods/01", "years to clear the backlog at that rate", 883, tol=1, key="backlog_years", fmt="int")
def _():
    z = one(f"select was_zero from {csv(*DIFF)} where measure = 'transaction_value'")
    moved = one(
        f"select zero_to_positive from {csv(*DIFF)} where measure = 'transaction_value'"
    )
    return round(z / moved * 4 / 365.0, 0)


@check("findings/money", "villages reporting, 5 Aug", 2_516, key="villages_reporting_aug05", fmt="int")
def _():
    return one(f"select villages_reporting from {csv(*SNAP)} where as_of = '2026-08-05'")


@check("findings/money", "villages reporting, 9 Aug", 2_517, key="villages_reporting_aug09", fmt="int")
def _():
    return one(f"select villages_reporting from {csv(*SNAP)} where as_of = '2026-08-09'")


@check("findings/money", "new reporting villages, 9 Aug to 13 Aug", 209, key="new_reporting_aug09_13", fmt="int")
def _():
    t = csv(*SNAP)
    return one(
        f"select (select villages_reporting from {t} where as_of = '2026-08-13') "
        f"- (select villages_reporting from {t} where as_of = '2026-08-09')"
    )


@check("findings/money", "press value growth, 31 Jul to 9 Aug (%)", 13.8, tol=0.05, key="press_growth_pct", fmt="pct1")
def _():
    t = csv("09-external-corroboration", "published_series.csv")
    a = one(f"select miliar from {t} where as_of = '2026-07-31'")
    b = one(f"select miliar from {t} where as_of = '2026-08-09'")
    return round(100 * (b - a) / a, 1)


@check("findings/money", "our value growth, 5 Aug to 9 Aug (%)", 0.13, tol=0.005, key="our_growth_aug05_09_pct", fmt="pct2")
def _():
    # The page used to pair the press series' +13,8% (31 Jul to 9 Aug) with our
    # own village count barely moving (2.516 to 2.517, which is 5 to 9 Aug), and
    # read the two together as "the value grew inside a fixed set of villages".
    # They are different windows. Over the window we actually observed, the
    # value did not grow either: this is that number, and it exists so the
    # sentence cannot be written the old way again.
    t = csv(*SNAP)
    a = one(f"select transaction_value_idr from {t} where as_of = '2026-08-05'")
    b = one(f"select transaction_value_idr from {t} where as_of = '2026-08-09'")
    return round(100 * (b - a) / a, 2)


@check("findings/money", "our value growth, 9 Aug to 13 Aug (%)", 12.7, tol=0.05, key="our_growth_pct", fmt="pct1")
def _():
    t = csv(*SNAP)
    a = one(f"select transaction_value_idr from {t} where as_of = '2026-08-09'")
    b = one(f"select transaction_value_idr from {t} where as_of = '2026-08-13'")
    return round(100 * (b - a) / a, 1)


@check("methods/09", "gap between press and our own pull, 9 Aug (%)", 0.042, tol=0.0005, key="press_reconcile_gap_pct", fmt="pct3")
def _():
    t = csv("09-external-corroboration", "reconciliation.csv")
    return one(f"select pct_difference from {t} where as_of = '2026-08-09'")


@check("methods/01", "duplicate village rows in the 5 Aug export", 1_555, key="duplicate_village_rows", fmt="int")
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


# ---------------------------------------------------------------------------
# The registry, and the pages that read from it
# ---------------------------------------------------------------------------

FIGURES = ROOT / "data" / "web" / "figures.json"

# Where a bound figure may appear. The method prose is markdown rendered at
# runtime by app/site.js, and marked passes inline HTML through, so the same
# <span data-fig> works in both.
BINDABLE = [("*.html", ("app", "_proto")), ("methods/_content/*.md", ())]

BINDING = re.compile(
    r"""<(\w+)[^>]*\bdata-fig\s*=\s*["']([^"']+)["'][^>]*>(.*?)</\1>""",
    re.S,
)


def registry(results):
    """The keyed subset of the run, as the pages will read it."""
    out = {}
    for c, value in results:
        if not c.key:
            continue
        out[c.key] = {
            "value": value,
            "text": render(value, c.fmt),
            "label": c.label,
            "page": c.page,
        }
    return dict(sorted(out.items()))


def bindings():
    """(file, line, key, literal) for every data-fig element on the site."""
    for pattern, skip in BINDABLE:
        for path in sorted(ROOT.rglob(pattern)):
            parts = path.relative_to(ROOT).parts
            if {".git", ".venv", "node_modules", "__pycache__"} & set(parts):
                continue
            if skip and parts[0] in skip:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for m in BINDING.finditer(text):
                literal = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(3))).strip()
                line = text[: m.start()].count("\n") + 1
                yield path.relative_to(ROOT).as_posix(), line, m.group(2), literal


def check_bindings(reg):
    """Compare each bound element's committed text to the registry.

    The literal in the file is the no-JavaScript fallback and the thing a
    reader sees in a diff, so it has to stay true on its own. This is what
    stops the registry from silently papering over a stale page.
    """
    problems = []
    for path, line, key, literal in bindings():
        if key not in reg:
            problems.append((path, line, key, literal, "no such figure in the registry"))
        elif literal != reg[key]["text"]:
            problems.append((path, line, key, literal, f"registry says {reg[key]['text']}"))
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument(
        "--emit",
        action="store_true",
        help=f"write the keyed figures to {FIGURES.relative_to(ROOT).as_posix()}",
    )
    args = ap.parse_args()

    width = max(len(c.label) for c in CHECKS) + 2
    fails, skips, results = [], [], []
    print(f"{'CHECK'.ljust(width)} {'PUBLISHED':>12} {'COMPUTED':>12}   STATUS")
    print("-" * (width + 42))

    for c in CHECKS:
        try:
            actual = c.fn()
        except FileNotFoundError as err:
            skips.append((c.label, f"missing {Path(str(err)).name}"))
            print(f"{c.label.ljust(width)} {c.published:>12} {'-':>12}   SKIP (no source)")
            continue
        except Exception as err:  # noqa: BLE001
            skips.append((c.label, str(err)[:70]))
            print(f"{c.label.ljust(width)} {c.published:>12} {'-':>12}   SKIP ({str(err)[:40]})")
            continue

        if isinstance(actual, tuple):  # unresolved probe, see NOTE
            skips.append((c.label, f"probe: {actual[1]}"))
            print(f"{c.label.ljust(width)} {c.published:>12} {'?':>12}   SKIP (probe)")
            continue

        # The epsilon matters: a page printing 69,9 against a CSV's 69.85 is a
        # difference of exactly the tolerance, and in binary that lands a hair
        # above it. Without this, every legitimate one-decimal rendering of a
        # two-decimal figure fails.
        ok = abs(float(actual) - float(c.published)) <= c.tol + 1e-9
        status = "OK" if ok else "MISMATCH"
        if not ok:
            fails.append((c.page, c.label, c.published, actual))
        else:
            results.append((c, actual))
        print(f"{c.label.ljust(width)} {c.published:>12} {actual:>12}   {status}")

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

    # Only figures that passed reach the registry: a mismatched check means we
    # do not yet know which of the two numbers is right, and shipping the
    # computed one would quietly rewrite a page the author has not re-read.
    reg = registry(results)
    keyed = sum(1 for c in CHECKS if c.key)
    print(f"\n{len(reg)} of {keyed} keyed figures resolved for the registry")

    if args.emit:
        FIGURES.write_text(
            json.dumps(reg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"wrote {FIGURES.relative_to(ROOT).as_posix()}")

    bad = check_bindings(reg)
    bound = sum(1 for _ in bindings())
    print(f"{bound} bound elements on the pages, {len(bad)} out of step")
    if bad:
        print("\nSTALE BINDINGS — the committed page text is not what the data says:")
        for path, line, key, literal, why in bad:
            print(f"  {path}:{line}\n    data-fig={key}: page says {literal!r}, {why}")

    return 1 if fails or bad else 0


if __name__ == "__main__":
    sys.exit(main())
