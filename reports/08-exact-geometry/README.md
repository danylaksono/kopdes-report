# 08 — Exact geometry: real distances, and coordinates that cannot be real

**Run**: `python reports/08-exact-geometry/run.py` · No network · **Last run**: 2026-08-13 (on 08-13 coordinates)
**Source**: `data/osm/indonesia_roads.gpkg`, `indonesia_minimarkets.gpkg`, 05's cached
H3 index, `kopdes_locations.csv`

[05](../05-road-access/) and [06](../06-minimarket-proximity/) measure distance
by growing H3 rings. That is the right way to sort 83,342 cooperatives into
bands in seconds, and the wrong thing to put in a sentence about a named
village: ring distance is quantised to ~132 m, carries directional error, and
stops at whatever `k` the search gave up on. A narrative needs _"the nearest road
is 9.7 km away"_, not _"in the >5 km band"_.

So: **H3 to rank, exact geometry to report.** Everything below is geodesic
(`pyproj.Geod`, WGS84) from the point to the nearest point on the real geometry.
The bounding boxes used to fetch local geometry are computed in degrees and are
deliberately generous — they are a _fetch window_, never a measurement.

## Finding 1 — 19 cooperatives are not in Indonesia, and 18 are a sign error

This was not the question the report set out to answer. It fell out of part B:
the maximum distance to a minimarket came back as 9,349 km, which is not a
number any Indonesian village can produce.

19 cooperatives sit outside Indonesia's envelope entirely. For each, compare the
distance to its own claimed province centroid **as recorded** against the
distance **with the latitude sign flipped**:

|                       | Median distance to its claimed province centroid |
| --------------------- | ------------------------------------------------ |
| As recorded           | **1,631 km**                                     |
| With latitude negated | **96 km**                                        |

All 18 move from the far side of the planet to inside their own province.
`-7.75°` was entered as `7.75°`; Java is south of the equator. The 19th
(KDMP KAMPUNG WOMBRISAUW, Papua) reads `85.05°N, −180.0°` and is simply
garbage.

> **Update 2026-08-13:** the ministry has since corrected these coordinates.
> A live pull shows **all 19 now inside Indonesia** — the 18 sign errors are
> flipped, the WOMBRISAUW garbage case re-placed at (−0.806, 135.740) — plus
> **10 further sign errors we had not flagged** (29 sign flips total) and 373
> cooperatives whose coordinates moved at all. This finding is therefore a
> statement about the 2026-08-05 snapshot, not the current registry. Re-running
> 04/05/06 against `data/snapshots/2026-08-13/` is required before these
> figures can be republished as current.

> **Correction, 2026-08-15 — the count is 20, and the fix landed on 08-09.**
> Two things were wrong with the paragraphs above, both found by testing the
> committed 08-05 export against a plain Indonesia bounding box rather than
> against an implausible retail distance:
>
> - **20 points, not 19.** The detection here started from a 9,349 km maximum
>   distance to a minimarket, which finds a coordinate thrown to the far side of
>   the planet but not one moved a few hundred kilometres into the South China
>   Sea. KDMP CURUGKEMBAR (Banten) sits at 6.35°N, outside the country and well
>   inside what a retail-distance test treats as ordinary. So this finding is
>   19 of 20, and the sign-flip subtotal is 19, not 18.
> - **They were corrected by 9 August, not "between 10 and 13 August".** All 20
>   are already inside Indonesia in the 2026-08-09 snapshot.
>
> `suspect_coordinates.csv` now has **zero rows**, correctly: it lists what is
> wrong in the snapshot `run.py` was pointed at, and nothing is. That is also
> how the evidence for a published claim disappeared. The historical record now
> lives in [`corrected_coordinates_2026-08.csv`](corrected_coordinates_2026-08.csv),
> written by [`make_corrections_record.py`](make_corrections_record.py), which
> `run.py` never touches: 20 rows, before and after coordinates, the diagnosis,
> and the first snapshot in which each was fixed.

### This corrects two earlier reports

A point in the Java Sea has no population and no roads, so it maxes out exactly
the screens designed to find isolation. **All 19 appear in 04's candidate list,
and all 19 are in 05's roadless set.**

| Published figure                              | Was   | Corrected |
| --------------------------------------------- | ----- | --------- |
| 04 — candidates carrying `Terverifikasi` land | 401   | **388**   |
| 04 — candidates on water/mangrove/wetland     | 69    | **67**    |
| 05 — no made road within ~5 km                | 5,133 | **5,114** |
| 05 — no road of any kind within ~5 km         | 4,321 | **4,302** |

17 of the 19 also explain most of 04's 26 "unresolved" land-cover rows: the
sampler found no ESA WorldCover tile because there is no land there.

This is [04's](../04-siting-screen/) own stated ambiguity — _badly sited or badly
geocoded_ — resolved for 19 named cases, in favour of geocoding. The effect on
04's headline is small (0.76% of its shortlist) and its argument survives. But
one of the two corrected water cases, **KDMP KARANGREJO (Kec. Gumukmas,
Jember)**, is printed in 04's README as an example of a cooperative sitting on
water. It is not. It is a cooperative with a mistyped latitude.

## Finding 2 — how far the roadless ones really are

[`exact_road_distance_bands.csv`](exact_road_distance_bands.csv) ·
[`exact_road_distance_far_set.csv`](exact_road_distance_far_set.csv)

05 could only say that 5,133 cooperatives have no made road within ~5 km,
because that is where its ring search stopped. Now they have numbers — the
r10 road-cell index rolled up to r6 gives each point a bound on how far its
nearest road can be, and that bound sizes one bbox-filtered read of the
GeoPackage. 5,114 of 5,133 resolved (the 19 failures are Finding 1's), in **51
seconds**.

| Exact distance to the nearest made road | Cooperatives |
| --------------------------------------- | ------------ |
| 5–10 km                                 | 2,466        |
| 10–25 km                                | 1,870        |
| 25–50 km                                | 523          |
| 50–100 km                               | 57           |
| **over 100 km**                         | **7**        |

**Median 9.7 km. 90th percentile 26.4 km. Maximum 185.9 km.**

"No road within 5 km" was an understatement produced by where the search
stopped. Half of this group is more than 9.7 km from the nearest made road, and
587 of them are more than 25 km away.

## Finding 3 — every cooperative now has a real retail distance

[`exact_minimarket_bands.csv`](exact_minimarket_bands.csv)

06's ring search capped at ~5 km, so 66,846 cooperatives had no value at all.
Minimarkets are only 7,617 points once 06's tiering is applied, so there is no
reason to approximate: one STRtree gives exact distances for all 83,342.

| Distance to nearest tier-1 minimarket | Cooperatives | Share      |
| ------------------------------------- | ------------ | ---------- |
| ≤ 100 m                               | 154          | 0.18%      |
| ≤ 500 m                               | 1,890        | 2.27%      |
| ≤ 1 km                                | 4,074        | 4.89%      |
| ≤ 2 km                                | 7,946        | 9.54%      |
| ≤ 5 km                                | 17,607       | 21.13%     |
| **beyond 10 km**                      | **53,737**   | **64.49%** |

Median 17.3 km. **This uses 06's own tier-1 definition** — 7,617 convenience/
minimarket POIs, not all 10,580 shops in the file. Measuring against everything
would have produced numbers that looked like a correction to 06 while answering
a different question.

## Finding 4 — the ring approximation, audited

[`ring_vs_exact_agreement.csv`](ring_vs_exact_agreement.csv) ·
[`ring_vs_exact_sample.csv`](ring_vs_exact_sample.csv)

Both earlier reports can now be checked against the truth rather than trusted.

|                                            | Points | Median abs error | p90 abs error | Within one cell width (132 m) |
| ------------------------------------------ | ------ | ---------------- | ------------- | ----------------------------- |
| **05 roads** (random band-resolved sample) | 800    | **34 m**         | 114 m         | **92.0%**                     |
| **06 minimarkets** (all resolved)          | 16,496 | 175 m            | 528 m         | 40.6%                         |

**05's bands hold up.** A median error of 34 m against a median true distance of
118 m, with 92% inside one cell width, is as good as the method could be. Cite
05 as published.

**06's distances are biased, and the bias has a direction.** The median signed
error is **+169 m** — ring distance _overstates_ how far the nearest minimarket
is, because error accumulates with `k` and retail is sparse enough to need large
`k`. That means 06's absolute proximity counts were **conservative**: it
undercounted how many KDMP sit close to a minimarket.

It does **not** overturn 06's finding. Its headline is a _difference_ — KDMP
versus a matched null model — and both arms were measured with the same ring
method at the same distances, so the bias very largely cancels. The absolute
band counts in 06 should be replaced by Finding 3; the +9.6 pt excess stands.

## Caveats

- **Precision has a floor, and it is not this script's arithmetic.** OSM road
  geometry is good to roughly 5–15 m, worse for rural tracks. Distances here are
  rounded to 1 m and should be **quoted to the nearest 100 m**. Decimals of a
  metre are theatre.
- **Straight-line, not travel distance.** A river or ridge between the point and
  the road is still invisible. 186 km in a straight line across the Papuan
  interior is not a journey anyone makes.
- **OSM absence is still not absence.** Every distance here is an upper bound on
  accessibility and a lower bound on retail proximity, exactly as in 05 and 06.
- **Finding 1 is a floor, not a count.** 19 is how many coordinates are so wrong
  they left the country. A latitude mistyped within Indonesia — or a desa
  centroid standing in for a building, as [07](../07-landuse-polygons/) worries —
  is invisible to this test.
- The suspect coordinates are **not** corrected in place anywhere. `data/raw/`
  is the 2026-08-05 baseline and is never edited; consumers should filter on
  `coordinate_suspect` in the mart.

## Outputs

| File                                                                 | Contents                                        |
| -------------------------------------------------------------------- | ----------------------------------------------- |
| [`suspect_coordinates.csv`](suspect_coordinates.csv)                 | live: points outside Indonesia in the snapshot `run.py` read (now 0) |
| [`corrected_coordinates_2026-08.csv`](corrected_coordinates_2026-08.csv) | historical: the 20 bad 08-05 coordinates, before/after, never overwritten |
| [`exact_road_distance_bands.csv`](exact_road_distance_bands.csv)     | the roadless set, resolved into real distances  |
| [`exact_road_distance_far_set.csv`](exact_road_distance_far_set.csv) | per-cooperative, 5,133 rows                     |
| [`exact_minimarket_bands.csv`](exact_minimarket_bands.csv)           | national distribution, exact                    |
| [`ring_vs_exact_agreement.csv`](ring_vs_exact_agreement.csv)         | the audit of 05 and 06                          |
| [`ring_vs_exact_sample.csv`](ring_vs_exact_sample.csv)               | the 800 re-measured road points                 |
| `exact_minimarket_distance.csv`                                      | per-cooperative, all 83,342 (gitignored, ~7 MB) |
