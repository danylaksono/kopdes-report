#!/usr/bin/env python3
"""
Build a compact point layer for the home page's "Momen peta" map.

The explorer reads the full mart through duckdb-wasm; the story page deliberately
does not — a national overview map does not justify a ~30 MB wasm download on the
narrative page. So this script derives a small, self-contained JSON from the mart
(single source of truth) and commits it, exactly like the simplified
`boundaries/` files are derived and committed.

Format (compact, not GeoJSON — plain GeoJSON is ~8 MB of structural overhead for
83 k points; this is ~2 MB):

    {
      "pts":  [[lon, lat, flags], ...],       // one entry per cooperative
      "meta": [[idx, name, province], ...],   // details ONLY for flagged points
      "counts": { "all": 83342, "isolated": 174, "roadless": 5133, "impossible": 19 }
    }

`flags` is a bitmask: 1 = isolated (report 03, nobody within 5 km), 2 = roadless
(report 05/08, no made road within ~5 km), 4 = impossible (report 08,
coordinate_suspect). Names/provinces are only attached to flagged points — those
are the ones a popup is useful for; the 78 k unflagged dots just fill the map.
Coordinates are rounded to 4 decimals (~11 m), plenty for a national map.

Usage:
  python scripts/build_story_points.py
"""

import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "web" / "kopdes_story_points.json"

con = duckdb.connect()
rows = con.execute(
    """
    SELECT
      cooperative_id,
      cooperative,
      province,
      round(longitude, 4) AS lon,
      round(latitude, 4)  AS lat,
      (remoteness_band = 'nobody within 5km') AS isolated,
      (km_non_track IS NULL)                  AS roadless,
      coordinate_suspect                      AS impossible
    FROM read_parquet('data/web/kopdes_points.parquet')
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """
).fetchall()

pts = []
meta = []
counts = {"all": 0, "isolated": 0, "roadless": 0, "impossible": 0}
for idx, (cid, name, province, lon, lat, iso, road, imp) in enumerate(rows):
    flags = (1 if iso else 0) | (2 if road else 0) | (4 if imp else 0)
    counts["all"] += 1
    if iso:
        counts["isolated"] += 1
    if road:
        counts["roadless"] += 1
    if imp:
        counts["impossible"] += 1
    pts.append([lon, lat, flags])
    if flags:
        meta.append([idx, name, province])

data = {
    "built": "2026-08-13",
    "counts": counts,
    "pts": pts,
    "meta": meta,
}
OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

print(f"wrote {OUT.relative_to(ROOT)}  {OUT.stat().st_size / 1e6:.2f} MB  {counts}  flagged={len(meta)}")
