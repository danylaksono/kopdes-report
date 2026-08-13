# 17 — Building proximity: how far is each KDMP from the nearest house?

**Run**: `python reports/17-building-proximity/run.py` · No network · **Last run**: 2026-08-13 (on 08-13 coordinates)
**Source**: `data/osm/building_cells_h3r10.parquet` (built by `python scripts/extract_buildings.py`
from the Indonesia PBF's ~44M OSM building footprints) + `kopdes_locations.csv`

## Why this report exists

The placement critique has two halves. "You can't get there" we measure with
roads (05). "There's nobody there" we approximate with a population grid (03) —
but a 400 m population cell is an aggregate, not a house. A field check finds
cooperatives with **no building footprint anywhere near them**, and neither the
population grid nor the road measure captures that directly. This report
measures the literal thing: **distance to the nearest mapped building**.

## The measure

`scripts/extract_buildings.py` reduces the PBF to the **distinct H3 r10 cells
that contain at least one building centroid** (one point per building way).
This report then runs the same staged ring search as 05: for each cooperative,
expand H3 rings outward until one hits a building cell. Ring _k_ converts to
distance the same way as roads — adjacent r10 cell centres are ~132 m apart —
so the bands below are **identical to report 05's**, and "far from a road" and
"no house nearby" are directly comparable at the same cell scale.

## Finding 1 — a tail of cooperatives with no house nearby

[`building_access_bands.csv`](building_access_bands.csv) ·
[`building_access_by_province.csv`](building_access_by_province.csv)

> Numbers filled on run: share with no building within ~500 m / ~1 km / ~5 km,
> per-province distribution, and the far tail.

## Finding 2 — the no-house tail overlaps the other tails

[`building_overlap.csv`](building_overlap.csv)

Cross-tab of "no mapped building within ~1 km / ~5 km" against the roadless set
(05), the isolated set (03) and the in-farmland set (07). The cases that are
_all three at once_ — no road, no house, recorded in a paddy field — are the
sharpest, most visual candidates in the whole dataset.

## Caveats — read these before quoting anything

- **OSM building coverage is incomplete in rural Indonesia.** "No building
  within X" is a **lower bound**: it means "no _mapped_ house", never "no
  house". The population grid (03) and the confirmed farmland set (07) are the
  independent checks that keep this honest. Write "no mapped house", always.
- Building proximity is a _distance band_ (k × 132 m), not an exact metric —
  same as 05's road bands.
- A building is a `building`-tagged OSM way reduced to one centroid. Large
  buildings (halls, factories) are represented by one point and may be
  under-represented; for the "is there a house within 500 m" question this is
  immaterial.
- The `building_band` null in the mart means "no mapped building within ~5 km",
  not "unknown" (see `mart_manifest.json`).

## Outputs

| File                                                                 | Contents                                         |
| -------------------------------------------------------------------- | ------------------------------------------------ |
| [`building_access_bands.csv`](building_access_bands.csv)             | per-band counts and shares                       |
| [`building_access_by_province.csv`](building_access_by_province.csv) | per-province share with no building within ~5 km |
| [`kopdes_building_access.csv`](kopdes_building_access.csv)           | per-cooperative `building_band`; feeds the mart  |
| [`building_overlap.csv`](building_overlap.csv)                       | no-house cases × roadless / isolated / farmland  |
