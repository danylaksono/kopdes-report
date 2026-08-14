#!/usr/bin/env python3
"""
Build the Kisi Provinsi cartogram grid for the explorer.

The grid LAYOUT is the Indonesia cartogram that ships with the geo-morpher
example data, committed at data/raw/cartogram/indonesia_grid.csv and keyed by
BPS province codes. This script re-keys that layout to SIMKOPDES province ids,
so the explorer can join it straight to its own provinsi boundary
(data/web/boundaries/provinsi.geojson, properties.id = province_id) with no
name matching in the browser.

The re-key is a name join over the same 38 provinces (including the six Papua
splits). It is lossless; any miss is printed and the script exits non-zero.

Output: data/web/cartogram/provinsi_grid.csv  (id,row,col)

Usage:
  python scripts/build_province_cartogram.py
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = ROOT / "data" / "raw" / "cartogram" / "indonesia_grid.csv"
DEFAULT_BOUNDARY = ROOT / "data" / "web" / "boundaries" / "provinsi.geojson"
DEFAULT_OUT = ROOT / "data" / "web" / "cartogram" / "provinsi_grid.csv"


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


# Same province, different long-form name: the geo-morpher data calls Jakarta
# "Daerah Khusus Ibukota Jakarta", our boundary calls it "DKI Jakarta".
NAME_ALIASES = {
    "DAERAHKHUSUSIBUKOTAJAKARTA": "DKIJAKARTA",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--boundary", default=str(DEFAULT_BOUNDARY))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    boundary = json.loads(Path(args.boundary).read_text(encoding="utf-8"))
    id_by_name = {
        norm(f["properties"]["name"]): f["properties"]["id"]
        for f in boundary["features"]
    }

    rows = []
    with open(args.src, encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            name = NAME_ALIASES.get(norm(rec["Provinsi"]), norm(rec["Provinsi"]))
            pid = id_by_name.get(name)
            if pid is None:
                print(f"  MISS {rec['Provinsi']!r} -> no provinsi boundary")
                sys.exit(1)
            rows.append((pid, int(rec["row"]), int(rec["col"])))

    rows.sort(key=lambda r: r[0])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "row", "col"])
        w.writerows(rows)

    print(f"wrote {len(rows)} grid cells to {out}")


if __name__ == "__main__":
    main()
