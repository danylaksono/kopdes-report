# 19 — Land cover: what is every KDMP on?

**Run**: `python reports/19-land-cover/run.py` · Reuses 04's cloud-raster
sampler over all coordinates · **Last run**: 2026-08-13 (on the 08-13 snapshot:
`$env:KOPDES_RAW='data/snapshots/2026-08-13'` before running)
**Source**: ESA WorldCover 10 m v200 (2021), sampled over HTTP
**Output**: [`kopdes_landcover.csv`](kopdes_landcover.csv) (83,379 rows)

## Why this exists

04 classified only its 2,500-candidate shortlist; the other ~81k coordinates
were never touched, so the app had no per-row land-cover value for everyone
else. This report runs the identical sampler at every cooperative coordinate,
so the directory table can show a "Penutup Lahan" class per row instead of a
shortlist flag.

OSM landuse polygons (07) are not a substitute for the column: OSM draws a
small fraction of rural Indonesia, and a miss there is no evidence (the same
asymmetry rule as 07). A 10 m satellite classification covers every point. The
price is a 2021 snapshot read at a single pixel.

## Method

Identical to 04's Stage B, reused as-is (`load_04_sampler`). WorldCover tiles
are 3°×3° on open S3; each tile is opened once and every point inside it is
sampled in memory. 68 tiles covered all 83,379 coordinates; every one
resolved.

## Results

| Land cover at the coordinate | Cooperatives | Share |
| ---------------------------- | ------------ | ----- |
| Tree cover                   | 50,848       | 61.0% |
| Built-up                     | 14,600       | 17.5% |
| Cropland                     | 10,529       | 12.6% |
| Grassland                    | 5,591        | 6.7%  |
| Water                        | 690          | 0.8%  |
| Mangrove                     | 400          | 0.5%  |
| Herbaceous wetland           | 363          | 0.4%  |
| Bare / sparse                | 208          | 0.2%  |
| Shrubland                    | 150          | 0.2%  |

**Read the numbers with the grain of the data.** ~61% of recorded coordinates
fall on a tree-cover pixel. That is the classification at the _coordinate_,
not a statement that cooperatives stand in forest: most coordinates are desa
centres, and a 10 m pixel around a settlement is frequently classified as tree
cover (2021). The caveat runs both ways, a "Built-up" pixel is likewise not
proof of a building.

## Reconciliation

04 sampled the same raster at the same coordinates for its 2,500-row
shortlist. This run agrees on **100.0%**.

## Caveats

- **2021 snapshot.** The raster is ESA WorldCover v200 from 2021, five years
  before these coordinates were recorded. Land use changes.
- **One pixel, not a building.** The class is the 10 m pixel under the
  recorded coordinate, not the cooperative's footprint. It corroborates a
  claim; it does not by itself place a building on that land.
- **Coordinate quality.** Every coordinate in the 08-13 snapshot resolves
  (all 83,379), but a resolved coordinate is not a verified one; a wrong
  coordinate gets a wrong class (08). The 08-05 baseline had ~26 unresolvable
  points; that snapshot is not what the mart ships.
- **Cropland is the actionable tail.** 10,520 coordinates classify as
  cropland, the raster signal behind the "dibangun di tengah sawah" claim.
  Cross it with 07's OSM farmland funnel for the verified set.
