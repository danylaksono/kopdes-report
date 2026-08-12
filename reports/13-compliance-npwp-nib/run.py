#!/usr/bin/env python3
"""
13-compliance-npwp-nib - the paperwork test: are KDMP actually registered as
businesses?

D3 of analytics-plan.md. NPWP (tax id) and NIB (business identification
number) are administrative, present at every admin level, and need no join.
The stakes differ: a missing NPWP is a paperwork gap, but NIB is the license
to operate as a business in Indonesia - a cooperative without one cannot
legally transact. The zombie test cross-tabs NIB-presence against
transaction-reporting: how many villages hold the license but show no
operations, and how many villages show operations without the license?

NPWP/NIB counts are aggregated over villages (deduplicated, per 01) and the
totals are checked against the national summary before anything is quoted.

Reads only committed CSVs; no network; deterministic.

Usage: python reports/13-compliance-npwp-nib/run.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.common import RAW, out_dir, write_csv  # noqa: E402

OUT = out_dir(__file__)


def main():
    v = pd.read_csv(RAW / "kopdes_stats_village.csv")
    before = len(v)
    v = v.drop_duplicates("village_id")
    if before != len(v):
        print(f"dropped {before - len(v):,} duplicate village_ids\n")

    # --- 0. reconcile against the national summary ----------------------------
    nat = pd.read_csv(RAW / "kopdes_national_summary.csv").set_index("metric")["value"]
    for field, metric in (("npwp_count", "with_npwp"), ("nib_count", "with_nib")):
        got = int(v[field].sum())
        expect = float(pd.to_numeric(nat[metric], errors="coerce"))
        print(f"{field}: village sum {got:,} vs national summary {expect:,.0f} "
              f"(diff {got - expect:,.0f})")
    print()

    # --- 1. compliance at every admin level -----------------------------------
    def level_stats(df, id_col):
        g = (
            df.groupby(id_col, as_index=False)
            .agg(label=("province", "first"), cooperatives=("cooperatives", "sum"),
                 npwp=("npwp_count", "sum"), nib=("nib_count", "sum"))
        )
        return pd.DataFrame([{
            "level": id_col,
            "units": len(g),
            "cooperatives": int(g.cooperatives.sum()),
            "with_npwp": int(g.npwp.sum()),
            "pct_npwp": round(100 * g.npwp.sum() / g.cooperatives.sum(), 2),
            "with_nib": int(g.nib.sum()),
            "pct_nib": round(100 * g.nib.sum() / g.cooperatives.sum(), 2),
        }])

    rows = [
        level_stats(v, "village_id"),
        level_stats(v, "subdistrict_id"),
        level_stats(v, "district_id"),
        level_stats(v, "province_id"),
    ]
    comp = pd.concat(rows, ignore_index=True)
    print("Compliance at each admin level:\n")
    print(comp.to_string(index=False))
    write_csv(comp, OUT / "compliance_by_level.csv")

    # --- 2. the zombie test: NIB (the license) vs reporting --------------------
    v["has_npwp"] = v.npwp_count > 0
    v["has_nib"] = v.nib_count > 0
    v["has_tx"] = v.transaction_value > 0

    ct = (
        v.groupby(["has_nib", "has_tx"], observed=True)
        .size()
        .reset_index(name="villages")
        .assign(pct=lambda d: round(100 * d.villages / len(v), 2))
        .replace({"has_nib": {False: "no NIB", True: "NIB"},
                  "has_tx": {False: "no transaction", True: "transaction"}})
        .sort_values(["has_nib", "has_tx"], ascending=[False, False])
    )
    write_csv(ct, OUT / "nib_vs_transaction.csv")
    print("\nNIB (business license) vs transaction-reporting, per village:\n")
    print(ct.to_string(index=False))

    # descriptive corners of the cross-tab
    no_nib_no_tx = int(((~v.has_nib) & (~v.has_tx)).sum())
    no_nib_tx = int(((~v.has_nib) & v.has_tx).sum())
    nib_no_tx = int((v.has_nib & (~v.has_tx)).sum())
    print(f"\nno NIB and no transaction: {no_nib_no_tx:,} ({100*no_nib_no_tx/len(v):.1f}%)")
    print(f"no NIB but reporting a transaction: {no_nib_tx:,} ({100*no_nib_tx/len(v):.2f}%)")
    print(f"NIB but no transaction: {nib_no_tx:,} ({100*nib_no_tx/len(v):.1f}%)")

    # --- 3. villages where nothing at all is registered ------------------------
    zero = pd.DataFrame([
        {"field": "npwp_count", "villages_zero": int((v.npwp_count == 0).sum()),
         "pct": round(100 * (v.npwp_count == 0).mean(), 2)},
        {"field": "nib_count", "villages_zero": int((v.nib_count == 0).sum()),
         "pct": round(100 * (v.nib_count == 0).mean(), 2)},
        {"field": "npwp_and_nib", "villages_zero": int(((v.npwp_count == 0) & (v.nib_count == 0)).sum()),
         "pct": round(100 * ((v.npwp_count == 0) & (v.nib_count == 0)).mean(), 2)},
    ])
    write_csv(zero, OUT / "compliance_zero_villages.csv")
    print("\nVillages where no cooperative holds the document:\n")
    print(zero.to_string(index=False))

    # --- 4. province spread -----------------------------------------------------
    prov = (
        v.groupby("province", as_index=False)
        .agg(cooperatives=("cooperatives", "sum"),
             npwp=("npwp_count", "sum"),
             nib=("nib_count", "sum"))
        .assign(pct_npwp=lambda d: (100 * d.npwp / d.cooperatives).round(2),
                pct_nib=lambda d: (100 * d.nib / d.cooperatives).round(2))
        .sort_values("pct_nib", ascending=False)
    )
    write_csv(prov, OUT / "compliance_by_province.csv")
    print("\nNIB uptake by province (share of cooperatives holding NIB):\n")
    print(prov[["province", "cooperatives", "pct_npwp", "pct_nib"]].to_string(index=False))


if __name__ == "__main__":
    main()
