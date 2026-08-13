# 17 — Building proximity: how far is each KDMP from the nearest house?

**Run**: `python reports/17-building-proximity/run.py` · No network · **Last run**: 2026-08-13 (on 08-13 coordinates)
**Source**: `data/osm/building_cells_h3r10.parquet` (built by `python scripts/extract_buildings.py`
from the Indonesia PBF's **43.9M OSM building footprints** → 3.59M distinct H3 r10 cells) + `kopdes_locations.csv`

## Why this report exists

The placement critique has two halves. "You can't get there" we measure with
roads (05). "There's nobody there" we approximate with a population grid (03) —
but a 400 m population cell is an aggregate, not a house. A field check finds
cooperatives with **no building footprint anywhere near them**, and neither the
population grid nor the road measure captures that directly. This report
measures the literal thing: **distance to the nearest mapped building**, using
an independent source (crowd-mapped OSM footprints) rather than the
satellite-derived grid.

## The measure

`scripts/extract_buildings.py` reduces the PBF to the **distinct H3 r10 cells
that contain at least one building centroid** (one point per building way).
This report then runs the same staged ring search as 05: for each cooperative,
expand H3 rings outward until one hits a building cell. Ring _k_ converts to
distance the same way as roads — adjacent r10 cell centres are ~132 m apart —
so the bands below are **identical to report 05's**, and "far from a road" and
"no house nearby" are directly comparable at the same cell scale.

## Finding 1 — near-field: only 23% of cooperatives sit on a building cell

[`building_access_bands.csv`](building_access_bands.csv) ·
[`building_access_by_province.csv`](building_access_by_province.csv)

| Distance to nearest building | Cooperatives | Share |
|---|---|---|
| on a building cell (<70 m) | 19,372 | 23.2% |
| < ~260 m | 5,711 | 6.9% |
| < ~530 m | 3,129 | 3.8% |
| < ~1 km | 1,748 | 2.1% |
| < ~2 km | 921 | 1.1% |
| < ~5 km | 339 | 0.4% |
| **> ~5 km / none found** | **52,159** | **62.6%** |

Only a quarter of cooperatives sit on a mapped building; 62.6% have no mapped
building within ~5 km. **That headline must not be read as "no house".** See
Finding 2.

## Finding 2 — OSM rural coverage is too sparse to claim "no house" from absence

[`building_overlap.csv`](building_overlap.csv)

Of the **53,419** cooperatives with no mapped building within ~1 km,
**53,274 (99.7%) still have people nearby** per the satellite-derived Kontur
grid. The two sources disagree almost everywhere — the signature of an
incomplete OSM rural building layer, not a truly uninhabited landscape.

**Consequence:** write "no *mapped* house", never "no house". The population
grid (03) is the better "is anyone there" measure; OSM buildings are the better
*independent confirmation* of the tail. This is a lower bound, exactly like
roads (05).

## Finding 3 — the concordance: two independent sources agree on the tail

The 146 isolated cooperatives of 03 (nobody within 5 km per Kontur) are
confirmed by a completely different source: **145 of them also have no OSM
building within 1 km**, and 140 of those are roadless. Two independent methods
(satellite building footprints vs crowd-mapped footprints) land on the same
~145-point tail. That set — no house by both measures, mostly without a road —
is the strongest "middle of nowhere" claim in the dataset, and it is now
triple-confirmed (population, buildings, roads).

## Finding 4 — the paddy-field connection

**1,221 cooperatives with no mapped building within ~5 km are recorded inside a
farmland polygon** (07). A cooperative *in a paddy field and with no mapped
house nearby* is exactly the individual case a field check should target — and
the intersection with the confirmed-agricultural set (448, two independent maps)
is where the strongest cases live.

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
