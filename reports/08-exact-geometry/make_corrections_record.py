#!/usr/bin/env python3
"""
Record which impossible coordinates the ministry fixed, and when.

`suspect_coordinates.csv` is a *live* output: it lists the points that fall
outside Indonesia in whatever snapshot `run.py` is pointed at. Once SIMKOPDES
corrected them it went to zero rows, which is the right behaviour for that file
and the wrong outcome for the claim built on it. The site says "19 impossible
coordinates on 5 August, all corrected by the ministry"; after the re-run,
nothing committed to this repo showed that this had ever been true.

This script writes the historical record instead: the before/after coordinates
for every point that left the Indonesia bounding box between snapshots. It is
not a re-runnable analysis of current data, it is evidence about a past state,
so its output is committed and `run.py` never overwrites it.

Two things it settles that the prose had wrong:

  - The count is 20, not 19. `run.py` found these accidentally, via an
    implausible maximum distance to a minimarket, which catches a point thrown
    to the far side of the planet but not one moved a few hundred kilometres
    north into the South China Sea. A bounding-box test catches both.
  - They were already corrected in the 2026-08-09 snapshot, not "between 10 and
    13 August".

Requires the dated snapshots under `data/snapshots/` (gitignored, 28 MB a pull).
Without them the committed CSV stands on its own.

Usage: python reports/08-exact-geometry/make_corrections_record.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.common import ROOT, out_dir  # noqa: E402

OUT = out_dir(__file__)

# Indonesia's land extent with a small margin. The northernmost point is about
# 5.9 N (Pulau Weh); 6.1 leaves room for the coastline without admitting a
# sign-flipped Java coordinate at 7 N.
BOX = dict(lat_min=-11.2, lat_max=6.1, lon_min=94.9, lon_max=141.1)

BASELINE = ROOT / "data" / "raw"  # the committed 2026-08-05 export
LATER = [
    ("2026-08-09", ROOT / "data" / "snapshots" / "2026-08-09"),
    ("2026-08-13", ROOT / "data" / "snapshots" / "2026-08-13"),
]


def outside(df):
    return df[
        (df.latitude > BOX["lat_max"])
        | (df.latitude < BOX["lat_min"])
        | (df.longitude < BOX["lon_min"])
        | (df.longitude > BOX["lon_max"])
    ]


def diagnose(row):
    """Why is this point impossible, and what does the fix look like?"""
    if abs(row.latitude) > 90 or abs(row.longitude) > 180:
        return "out-of-range value"
    if BOX["lat_min"] <= -row.latitude <= BOX["lat_max"]:
        return "latitude sign flipped (N instead of S)"
    return "outside Indonesia, cause unclear"


def main():
    base = pd.read_csv(BASELINE / "kopdes_locations.csv")
    bad = outside(base).copy()
    bad["diagnosis"] = bad.apply(diagnose, axis=1)
    print(f"2026-08-05 baseline: {len(bad)} coordinates outside Indonesia")
    print(bad.diagnosis.value_counts().to_string(), "\n")

    rec = bad[
        ["cooperative_id", "name", "province", "district", "latitude", "longitude", "diagnosis"]
    ].rename(columns={"latitude": "lat_2026_08_05", "longitude": "lon_2026_08_05"})

    first_fixed = {}
    for date, path in LATER:
        f = path / "kopdes_locations.csv"
        if not f.exists():
            print(f"  {date}: snapshot not present, skipped")
            continue
        later = pd.read_csv(f).set_index("cooperative_id")
        rec[f"lat_{date.replace('-', '_')}"] = rec.cooperative_id.map(later.latitude)
        rec[f"lon_{date.replace('-', '_')}"] = rec.cooperative_id.map(later.longitude)
        still = rec.cooperative_id.map(
            lambda i: i in later.index and len(outside(later.loc[[i]])) > 0
        )
        print(f"  {date}: {int(still.sum())} of {len(rec)} still outside Indonesia")
        for i in rec.cooperative_id[~still]:
            first_fixed.setdefault(i, date)

    rec["first_snapshot_corrected"] = rec.cooperative_id.map(first_fixed)
    rec = rec.sort_values("cooperative_id")
    rec.to_csv(OUT / "corrected_coordinates_2026-08.csv", index=False)
    print(f"\n  wrote {(OUT / 'corrected_coordinates_2026-08.csv').relative_to(ROOT)} ({len(rec)} rows)")
    print("\nfirst snapshot in which each was corrected:")
    print(rec.first_snapshot_corrected.value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
