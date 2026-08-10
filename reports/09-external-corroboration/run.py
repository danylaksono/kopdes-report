#!/usr/bin/env python3
"""
09-external-corroboration - does the ministry's own public arithmetic match its
dashboard?

This answers the single strongest rebuttal available to the government. Every
finding in this investigation rests on SIMKOPDES reporting almost no economic
activity, and the ministry can answer that with *"the website simply isn't up to
date"*. [01](../01-snapshot-drift/) narrowed that defence but could not close
it: four days is a short window, and a system nobody has finished filling in
looks exactly like a system with nothing to report.

The way to close it is from outside. Either the ministry's own public statements
match its dashboard - in which case the dashboard *is* the official number and
the rebuttal collapses - or they diverge, which is a story in itself. Both
outcomes are useful, which is why this is worth running before knowing the
answer.

Method
------
`external_figures.csv` holds every published figure found, one row per claim,
with an as-of date, the outlet, who said it, the URL and a verbatim quote. It is
**hand-curated and committed**, because a press figure cannot be re-derived and a
URL can go dead. Nothing here is scraped at run time - a scraper would silently
change the evidence base between runs.

This script reconciles those figures against our own snapshots:

  data/raw/                     the 2026-08-05 baseline (committed)
  data/snapshots/YYYY-MM-DD/    dated pulls (gitignored, held locally)

Village statistics are deduplicated on `village_id` before summing - the export
repeats 1,555 villages, and summing rows inflates the total (01).

The comparison that matters is `transaction_value`, because that is the number
the whole investigation turns on and the number the press prints.

Usage:
  python reports/09-external-corroboration/run.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.common import RAW, ROOT, out_dir, write_csv  # noqa: E402

OUT = out_dir(__file__)
SNAPSHOTS = ROOT / "data" / "snapshots"
BASELINE_DATE = "2026-08-05"   # what data/raw is, per AGENTS.md


def our_snapshots():
    """Every SIMKOPDES export we hold, summed the same way every time."""
    rows = []
    sources = [(BASELINE_DATE, RAW)]
    if SNAPSHOTS.exists():
        sources += [(p.name, p) for p in sorted(SNAPSHOTS.iterdir()) if p.is_dir()]

    for date, path in sources:
        vil = path / "kopdes_stats_village.csv"
        if not vil.exists():
            print(f"  {date}: no village file, skipped")
            continue
        d = pd.read_csv(vil).drop_duplicates("village_id")
        loc = path / "kopdes_locations.csv"
        rows.append({
            "as_of": date,
            "source": str(path.relative_to(ROOT)).replace("\\", "/"),
            "villages": len(d),
            "villages_reporting": int((d.transaction_value > 0) .sum()),
            "transaction_value_idr": int(d.transaction_value.sum()),
            "cooperatives_total": len(pd.read_csv(loc)) if loc.exists() else None,
        })
    return pd.DataFrame(rows)


def main():
    ext = pd.read_csv(OUT / "external_figures.csv")
    print(f"external figures on file: {len(ext)} claims from "
          f"{ext.outlet.nunique()} outlets, {ext.as_of.min()} to {ext.as_of.max()}\n")

    print("our snapshots:")
    ours = our_snapshots()
    for _, r in ours.iterrows():
        print(f"  {r.as_of}  {r.source:28} Rp {r.transaction_value_idr/1e9:8,.2f} miliar   "
              f"{r.villages_reporting:,} villages reporting")
    write_csv(ours, OUT / "our_snapshot_totals.csv")

    # --- the reconciliation -------------------------------------------------
    # Only same-day pairs are compared. Comparing across dates would be
    # comparing a growing series against itself.
    ev = ext[ext.metric == "transaction_value_idr"][["as_of", "value", "outlet", "url"]]
    cmp = ours.merge(ev, on="as_of", how="inner")
    if len(cmp):
        cmp["published_idr"] = cmp.value.astype("int64")
        cmp["ours_idr"] = cmp.transaction_value_idr
        cmp["difference_idr"] = cmp.ours_idr - cmp.published_idr
        cmp["pct_difference"] = (100 * cmp.difference_idr / cmp.published_idr).round(3)
        cmp = cmp[["as_of", "outlet", "published_idr", "ours_idr",
                   "difference_idr", "pct_difference", "url"]]
        print("\nsame-day reconciliation:")
        for _, r in cmp.iterrows():
            print(f"  {r.as_of}  published Rp {r.published_idr/1e9:,.2f} miliar   "
                  f"ours Rp {r.ours_idr/1e9:,.2f} miliar   "
                  f"difference {r.pct_difference:+.3f}%")
        write_csv(cmp, OUT / "reconciliation.csv",
                  "same-day comparison of published figure vs our own extraction")
    else:
        print("\n  no same-day pair - hold a snapshot on a date the press quoted")

    # --- the published series -----------------------------------------------
    series = ext[ext.metric == "transaction_value_idr"].copy()
    series["miliar"] = (series.value / 1e9).round(2)
    series = series.sort_values("as_of")
    prev = series.miliar.shift()
    series["change_miliar"] = (series.miliar - prev).round(2)
    print("\npublished transaction-value series:")
    print(series[["as_of", "miliar", "change_miliar", "outlet"]].to_string(index=False))
    write_csv(series[["as_of", "value", "miliar", "change_miliar", "outlet", "url"]],
              OUT / "published_series.csv")

    # --- the activity claim, independently -----------------------------------
    # The government's own count of cooperatives actually trading is the second
    # line of evidence, and it does not depend on the dashboard at all.
    op = ext[ext.metric == "cooperatives_operating"]
    if len(op) and len(ours):
        latest = ours.iloc[-1]
        print(f"\ngovernment's own operating count: {int(op.value.iloc[0]):,} "
              f"({op.as_of.iloc[0]}, {op.outlet.iloc[0]})")
        print(f"our villages reporting any transaction: {latest.villages_reporting:,} "
              f"({latest.as_of})")
        print(f"registry size: {int(latest.villages):,} villages")
        print(f"  -> both are ~{100*int(op.value.iloc[0])/int(latest.villages):.1f}% and "
              f"~{100*latest.villages_reporting/int(latest.villages):.1f}% of the registry")

    # Provincial cross-check: the June statement named two provinces and gave a
    # count for each. Our export is later, so ours should be larger and in the
    # same places - a weaker test than the totals, but an independent one.
    prov_claims = ext[ext.metric.str.startswith("operating_")]
    if len(prov_claims):
        mart = ROOT / "data" / "web" / "kopdes_provinsi.parquet"
        if mart.exists():
            import duckdb
            p = duckdb.connect().execute(
                f"select province, villages_reporting from read_parquet('{mart.as_posix()}')"
            ).fetchdf()
            name = {"operating_jawa_timur": "JAWA TIMUR",
                    "operating_jawa_tengah": "JAWA TENGAH"}
            rows = []
            for _, c in prov_claims.iterrows():
                prov = name.get(c.metric)
                got = p[p.province == prov]
                rows.append({
                    "province": prov,
                    "government_operating": int(c.value),
                    "government_as_of": c.as_of,
                    "ours_reporting": int(got.villages_reporting.iloc[0]) if len(got) else None,
                    "ours_as_of": ours.iloc[-1].as_of,
                })
            pc = pd.DataFrame(rows)
            print()
            print(pc.to_string(index=False))
            write_csv(pc, OUT / "provincial_cross_check.csv")
        else:
            print(f"\n  note: {mart.name} missing - run scripts/build_analysis_mart.py")


if __name__ == "__main__":
    main()
