#!/usr/bin/env python3
"""
19-land-cover - what land cover is every KDMP on?

04 sampled ESA WorldCover 10m but only for its 2,500-candidate shortlist; the
other ~81k coordinates were never classified. This report runs 04's own
cloud-raster sampler, reused as-is, over every cooperative coordinate, so the
table can carry a land-cover class per row instead of a shortlist flag.

Why a satellite classification and not OSM landuse: OSM draws landuse polygons
for a small fraction of rural Indonesia, and a miss there is not evidence (the
same asymmetry rule as 07). A 10 m raster covers every point; the price is a
2021 snapshot at a single pixel.

Read the column as "what the 10 m pixel under the recorded coordinate is
classified as in 2021", never as "this cooperative is standing in a forest".

Usage:
  python reports/19-land-cover/run.py

Outputs:
  reports/19-land-cover/kopdes_landcover.csv   cooperative_id, landcover_code, landcover
"""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.common import RAW, ROOT, out_dir, write_csv  # noqa: E402

OUT = out_dir(__file__)
LOCATIONS = RAW / "kopdes_locations.csv"
SHORTLIST = ROOT / "reports" / "04-siting-screen" / "candidates.csv"


def load_04_sampler():
    """
    Reuse 04's cloud-raster sampler rather than copy 80 lines of it.

    04/run.py takes its shortlist size from argv and guards main() behind
    __main__, so neutralising argv is enough to import it. Importing it also
    sets the GDAL/vsicurl environment defaults it needs.
    """
    spec = importlib.util.spec_from_file_location(
        "siting_screen", ROOT / "reports" / "04-siting-screen" / "run.py"
    )
    mod = importlib.util.module_from_spec(spec)
    saved, sys.argv = sys.argv, ["run"]
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.argv = saved
    return mod


def main():
    loc = pd.read_csv(LOCATIONS, usecols=["cooperative_id", "latitude", "longitude"])
    loc = loc.dropna(subset=["latitude", "longitude"]).set_index("cooperative_id")
    print(f"sampling {len(loc):,} coordinates")

    s04 = load_04_sampler()
    cov = s04.sample_all(
        loc, lambda a, b: s04.cover_url(a, b), s04.cover_key,
        window_px=5, label="ESA WorldCover 10m",
    )

    out = pd.DataFrame({
        "cooperative_id": loc.index,
        "landcover_code": [int(cov[i][0]) if i in cov else np.nan for i in loc.index],
    })
    out["landcover"] = out.landcover_code.map(s04.WORLDCOVER)

    # Cheap correctness check: 04 sampled the same raster at the same
    # coordinates for its shortlist. Two independent runs must agree on every
    # row 04 resolved; a mismatch means one of us moved the goalposts.
    short = pd.read_csv(SHORTLIST, usecols=["cooperative_id", "landcover_code"])
    merged = out.merge(short, on="cooperative_id", suffixes=("", "_04"))
    resolved = merged[merged.landcover_code_04.notna()]
    if len(resolved):
        match = (resolved.landcover_code == resolved.landcover_code_04).mean()
        print(f"  reconciliation vs 04 shortlist: {match:.1%} of {len(resolved):,} agree")
    else:
        print("  no 04 shortlist rows to reconcile against")

    print(out.landcover.value_counts(dropna=False).to_string())
    write_csv(out, OUT / "kopdes_landcover.csv")


if __name__ == "__main__":
    main()
