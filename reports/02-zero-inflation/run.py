#!/usr/bin/env python3
"""
02-zero-inflation - how much of the performance data is actually zero, and is
the zero-ness patterned?

Reads only committed CSVs; no network, deterministic.

The point is to establish (a) that transaction volume is unusable as a
continuous outcome variable, and (b) that administrative fields are almost
fully populated while activity fields are not - which is the main clue about
whether zeros are inactivity or non-reporting.

Usage: python reports/02-zero-inflation/run.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.common import RAW, out_dir, write_csv  # noqa: E402

OUT = out_dir(__file__)

# Split deliberately: the first group is filled in when a cooperative is
# registered, the second only when it does something.
ADMIN_COLS = ["accounts_count", "npwp_count", "nib_count"]
ACTIVITY_COLS = [
    "transaction_volume",
    "transaction_value",
    "simpanan_pokok_amount",
    "simpanan_wajib_amount",
    "savings_total_amount",
]


def main():
    v = pd.read_csv(RAW / "kopdes_stats_village.csv")

    rows = []
    for kind, cols in (("administrative", ADMIN_COLS), ("activity", ACTIVITY_COLS)):
        for c in cols:
            rows.append(
                {
                    "field": c,
                    "kind": kind,
                    "rows": len(v),
                    "nonzero": int((v[c] > 0).sum()),
                    "pct_nonzero": round(100 * float((v[c] > 0).mean()), 2),
                }
            )
    overall = pd.DataFrame(rows)
    print("Village-level fields, share that are non-zero (n=%d villages)\n" % len(v))
    print(overall.to_string(index=False))
    write_csv(overall, OUT / "zero_inflation_by_field.csv")

    # Conditioning on "has an account" isolates reporting from existence: a
    # village with an account is registered and connected to the system, so a
    # zero there is a stronger signal than a zero in a village with nothing.
    with_acct = v[v.accounts_count > 0]
    cond = pd.DataFrame(
        [
            {
                "field": c,
                "villages_with_account": len(with_acct),
                "pct_nonzero_given_account": round(100 * float((with_acct[c] > 0).mean()), 2),
            }
            for c in ADMIN_COLS + ACTIVITY_COLS
            if c != "accounts_count"
        ]
    )
    print()
    print("Conditioned on the village having at least one account:\n")
    print(cond.to_string(index=False))
    write_csv(cond, OUT / "zero_inflation_given_account.csv")

    # Province gradient: if zeros were a random data backlog they would be flat
    # across provinces. If they track development/connectivity they are either
    # real inactivity or reporting capacity - the two we cannot separate.
    prov = (
        v.groupby("province")
        .agg(
            villages=("village", "size"),
            cooperatives=("cooperatives", "sum"),
            pct_tx_nonzero=("transaction_value", lambda s: round(100 * float((s > 0).mean()), 2)),
            pct_savings_nonzero=("savings_total_amount", lambda s: round(100 * float((s > 0).mean()), 2)),
            pct_account_nonzero=("accounts_count", lambda s: round(100 * float((s > 0).mean()), 2)),
            total_tx_value=("transaction_value", "sum"),
        )
        .sort_values("pct_tx_nonzero", ascending=False)
        .reset_index()
    )
    print()
    print("Province spread of transaction non-zero rate: min %.1f%%  median %.1f%%  max %.1f%%"
          % (prov.pct_tx_nonzero.min(), prov.pct_tx_nonzero.median(), prov.pct_tx_nonzero.max()))
    write_csv(prov, OUT / "zero_inflation_by_province.csv")

    # Concentration - what share of national transaction value sits in the top
    # N villages. This is the "H7" question.
    tx = v.transaction_value.sort_values(ascending=False)
    total = tx.sum()
    conc = pd.DataFrame(
        [
            {"top_n_villages": n, "share_of_national_tx_value": round(100 * float(tx.head(n).sum() / total), 2)}
            for n in (10, 50, 100, 500, 1000, 2521)
        ]
    )
    print()
    print("Concentration of transaction value:\n")
    print(conc.to_string(index=False))
    write_csv(conc, OUT / "transaction_concentration.csv")


if __name__ == "__main__":
    main()
