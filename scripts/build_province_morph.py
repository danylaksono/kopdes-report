#!/usr/bin/env python3
"""
Build the data file for the province morph prototype (_proto/morph): one row
per province, copied verbatim from the analysis mart.

This exists so the demo page gets its glyph data without loading duckdb-wasm.
It computes nothing: the 38 rows are the exact rows of
data/web/kopdes_provinsi.parquet, in province_id order. NaN and infinity become
null, because JSON has no representation for them and the browser would
otherwise receive values it cannot draw.

The cartogram layout itself is NOT built here. The prototype reuses the
Indonesia grid cartogram that ships with the geo-morpher example data (vendored
into _proto/morph/data/), so there is no grid generation step at all.

Usage:
  python scripts/build_province_morph.py
  python scripts/build_province_morph.py --out _proto/morph/data/provinsi_morph.json
"""

import argparse
import json
import math
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = ROOT / "data" / "web" / "kopdes_provinsi.parquet"
DEFAULT_OUT = ROOT / "_proto" / "morph" / "data" / "provinsi_morph.json"


def clean(value):
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    con = duckdb.connect()
    try:
        table = con.execute(
            f"select * from read_parquet('{args.src}') order by province_id"
        )
        cols = [d[0] for d in table.description]
        rows = [
            {k: clean(v) for k, v in zip(cols, row)} for row in table.fetchall()
        ]
    finally:
        con.close()

    payload = {
        "source": Path(args.src).name,
        "note": (
            "Glyph data for the province morph prototype, copied verbatim from "
            "the analysis mart. Rows are keyed to the geo-morpher example "
            "cartogram by normalized province name in the demo page."
        ),
        "provinces": rows,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"wrote {len(rows)} provinces to {out}")


if __name__ == "__main__":
    main()
