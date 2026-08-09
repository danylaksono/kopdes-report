#!/usr/bin/env python3
"""
Compare two committed SIMKOPDES snapshots, village by village.

This supersedes run.py's live-API sampling as the primary drift measurement.
run.py samples 400 subdistricts against whatever the API says right now; this
compares *every* village between two frozen snapshots, needs no network, and
gives the same answer to anyone who checks out the repo.

Why this measurement carries the investigation
----------------------------------------------
97% of villages report no transactions at all. The government's strongest
rebuttal is that the figures simply have not been entered yet. A single
snapshot cannot distinguish "no business" from "no paperwork"; a series can,
because a reporting backlog being worked through shows up as zeros turning
into non-zeros over time.

TWO GOTCHAS, both discovered the hard way:

1. **Deduplicate before comparing.** The 2026-08-05 export contains 1,555
   duplicate village_ids (also 148 subdistricts, 5 districts). Comparing raw
   row counts makes it look as though 1,555 villages disappeared. They did not.
2. Those same duplicates inflate any sum over rows - the village-level
   transaction total was overstated by IDR 18.8M against the province total.

Usage:
  python reports/01-snapshot-drift/diff_snapshots.py data/raw data/snapshots/2026-08-09
  python reports/01-snapshot-drift/diff_snapshots.py <t0_dir> <t1_dir> --label-t0 2026-08-05
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.common import ROOT, out_dir, write_csv  # noqa: E402

OUT = out_dir(__file__)

MEASURES = [
    ("transaction_value", "activity"),
    ("transaction_volume", "activity"),
    ("savings_total_amount", "activity"),
    ("accounts_count", "administrative"),
    ("npwp_count", "administrative"),
    ("nib_count", "administrative"),
    ("cooperatives", "administrative"),
]


def load(snapshot_dir: Path, name: str, key: str) -> pd.DataFrame:
    df = pd.read_csv(snapshot_dir / name)
    before = len(df)
    df = df.drop_duplicates(key)
    if before != len(df):
        print(f"  {snapshot_dir.name}/{name}: dropped {before - len(df):,} duplicate {key}s")
    return df


def snapshot_label(snapshot_dir: Path, fallback: str) -> str:
    manifest = snapshot_dir / "_manifest.json"
    if manifest.exists():
        return json.loads(manifest.read_text(encoding="utf-8")).get("snapshot_date", fallback)
    return fallback


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("t0", type=Path)
    ap.add_argument("t1", type=Path)
    ap.add_argument("--label-t0", default=None)
    ap.add_argument("--label-t1", default=None)
    args = ap.parse_args()

    l0 = args.label_t0 or snapshot_label(args.t0, args.t0.name)
    l1 = args.label_t1 or snapshot_label(args.t1, args.t1.name)
    print(f"comparing {l0} -> {l1}\n")

    a = load(args.t0, "kopdes_stats_village.csv", "village_id")
    b = load(args.t1, "kopdes_stats_village.csv", "village_id")

    m = a.merge(b, on="village_id", suffixes=("_t0", "_t1"), how="outer", indicator=True)
    appeared = int((m._merge == "right_only").sum())
    vanished = int((m._merge == "left_only").sum())
    m = m[m._merge == "both"]
    print(f"\nvillages: {len(m):,} in both, {appeared:,} new, {vanished:,} gone\n")

    rows = []
    for col, kind in MEASURES:
        old, new = m[col + "_t0"], m[col + "_t1"]
        was_zero = old == 0
        rows.append(
            {
                "measure": col,
                "kind": kind,
                "villages_compared": len(m),
                "changed": int((old != new).sum()),
                "was_zero": int(was_zero.sum()),
                "zero_to_positive": int((was_zero & (new > 0)).sum()),
                "positive_to_zero": int(((old > 0) & (new == 0)).sum()),
                "conversion_rate_pct": round(100 * float((new[was_zero] > 0).mean()), 5) if was_zero.any() else 0.0,
                "net_delta": float(new.sum() - old.sum()),
            }
        )
    summary = pd.DataFrame(rows)
    summary.insert(0, "t0", l0)
    summary.insert(1, "t1", l1)
    print(summary.drop(columns=["t0", "t1", "kind"]).to_string(index=False))
    write_csv(summary, OUT / "snapshot_diff_summary.csv")

    changed = m[m.transaction_value_t0 != m.transaction_value_t1].copy()
    if len(changed):
        keep = ["village_id", "province_t0", "district_t0", "subdistrict_t0", "village_t0",
                "transaction_value_t0", "transaction_value_t1", "savings_total_amount_t0",
                "savings_total_amount_t1"]
        changed = changed[[c for c in keep if c in changed.columns]]
        changed["transaction_delta"] = changed.transaction_value_t1 - changed.transaction_value_t0
        write_csv(changed.sort_values("transaction_delta", ascending=False),
                  OUT / "snapshot_diff_changed_villages.csv", "every village whose transactions moved")

    z = m[m.transaction_value_t0 == 0]
    converted = int((z.transaction_value_t1 > 0).sum())
    print()
    print(f"villages with ZERO transactions at {l0}: {len(z):,}")
    print(f"  reporting any activity by {l1}: {converted:,}  ({100*converted/len(z):.4f}%)")
    if converted:
        # A rate this low is more legible as a horizon than a percentage, but it
        # assumes the backlog drains at a constant rate - which a single batch
        # release would break. State it as "at the rate observed", never as a
        # forecast.
        days = (pd.Timestamp(l1) - pd.Timestamp(l0)).days or 1
        per_year = converted * 365 / days
        print(f"  at that rate: ~{per_year:,.0f} villages/year would begin reporting;")
        print(f"  clearing the current {len(z):,} would take ~{len(z)/per_year:,.0f} years")


if __name__ == "__main__":
    main()
