# 20 — Terrain: how high, and how broken, is the ground under every KDMP?

**Reproduce**: `KOPDES_RAW=data/snapshots/2026-08-13 python reports/20-terrain/run.py` ·
Samples cloud rasters over HTTP · **Last run**: 2026-08-15
**Source**: Copernicus GLO-30 DEM COGs on open S3 + `kopdes_locations.csv` from the
**2026-08-13** snapshot. Hashes in [`_source.json`](_source.json).

## Why this report exists

[04](../04-siting-screen/) sampled the DEM for its **2,500-candidate shortlist
only**, so `elevation_m` and `relief_200m_m` were populated for 3% of the
registry. Every terrain sentence the site could write was therefore stuck in the
form _"of the 2,500 most remote, 1,008 are on steep ground"_ — a statistic about
a shortlist we had chosen, not about the programme. No table column and no map
filter could use a field that is 97% null.

[19](../19-land-cover/) had already closed exactly this gap for land cover by
reusing 04's sampler over every coordinate. This report does the same for the
DEM. It is the same machinery, pointed at the other raster.

**All 83,379 coordinates resolved (100%).** Reconciling against 04's shortlist,
where both sampled the same raster at the same points, **98.2% of 2,500 agree on
elevation to within 0.5 m**; the remainder are points whose coordinates the
ministry corrected between the two runs.

## What `relief_200m_m` is, and is not

This is the caveat that governs every number below, and it is 04's caveat
repeated because it kept getting lost downstream.

`relief_200m_m` is **max minus min elevation over a 7×7 window of 30 m DEM**,
i.e. the total height range within roughly 200 m of the point. It is a **relief
proxy, not a slope**:

- it has no direction, and no gradient
- it cannot distinguish a uniform incline from a flat shelf with one cliff at
  its edge
- a point at the foot of a hill scores the same as a point on the hill

The threshold for `flag_steep` is `> 60 m`, kept identical to 04 so the two
reports remain comparable. **The supportable wording is "ground that rises or
falls more than 60 m within about 200 m", never "a steep slope" and never a
gradient in degrees.** Elevation is the more robust of the two fields: one pixel
of a 30 m DEM is a good estimate of height and a poor estimate of steepness.

## Finding 1 — the national picture

[`terrain_bands.csv`](terrain_bands.csv)

**Median elevation 67 m. Median relief 14 m.** Most of the programme is on flat,
low ground, which is what a village-level rollout in Indonesia should look like.

| Elevation                | Cooperatives | Share      |
| ------------------------ | ------------ | ---------- |
| 0–50 m (coastal plain)   | 37,447       | **44.9%**  |
| 50–200 m (lowland)       | 19,236       | 23.1%      |
| 200–500 m (hills)        | 11,193       | 13.4%      |
| 500–1,000 m (highland)   | 8,908        | 10.7%      |
| 1,000–2,000 m (mountain) | 5,090        | 6.1%       |
| above 2,000 m            | **1,505**    | 1.8%       |

| Relief within ~200 m | Cooperatives | Share     |
| -------------------- | ------------ | --------- |
| < 10 m (flat)        | 32,145       | **38.6%** |
| 10–30 m (undulating) | 26,651       | 32.0%     |
| 30–60 m (rolling)    | 12,258       | 14.7%     |
| 60–150 m             | 11,285       | 13.5%     |
| > 150 m              | 1,040        | 1.2%      |

**12,325 cooperatives (14.8%) sit on ground with more than 60 m of relief within
~200 m.** That is the first time this can be said nationally rather than about a
shortlist.

## Finding 2 — the shortlist was not representative, and that is the point

04's top 2,500 are **2.7× more likely to be on broken ground** than the registry
as a whole: 40.3% against 14.8%. That is a check on 04's screen rather than a
finding about the programme — the screen ranks by isolation, and isolation and
terrain correlate in Indonesia, so it should over-select rough ground. It does.

It also means the old figure could never have been generalised. Anyone reading
"1,008 di lereng curam" without the "dari 2.500 paling terpencil" qualifier
would have been reading a number 2.7× too pessimistic.

## Finding 3 — terrain is the eastern-Indonesia story again

[`terrain_by_island.csv`](terrain_by_island.csv)

| Island        | Cooperatives | Median elevation | Median relief | On >60 m relief |
| ------------- | ------------ | ---------------- | ------------- | --------------- |
| **Papua**     | 7,062        | **533 m**        | **51.7 m**    | **44.7%**       |
| Nusa Tenggara | 5,342        | 260 m            | 33.4 m        | 27.9%           |
| Maluku        | 2,427        | 79 m             | 31.1 m        | 27.4%           |
| Sulawesi      | 10,554       | 66 m             | 20.4 m        | 23.3%           |
| Sumatra       | 25,587       | 42 m             | 12.5 m        | 10.4%           |
| Java          | 25,247       | 91 m             | 10.5 m        | 6.1%            |
| Kalimantan    | 7,160        | 13 m             | 8.3 m         | 4.7%            |

Nearly half of Papua's cooperatives are on broken ground, against one in
sixteen in Java. This is the same gradient as every other tail measure
([14](../14-island-comparison/)), from a completely independent source: a global
elevation model that knows nothing about SIMKOPDES.

## What this cannot settle

- **A coordinate on a mountainside may never have been a building.** The same
  ambiguity as [04](../04-siting-screen/) and [07](../07-landuse-polygons/).
  Terrain describes the ground under a recorded point, not under a building.
- **Relief is not slope**, and no number here should be restated as a gradient.
- **30 m resolution smooths real terrain.** A cooperative on a 20 m ledge above a
  river reads as moderate relief.
- **Steepness is not inaccessibility.** A terraced hillside in Java is steep and
  perfectly reachable; the accessibility question is [05](../05-road-access/)'s.
- Elevation is sampled at a **single pixel**, so a coordinate a few tens of
  metres out can land on the wrong side of a break in slope. The band summaries
  absorb this; a single row's elevation should not be quoted to the metre.

## Outputs

| File                                             | Contents                                                     |
| ------------------------------------------------ | ------------------------------------------------------------ |
| [`terrain_bands.csv`](terrain_bands.csv)         | national distribution, elevation and relief                  |
| [`terrain_by_island.csv`](terrain_by_island.csv) | the geography                                                |
| `kopdes_terrain.csv`                             | per-cooperative (gitignored, 83,379 rows, needs a raster run) |
