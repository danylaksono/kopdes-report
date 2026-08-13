#!/usr/bin/env python3
"""
16-rat-compliance - are the cooperatives holding their annual member meetings?

C3 of analytics-plan.md. The original plan (and report 15) claimed RAT was
zero in all 38 provinces, based on the `total_rat` field in
`kopdes_province_rat_and_construction.csv`. That field comes from the per-
province `/statistics/national-readiness/province/{id}` `rat_summary` object,
which has been observed empty (period 2024, all fields 0) on every pull.

The real RAT channel is `rat_count` in the stats files
(`kopdes_stats_{village,district,province}.csv`), which the dashboard renders
per province as "Koperasi Telah Melaksanakan RAT". It sums to ~50,000 (about
60% of cooperatives) and is stable across the 08-05 baseline, the 08-09
snapshot and the live 08-13 pull (50,174 / 50,188 / 50,200). The "RAT = 0
everywhere" finding was a field-selection error, not a real result.

Reads only committed CSVs; no network; deterministic.

Usage: python reports/16-rat-compliance/run.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.common import RAW, out_dir, write_csv  # noqa: E402

OUT = out_dir(__file__)


def main():
    p = pd.read_csv(RAW / "kopdes_stats_province.csv")

    # --- 0. the field trap, stated once -------------------------------------
    print("RAT sources: `total_rat` (province readiness endpoint) has been 0 in "
          "every pull; `rat_count` (stats endpoint, dashboard's own display) is "
          "the real channel. This report uses `rat_count`.")

    # --- 1. national ---------------------------------------------------------
    nat_rat = int(p.rat_count.sum())
    nat_coop = int(p.cooperatives.sum())
    print(f"\nnational: {nat_rat:,} of {nat_coop:,} cooperatives have conducted "
          f"an RAT = {100 * nat_rat / nat_coop:.1f}%")

    # --- 2. per province -----------------------------------------------------
    prov = p[["province_id", "province", "cooperatives", "rat_count",
              "transaction_value"]].copy()
    prov["rat_pct"] = (100 * prov.rat_count / prov.cooperatives).round(1)
    prov["tx_per_coop"] = (prov.transaction_value / prov.cooperatives).round(0)
    prov = prov.sort_values("rat_pct", ascending=False)
    write_csv(prov, OUT / "rat_by_province.csv", "n = 38 provinces, `rat_count` source")

    # --- 3. availability -----------------------------------------------------
    # rat_count is populated ONLY at province level in the stats endpoint.
    # The district/subdistrict/village walks all return 0 (verified across
    # 08-05, 08-09 and the live 08-13 pull), so no finer-grained RAT analysis
    # is possible from this API. State it once, don't chase it.
    print("rat_count availability: province only. District/subdistrict/village "
          "stats carry 0 on every pull - the API exposes RAT at province level "
          "only (via nested_data.grouped).")

    # --- 4. is RAT compliance correlated with activity? ----------------------
    rho_tx = prov.rat_pct.corr(prov.tx_per_coop, method="spearman")
    print(f"\nspearman(rat_pct, tx_per_coop) = {rho_tx:.3f}  (n = 38)")
    print("\ntop / bottom provinces by RAT compliance:\n")
    print(prov.head(6).to_string(index=False))
    print("\n...\n")
    print(prov.tail(6).to_string(index=False))


if __name__ == "__main__":
    main()
