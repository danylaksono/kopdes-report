#!/usr/bin/env python3
"""
14-island-comparison - how does KDMP performance differ across Indonesia's
major island groups?

F3 of analytics-plan.md. Maps the 38 provinces to seven island groups and
compares both halves of the evidence: the complete economic picture (grouped
straight off the deduplicated village file) and the spatial/placement picture
(per-cooperative measures assembled in the committed analysis mart).

The island split is the one aggregation the program itself would defend -
logistics cost, population density and existing retail differ by orders of
magnitude between Java and Papua, so a fair read of the program has to say
which island each finding lives on.

Reads committed CSVs + data/web/kopdes_points.parquet; no network; deterministic.

Usage: python reports/14-island-comparison/run.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.common import RAW, ROOT, out_dir, write_csv  # noqa: E402

OUT = out_dir(__file__)

ISLANDS = {
    "SUMATRA": ["ACEH", "SUMATERA UTARA", "SUMATERA BARAT", "RIAU", "JAMBI",
                "SUMATERA SELATAN", "BENGKULU", "LAMPUNG",
                "KEPULAUAN BANGKA BELITUNG", "KEPULAUAN RIAU"],
    "JAVA": ["DKI JAKARTA", "JAWA BARAT", "JAWA TENGAH",
             "DAERAH ISTIMEWA YOGYAKARTA", "JAWA TIMUR", "BANTEN"],
    "KALIMANTAN": ["KALIMANTAN BARAT", "KALIMANTAN TENGAH", "KALIMANTAN SELATAN",
                   "KALIMANTAN TIMUR", "KALIMANTAN UTARA"],
    "SULAWESI": ["SULAWESI UTARA", "SULAWESI TENGAH", "SULAWESI SELATAN",
                 "SULAWESI TENGGARA", "GORONTALO", "SULAWESI BARAT"],
    "NUSA TENGGARA": ["BALI", "NUSA TENGGARA BARAT", "NUSA TENGGARA TIMUR"],
    "MALUKU": ["MALUKU", "MALUKU UTARA"],
    "PAPUA": ["PAPUA", "PAPUA BARAT", "PAPUA TENGAH", "PAPUA BARAT DAYA",
              "PAPUA SELATAN", "PAPUA PEGUNUNGAN"],
}
PROVINCE_TO_ISLAND = {p: i for i, provs in ISLANDS.items() for p in provs}


def main():
    v = pd.read_csv(RAW / "kopdes_stats_village.csv").drop_duplicates("village_id")
    v["island"] = v["province"].map(PROVINCE_TO_ISLAND)
    unk = v["island"].isna().sum()
    if unk:
        print(f"WARNING: {unk:,} villages in unmatched provinces - {v.loc[v.island.isna(), 'province'].unique()}")
    print()

    # --- economics: complete, from the village file ----------------------------
    econ = (
        v.groupby("island", as_index=False)
        .agg(villages=("village_id", "size"),
             cooperatives=("cooperatives", "sum"),
             pct_reporting_tx=("transaction_value", lambda s: round(100 * float((s > 0).mean()), 2)),
             pct_any_savings=("savings_total_amount", lambda s: round(100 * float((s > 0).mean()), 2)),
             total_transaction_value=("transaction_value", "sum"),
             total_savings=("savings_total_amount", "sum"))
        .assign(tx_per_coop=lambda d: (d.total_transaction_value / d.cooperatives).round(0))
        .sort_values("cooperatives", ascending=False)
    )
    print("Island economics (complete, village file):\n")
    print(econ.to_string(index=False))
    write_csv(econ, OUT / "islands_economy.csv")

    # --- spatial: per-cooperative, from the committed mart ----------------------
    pt = pd.read_parquet(ROOT / "data" / "web" / "kopdes_points.parquet")
    pt["island"] = pt["province"].map(PROVINCE_TO_ISLAND)
    # drop the 19 impossible coordinates from medians (mart's coordinate_suspect)
    ok = pt[~pt.coordinate_suspect.fillna(False)]

    spat = (
        ok.groupby("island", as_index=False)
        .agg(cooperatives=("cooperative_id", "size"),
             pct_zero_pop_cell=("own_cell_pop", lambda s: round(100 * float((s == 0).mean()), 2)),
             median_pop_1_4km=("pop_within_1_4km", "median"),
             median_km_to_road=("km_non_track", "median"),
             median_km_to_minimarket=("m_to_minimarket_exact", lambda s: round(s.median() / 1000, 2)),
             median_m_to_nearest_coop=("m_to_nearest_other", "median"),
             pct_sibling_within_1km=("m_to_nearest_other", lambda s: round(100 * float((s <= 1000).mean()), 2)),
             pct_land_verified=("land_verified", lambda s: round(100 * float((s == True).mean()), 2)))
        .sort_values("cooperatives", ascending=False)
    )
    print("\nIsland spatial picture (per-cooperative mart, excluding 19 bad coords):\n")
    print(spat.to_string(index=False))
    write_csv(spat, OUT / "islands_spatial.csv")

    # sanity: every cooperative maps to exactly one island
    total = ok.groupby("island").size().sum()
    print(f"\n{total:,} of {len(pt):,} cooperatives placed on an island group")


if __name__ == "__main__":
    main()
