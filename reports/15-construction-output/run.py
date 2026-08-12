#!/usr/bin/env python3
"""
15-construction-output - does construction progress track economic output?

C1 of analytics-plan.md, deliberately downgraded: n = 38 provinces, no
confounder control, so this is a descriptive scatter, never evidence of
causation. The plan-review's verdict is explicit - "a correlation on 38 points
with no confounder control is a scatter plot, not evidence."

Two things are worth printing anyway, because both are structural facts the
report should state once:
  - RAT (annual member meeting) compliance is zero in every province.
  - Fewer than a quarter of cooperatives nationally are at 100% construction,
    and more than half have no construction stage recorded at all.

Reads only committed CSVs; no network; deterministic.

Usage: python reports/15-construction-output/run.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.common import RAW, out_dir, write_csv  # noqa: E402

OUT = out_dir(__file__)

BUILD_STAGES = ["build_upto_20", "build_21_50", "build_51_75", "build_76_99", "build_100"]


def main():
    c = pd.read_csv(RAW / "kopdes_province_rat_and_construction.csv")
    s = pd.read_csv(RAW / "kopdes_stats_province.csv")[["province", "cooperatives", "transaction_value"]]

    print(f"RAT compliance: {c.total_rat.sum():,} total, {c.total_done_rat.sum():,} done "
          f"across all provinces - the RAT channel is empty\n")

    df = c.merge(s, on="province", how="left")
    df["with_stage"] = df[BUILD_STAGES].sum(axis=1)
    df["pct_with_stage"] = (100 * df.with_stage / df.cooperatives).round(2)
    df["pct_build_100"] = (100 * df.build_100 / df.cooperatives).round(2)
    df["pct_build_ge76"] = (100 * (df.build_76_99 + df.build_100) / df.cooperatives).round(2)
    df["tx_per_coop"] = (df.transaction_value / df.cooperatives).round(0)

    out = df[["province", "cooperatives", "with_stage", "pct_with_stage",
              "pct_build_ge76", "pct_build_100", "transaction_value", "tx_per_coop"]]
    write_csv(out, OUT / "construction_vs_output.csv", "n = 38 provinces, descriptive only")

    print("Construction progress vs economic output, per province:\n")
    print(out.sort_values("pct_build_100", ascending=False).to_string(index=False))

    rho = df.pct_build_100.corr(df.tx_per_coop, method="spearman")
    rho2 = df.pct_with_stage.corr(df.tx_per_coop, method="spearman")
    print(f"\nspearman(pct_build_100, tx_per_coop) = {rho:.3f}   (n = {len(df)})")
    print(f"spearman(pct_with_stage, tx_per_coop) = {rho2:.3f}   (n = {len(df)})")

    nat_coops = int(s.cooperatives.sum())
    nat_100 = int(c.build_100.sum())
    nat_stage = int(c[BUILD_STAGES].sum().sum())
    print(f"\nnationally: {nat_100:,}/{nat_coops:,} ({100*nat_100/nat_coops:.1f}%) at 100% construction; "
          f"{nat_stage:,} ({100*nat_stage/nat_coops:.1f}%) have any construction stage recorded")


if __name__ == "__main__":
    main()
