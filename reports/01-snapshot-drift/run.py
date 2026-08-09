#!/usr/bin/env python3
"""
01-snapshot-drift - is SIMKOPDES still being filled in, and are the zeros
temporary?

SIMKOPDES is a live system under active rollout, so a zero in our snapshot has
two possible readings:
  (a) the cooperative genuinely has no activity, or
  (b) the activity exists but hasn't been entered into the system yet.

These have opposite policy implications and the snapshot alone cannot tell them
apart - there is no per-record timestamp in the API (see README.md).

The only instrument that separates them is time: re-query the live API and see
whether zeros convert to non-zeros. This script does that for a random sample
of subdistricts, comparing data/raw/kopdes_stats_subdistrict.csv (the committed
snapshot) against the API right now.

HITS THE LIVE API. Results are expected to differ from the committed CSVs -
that is the entire point. Re-running appends nothing; it overwrites with a
fresh comparison, so keep prior runs by committing the CSVs.

Usage: python reports/01-snapshot-drift/run.py [--sample N] [--seed S]
"""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from _lib.common import RAW, live_client, out_dir, write_csv  # noqa: E402

OUT = out_dir(__file__)


def fetch_one(api, row):
    try:
        node = api.get(
            "/statistics/national-readiness/subdistrict/%d" % row.subdistrict_id, tries=2
        )
    except Exception:
        return None
    econ = node.get("economic_impact") or {}
    savings = node.get("savings_summary") or {}
    return {
        "subdistrict_id": row.subdistrict_id,
        "province": row.province,
        "district": row.district,
        "subdistrict": row.subdistrict,
        "cooperatives": row.cooperatives,
        "snapshot_tx_value": row.transaction_value,
        "live_tx_value": econ.get("total_value"),
        "snapshot_tx_volume": row.transaction_volume,
        "live_tx_volume": econ.get("total_volume"),
        "snapshot_savings": row.savings_total_amount,
        "live_savings": savings.get("total_amount"),
    }


def summarise(d, prefix, label):
    old, new = d["snapshot_" + prefix], d["live_" + prefix]
    was_zero = old == 0
    return {
        "measure": label,
        "n_sampled": len(d),
        "changed": int((old != new).sum()),
        "was_zero": int(was_zero.sum()),
        "was_zero_now_positive": int((was_zero & (new > 0)).sum()),
        "zero_conversion_rate": round(float((new[was_zero] > 0).mean()) if was_zero.any() else 0.0, 5),
        "was_positive_increased": int(((old > 0) & (new > old)).sum()),
        "was_positive_decreased": int(((old > 0) & (new < old)).sum()),
        "total_delta": float((new - old).sum()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=400)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    snap = pd.read_csv(RAW / "kopdes_stats_subdistrict.csv")
    sample = snap.sample(min(args.sample, len(snap)), random_state=args.seed)

    print(f"querying live SIMKOPDES for {len(sample):,} subdistricts...")
    api = live_client()
    with ThreadPoolExecutor(12) as pool:
        rows = [r for r in pool.map(lambda t: fetch_one(api, t[1]), sample.iterrows()) if r]

    d = pd.DataFrame(rows).dropna(subset=["live_tx_value"])
    for col in ("live_tx_value", "live_tx_volume", "live_savings"):
        d[col] = d[col].astype(float)
    d["tx_value_delta"] = d.live_tx_value - d.snapshot_tx_value
    d["savings_delta"] = d.live_savings - d.snapshot_savings

    summary = pd.DataFrame(
        [summarise(d, "tx_value", "transaction_value"), summarise(d, "savings", "savings_total_amount")]
    )
    summary.insert(0, "checked_at", datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"))
    summary.insert(1, "snapshot_date", "2026-08-05")

    print()
    print(summary.to_string(index=False))
    print()
    write_csv(summary, OUT / "drift_summary.csv")
    write_csv(
        d[d.tx_value_delta.ne(0) | d.savings_delta.ne(0)].sort_values("tx_value_delta", ascending=False),
        OUT / "drift_changed_rows.csv",
        "only the subdistricts that moved",
    )


if __name__ == "__main__":
    main()
