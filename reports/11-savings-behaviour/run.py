#!/usr/bin/env python3
"""
11-savings-behaviour - are members actually saving, or are the accounts dormant?

F2 of analytics-plan.md. Transactions are 97% zero (02), which makes them a
poor lens on whether KDMP are alive. Savings are the second activity channel
in the data, split into simpanan pokok (one-time capital collected at founding)
and simpanan wajib (ongoing compulsory dues). The pokok/wajib split is the
dormancy signal the plan asks for: pokok money is collected once when a
cooperative is registered, wajib money keeps coming only while the cooperative
is actually operating.

The core read is structural, not per-village: admin fields are populated for
~96% of villages, one-time capital for ~12%, ongoing operations (transactions
or wajib) for under 10%. A registration machine that worked and an operating
machine that did not.

Reads only committed CSVs; no network; deterministic.

Usage: python reports/11-savings-behaviour/run.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.common import IDR_PER_USD, RAW, out_dir, write_csv  # noqa: E402

OUT = out_dir(__file__)

SAVINGS_FIELDS = [
    ("simpanan_pokok_amount", "pokok - one-time capital, value"),
    ("simpanan_pokok_members", "pokok - one-time capital, members"),
    ("simpanan_pokok_tx", "pokok - one-time capital, transactions"),
    ("simpanan_wajib_amount", "wajib - ongoing dues, value"),
    ("simpanan_wajib_members", "wajib - ongoing dues, members"),
    ("simpanan_wajib_tx", "wajib - ongoing dues, transactions"),
    ("savings_total_amount", "all savings (pokok + wajib)"),
]

CONCENTRATION_NS = (10, 50, 100, 500, 1000)


def main():
    v = pd.read_csv(RAW / "kopdes_stats_village.csv")
    before = len(v)
    v = v.drop_duplicates("village_id")
    if before != len(v):
        print(f"dropped {before - len(v):,} duplicate village_ids "
              f"({before:,} rows -> {len(v):,} villages)\n")

    # --- 0. integrity check: savings_total must be pokok + wajib -------------
    lhs = v.savings_total_amount
    rhs = v.simpanan_pokok_amount + v.simpanan_wajib_amount
    ok = (lhs == rhs).all()
    print(f"savings_total == pokok + wajib for all {len(v):,} villages: {ok}")
    if not ok:
        bad = int((lhs != rhs).sum())
        print(f"  WARNING: {bad:,} rows disagree - checking a sample before trusting any total")
    print()

    # --- 1. zero inflation of every savings field (extends 02) --------------
    rows = []
    for c, label in SAVINGS_FIELDS:
        nz = int((v[c] > 0).sum())
        rows.append({
            "field": c,
            "label": label,
            "villages": len(v),
            "nonzero": nz,
            "pct_nonzero": round(100 * nz / len(v), 2),
            "max": round(float(v[c].max()), 0),
        })
    zi = pd.DataFrame(rows)
    print("Village-level savings fields, share non-zero (n=%d villages):\n" % len(v))
    print(zi[["field", "pct_nonzero", "max"]].to_string(index=False))
    write_csv(zi, OUT / "savings_zero_inflation.csv")

    # --- 2. savings vs transactions: do they tell the same story? ------------
    v["has_tx"] = v.transaction_value > 0
    v["has_sav"] = v.savings_total_amount > 0
    ct = (
        v.groupby(["has_sav", "has_tx"], observed=True)
        .size()
        .reset_index(name="villages")
        .assign(pct=lambda d: round(100 * d.villages / len(v), 2))
        .replace({"has_sav": {False: "no savings", True: "savings"},
                  "has_tx": {False: "no transaction", True: "transaction"}})
        .sort_values(["has_sav", "has_tx"], ascending=[False, False])
    )
    write_csv(ct, OUT / "savings_vs_transactions.csv")
    print("\nCross-tab: savings-reported vs transaction-reported:\n")
    print(ct.to_string(index=False))

    union = int((v.has_sav | v.has_tx).sum())
    print(f"\nany reported financial footprint (savings or transaction): "
          f"{union:,} ({100*union/len(v):.1f}%)  vs  transaction-only 3.0%")

    # --- 3. dormancy: pokok vs wajib -----------------------------------------
    p = (v.simpanan_pokok_amount > 0).to_numpy()
    w = (v.simpanan_wajib_amount > 0).to_numpy()
    bands = pd.DataFrame([
        {"band": "no savings at all", "n": int((~p & ~w).sum())},
        {"band": "pokok only (one-time capital, no ongoing dues)", "n": int((p & ~w).sum())},
        {"band": "wajib only (ongoing dues, no recorded capital)", "n": int((~p & w).sum())},
        {"band": "both pokok and wajib", "n": int((p & w).sum())},
    ])
    bands["pct"] = (100 * bands.n / len(v)).round(2)
    write_csv(bands, OUT / "dormancy_bands.csv")
    print("\nDormancy structure:\n")
    print(bands.to_string(index=False))

    both = v[p & w].copy()
    both["wajib_over_pokok"] = both.simpanan_wajib_amount / both.simpanan_pokok_amount
    ratio = pd.DataFrame([
        {"stat": "villages with both pokok and wajib", "value": len(both)},
        {"stat": "median wajib/pokok", "value": round(both.wajib_over_pokok.median(), 3)},
        {"stat": "p25 wajib/pokok", "value": round(both.wajib_over_pokok.quantile(0.25), 3)},
        {"stat": "p75 wajib/pokok", "value": round(both.wajib_over_pokok.quantile(0.75), 3)},
        {"stat": "share with wajib > pokok (pct)", "value": round(100 * (both.wajib_over_pokok > 1).mean(), 1)},
    ])
    write_csv(ratio, OUT / "wajib_pokok_ratio.csv")
    print("\nPokok-vs-wajib ratio among villages reporting both:\n")
    print(ratio.to_string(index=False))

    # --- 4. per-member magnitudes (plausibility) -----------------------------
    def per_member(amount_col, members_col):
        sub = v[(v[amount_col] > 0) & (v[members_col] > 0)].copy()
        r = sub[amount_col] / sub[members_col]
        return len(sub), r.quantile(0.25), r.median(), r.mean(), r.quantile(0.75)

    rows = []
    for amt, mem, label in (("simpanan_pokok_amount", "simpanan_pokok_members", "pokok"),
                            ("simpanan_wajib_amount", "simpanan_wajib_members", "wajib")):
        n, q25, med, mean, q75 = per_member(amt, mem)
        rows.append({
            "type": label,
            "villages_reporting": n,
            "per_member_p25": round(float(q25), 0),
            "per_member_median": round(float(med), 0),
            "per_member_mean": round(float(mean), 0),
            "per_member_p75": round(float(q75), 0),
        })
    pm = pd.DataFrame(rows)
    write_csv(pm, OUT / "savings_per_member.csv")
    print("\nImplied per-member amounts where reported:\n")
    print(pm.to_string(index=False))

    # --- 5. concentration of savings value -----------------------------------
    s = v.savings_total_amount.sort_values(ascending=False)
    total = s.sum()
    conc = pd.DataFrame(
        [{"top_n_villages": n, "share_of_savings_value": round(100 * float(s.head(n).sum() / total), 2)}
         for n in CONCENTRATION_NS]
    )
    write_csv(conc, OUT / "savings_concentration.csv")
    print("\nConcentration of savings value:\n")
    print(conc.to_string(index=False))

    # --- 6. national totals ---------------------------------------------------
    tx_total = v.transaction_value.sum()
    nat = pd.DataFrame([
        {"metric": "villages", "value": len(v)},
        {"metric": "savings_total_amount", "value": round(float(total), 0)},
        {"metric": "transaction_total_amount", "value": round(float(tx_total), 0)},
        {"metric": "savings_per_village", "value": round(float(total / len(v)), 0)},
        {"metric": "pct_any_savings", "value": round(100 * float((v.has_sav).mean()), 2)},
        {"metric": "pct_any_transaction", "value": round(100 * float((v.has_tx).mean()), 2)},
        {"metric": "pct_any_financial_footprint", "value": round(100 * float((v.has_sav | v.has_tx).mean()), 2)},
        {"metric": "ratio_savings_to_transactions", "value": round(float(total / tx_total), 3)},
    ])
    write_csv(nat, OUT / "savings_national.csv")

    # --- 7. province spread, cross-referenced to the health index -------------
    prov = (
        v.groupby("province", as_index=False)
        .agg(villages=("village_id", "size"),
             pct_any_savings=("savings_total_amount", lambda s: round(100 * float((s > 0).mean()), 2)),
             pct_pokok=("simpanan_pokok_amount", lambda s: round(100 * float((s > 0).mean()), 2)),
             pct_wajib=("simpanan_wajib_amount", lambda s: round(100 * float((s > 0).mean()), 2)),
             total_savings=("savings_total_amount", "sum"),
             total_tx_value=("transaction_value", "sum"))
        .sort_values("pct_any_savings", ascending=False)
    )
    health = pd.read_csv(RAW / "kopdes_stats_province.csv")[
        ["province", "average_health_index", "health_status"]
    ]
    prov = prov.merge(health, on="province", how="left")
    write_csv(prov, OUT / "savings_by_province.csv")
    print("\nProvince spread of savings uptake:\n")
    print(prov[["province", "pct_any_savings", "pct_pokok", "pct_wajib", "average_health_index"]]
          .to_string(index=False))

    # --- 8. national cross-check of the totals above --------------------------
    print(f"\nsavings total Rp {total/1e9:.1f} miliar "
          f"(~USD {total/IDR_PER_USD/1e6:.1f}M) vs "
          f"transactions Rp {tx_total/1e9:.1f} miliar "
          f"(~USD {tx_total/IDR_PER_USD/1e6:.1f}M)  [at {IDR_PER_USD:,}/USD]")


if __name__ == "__main__":
    main()
