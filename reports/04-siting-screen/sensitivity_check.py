#!/usr/bin/env python3
"""
Method validation for 04-siting-screen: is a single 10 m pixel enough?

The screen samples ESA WorldCover at one pixel per cooperative. That is only
sound if the answer is robust to (a) the pixel size and (b) positional error in
the SIMKOPDES coordinate, which is unknown and could be tens of metres. If a
cooperative sits 30 m from a village edge, a point sample could report "closed
forest" for a site that is effectively in a settlement.

This re-samples a random subset of the candidates at three window sizes and
reports how often the answer changes. It also computes the built-up fraction
within 250 m, which is a far more legible statistic for a write-up than a land
cover class code: "no built-up pixel within 250 m" is a claim a reader can
picture.

Run this whenever the screen's parameters change. It is the check that lets the
paper say the classification is not an artefact of the sampling design.

Usage: python reports/04-siting-screen/sensitivity_check.py [--sample 250]
"""

import argparse
import math
import os
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.common import out_dir, write_csv  # noqa: E402

OUT = out_dir(__file__)
os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")

BUILT_UP = 50           # ESA WorldCover class
WINDOWS = [1, 11, 25]   # 10 m, 110 m, 250 m at 10 m resolution


def cover_url(lat, lon):
    la, lo = math.floor(lat / 3) * 3, math.floor(lon / 3) * 3
    ns, ew = ("N", "S")[la < 0], ("E", "W")[lo < 0]
    name = f"ESA_WorldCover_10m_2021_v200_{ns}{abs(la):02d}{ew}{abs(lo):03d}_Map"
    return f"https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/{name}.tif"


def work(item):
    _, points = item
    out = {}
    try:
        with rasterio.open(cover_url(points[0][2], points[0][1])) as ds:
            for idx, lon, lat in points:
                try:
                    row, col = ds.index(lon, lat)
                    res = {}
                    for w in WINDOWS:
                        half = w // 2
                        arr = ds.read(
                            1,
                            window=rasterio.windows.Window(col - half, row - half, w, w),
                            boundless=True,
                            fill_value=0,
                        )
                        arr = arr[arr > 0]  # 0 = outside the tile
                        if arr.size:
                            res[w] = (
                                Counter(arr.tolist()).most_common(1)[0][0],
                                float((arr == BUILT_UP).mean()),
                            )
                    if len(res) == len(WINDOWS):
                        out[idx] = res
                except Exception:
                    continue
    except Exception:
        pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=250)
    ap.add_argument("--seed", type=int, default=3)
    args = ap.parse_args()

    cand = pd.read_csv(OUT / "candidates.csv").dropna(subset=["landcover_code"])
    sub = cand.sample(min(args.sample, len(cand)), random_state=args.seed)

    groups = defaultdict(list)
    for idx, lon, lat in zip(sub.index, sub.longitude, sub.latitude):
        groups[(math.floor(lat / 3) * 3, math.floor(lon / 3) * 3)].append((idx, lon, lat))

    res = {}
    with ThreadPoolExecutor(8) as pool:
        for got in pool.map(work, groups.items()):
            res.update(got)
    print(f"compared {len(res)} points across window sizes {WINDOWS} (10 m px)\n")

    rows = []
    for w in WINDOWS[1:]:
        agree = sum(v[1][0] == v[w][0] for v in res.values())
        rows.append(
            {
                "window_px": w,
                "window_m": w * 10,
                "n": len(res),
                "centre_class_equals_window_majority": agree,
                "pct_agreement": round(100 * agree / len(res), 1),
            }
        )
        print(f"  centre 10 m class == majority over {w*10:>3} m window : "
              f"{agree}/{len(res)} = {100*agree/len(res):.1f}%")
    write_csv(pd.DataFrame(rows), OUT / "sensitivity_window_agreement.csv")

    bu = np.array([v[25][1] for v in res.values()])
    bands = pd.DataFrame(
        [
            {"built_up_fraction_within_250m": "exactly 0%", "candidates": int((bu == 0).sum())},
            {"built_up_fraction_within_250m": ">0 and <5%", "candidates": int(((bu > 0) & (bu < 0.05)).sum())},
            {"built_up_fraction_within_250m": ">=5%", "candidates": int((bu >= 0.05).sum())},
        ]
    )
    print("\nbuilt-up fraction within 250 m:")
    print(bands.to_string(index=False))
    write_csv(bands, OUT / "sensitivity_builtup_within_250m.csv")


if __name__ == "__main__":
    main()
