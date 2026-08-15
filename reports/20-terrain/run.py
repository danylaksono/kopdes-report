#!/usr/bin/env python3
"""
20-terrain - how high, and how broken, is the ground under every KDMP?

04 sampled Copernicus GLO-30 but only for its 2,500-candidate shortlist, so
`elevation_m` and `relief_200m_m` were populated for 3% of the registry and the
"steep ground" finding could only ever be stated as "of the 2,500 most remote".
19 had already fixed exactly this asymmetry for land cover by reusing 04's
sampler over every coordinate; this report does the same for the DEM.

WHAT `relief_200m_m` IS, AND IS NOT
-----------------------------------
It is max minus min elevation over a 7x7 window of 30 m DEM, i.e. the total
height range within roughly 200 m of the point. It is a **relief proxy, not a
slope**: it cannot tell a uniform 30% gradient from a flat shelf with one cliff
at its edge, and it carries no direction. 04's threshold of >60 m over ~200 m is
kept here unchanged so the two reports remain comparable, but the honest public
wording is "ground that rises or falls more than 60 m within about 200 m", never
"a 30-degree slope".

Elevation is the more robust of the two: a single pixel of a 30 m DEM is a good
estimate of height and a poor estimate of steepness.

Usage:
  python reports/20-terrain/run.py

Outputs:
  reports/20-terrain/kopdes_terrain.csv    per cooperative (gitignored, large)
  reports/20-terrain/terrain_bands.csv     national distribution
  reports/20-terrain/terrain_by_island.csv the geography of it
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

# 04's threshold, kept identical on purpose: two reports disagreeing about what
# "steep" means would be worse than the proxy being crude.
STEEP_M = 60

ELEVATION_BANDS = [
    (0, 50, "0-50 m (dataran pantai)"),
    (50, 200, "50-200 m (dataran rendah)"),
    (200, 500, "200-500 m (perbukitan)"),
    (500, 1000, "500-1.000 m (dataran tinggi)"),
    (1000, 2000, "1.000-2.000 m (pegunungan)"),
    (2000, 10000, "di atas 2.000 m"),
]
RELIEF_BANDS = [
    (0, 10, "< 10 m (rata)"),
    (10, 30, "10-30 m (bergelombang)"),
    (30, 60, "30-60 m (berbukit)"),
    (60, 150, "60-150 m (curam)"),
    (150, 10000, "> 150 m (sangat curam)"),
]

ISLANDS = {
    "SUMATRA": ["ACEH", "SUMATERA UTARA", "SUMATERA BARAT", "RIAU", "JAMBI",
                "SUMATERA SELATAN", "BENGKULU", "LAMPUNG",
                "KEPULAUAN BANGKA BELITUNG", "KEPULAUAN RIAU"],
    "JAVA": ["DKI JAKARTA", "JAWA BARAT", "JAWA TENGAH",
             "DAERAH ISTIMEWA YOGYAKARTA", "JAWA TIMUR", "BANTEN"],
    "NUSA TENGGARA": ["BALI", "NUSA TENGGARA BARAT", "NUSA TENGGARA TIMUR"],
    "KALIMANTAN": ["KALIMANTAN BARAT", "KALIMANTAN TENGAH", "KALIMANTAN SELATAN",
                   "KALIMANTAN TIMUR", "KALIMANTAN UTARA"],
    "SULAWESI": ["SULAWESI UTARA", "SULAWESI TENGAH", "SULAWESI SELATAN",
                 "SULAWESI TENGGARA", "GORONTALO", "SULAWESI BARAT"],
    "MALUKU": ["MALUKU", "MALUKU UTARA"],
    "PAPUA": ["PAPUA", "PAPUA BARAT", "PAPUA SELATAN", "PAPUA TENGAH",
              "PAPUA PEGUNUNGAN", "PAPUA BARAT DAYA"],
}


def load_04_sampler():
    """Reuse 04's cloud-raster sampler rather than copy 80 lines of it."""
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


def band(value, bands):
    if pd.isna(value):
        return None
    for lo, hi, label in bands:
        if lo <= value < hi:
            return label
    return bands[-1][2]


def main():
    loc = pd.read_csv(
        LOCATIONS, usecols=["cooperative_id", "province", "latitude", "longitude"]
    )
    loc = loc.dropna(subset=["latitude", "longitude"]).set_index("cooperative_id")
    print(f"sampling {len(loc):,} coordinates")

    s04 = load_04_sampler()
    dem = s04.sample_all(
        loc, s04.dem_url, s04.dem_key,
        window_px=7, label="Copernicus GLO-30 DEM",
    )

    out = pd.DataFrame({
        "cooperative_id": loc.index,
        "province": loc.province.values,
        "elevation_m": [dem.get(i, (np.nan, np.nan))[0] for i in loc.index],
        "relief_200m_m": [dem.get(i, (np.nan, np.nan))[1] for i in loc.index],
    })
    out["flag_steep"] = out.relief_200m_m > STEEP_M
    resolved = out.elevation_m.notna()
    print(f"\nresolved {resolved.sum():,} of {len(out):,} ({100 * resolved.mean():.1f}%)")

    # Same reconciliation 19 does: 04 sampled this raster at these coordinates
    # already, so the two runs must agree wherever they overlap.
    short = pd.read_csv(SHORTLIST, usecols=["cooperative_id", "elevation_m", "relief_200m_m"])
    m = out.merge(short, on="cooperative_id", suffixes=("", "_04"))
    both = m[m.elevation_m.notna() & m.elevation_m_04.notna()]
    if len(both):
        agree = np.isclose(both.elevation_m, both.elevation_m_04, atol=0.5).mean()
        print(f"  reconciliation vs 04 shortlist: {agree:.1%} of {len(both):,} agree on elevation")

    write_csv(out, OUT / "kopdes_terrain.csv", "per-cooperative")

    # --- national distribution ------------------------------------------------
    rows = []
    for col, bands, kind in (("elevation_m", ELEVATION_BANDS, "elevation"),
                             ("relief_200m_m", RELIEF_BANDS, "relief")):
        labels = out[col].map(lambda v: band(v, bands))
        for _, _, label in bands:
            n = int((labels == label).sum())
            rows.append({"measure": kind, "band": label, "cooperatives": n,
                         "pct": round(100 * n / int(resolved.sum()), 2)})
    bands_df = pd.DataFrame(rows)
    print("\nNational distribution:\n")
    print(bands_df.to_string(index=False))
    write_csv(bands_df, OUT / "terrain_bands.csv")

    steep_n = int(out.flag_steep.sum())
    print(f"\nsteep ground (>{STEEP_M} m relief over ~200 m): {steep_n:,} "
          f"({100 * steep_n / int(resolved.sum()):.2f}% of resolved)")
    print(f"median elevation {out.elevation_m.median():,.0f} m, "
          f"median relief {out.relief_200m_m.median():,.0f} m")

    # --- geography ------------------------------------------------------------
    prov_to_island = {p: isl for isl, ps in ISLANDS.items() for p in ps}
    out["island"] = out.province.map(prov_to_island)
    isl = (
        out[resolved].groupby("island", as_index=False)
        .agg(cooperatives=("cooperative_id", "size"),
             median_elevation_m=("elevation_m", "median"),
             median_relief_m=("relief_200m_m", "median"),
             pct_steep=("flag_steep", lambda s: round(100 * float(s.mean()), 2)))
        .sort_values("pct_steep", ascending=False)
    )
    print("\nBy island:\n")
    print(isl.to_string(index=False))
    write_csv(isl, OUT / "terrain_by_island.csv")


if __name__ == "__main__":
    main()
