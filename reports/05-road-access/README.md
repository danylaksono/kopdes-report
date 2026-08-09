# 05 — Road access: how far is each KDMP from a road?

**Run**: `python reports/05-road-access/run.py` · No network · **Last run**: 2026-08-09
**Source**: `data/osm/indonesia_roads.gpkg` (4,494,742 LineStrings) + `kopdes_locations.csv`

## Method — H3 line rasterisation instead of a spatial index

Nearest-neighbour search from 83k points against 4.5M LineStrings would normally
mean an R-tree over ~85M vertices. Instead the network is rasterised into H3
cells once and proximity becomes ring arithmetic on integer cell ids:

1. read the GeoPackage in chunks of 200k features
2. **densify** each LineString to ≤55 m segments (`shapely.segmentize`) — an r10
   cell is only ~76 m across, so a straight 500 m segment with two vertices
   would otherwise leave a false gap of unmarked cells in the middle
3. H3-index every vertex at r10 **in DuckDB** (vectorised C++, not a Python loop
   over 85M points)
4. keep the distinct cells

| | |
|---|---|
| Input | 4,494,742 LineStrings, 1.67 GB GPKG |
| Output | **9,051,169 distinct H3 r10 cells** (7,760,070 with a non-track road) |
| Cached index | `data/osm/road_cells_h3r10.parquet`, **34 MB** |
| Build time | **129 s**, once |

Distance then comes from a staged outward ring search: grow the H3 disk one
shell at a time and drop cooperatives as they resolve. Most resolve at k ≤ 2, so
only the genuinely remote ones pay for large disks — a flat `grid_disk(38)` over
83k points would be 4.5 billion rows; this runs in ~12 s.

`track` is reported separately from made roads throughout. A track is evidence
of *some* access; it is not a road you drive a delivery van down, and merging
the two would flatter the result.

## Finding 1 — 6.2% of KDMP have no made road within ~5 km

[`road_access_bands.csv`](road_access_bands.csv)

| Distance to nearest non-track road | Cooperatives | Share |
|---|---|---|
| on a road cell (<70 m) | 31,483 | 37.8% |
| < ~260 m | 21,438 | 25.7% |
| < ~530 m | 7,481 | 9.0% |
| < ~1 km | 6,942 | 8.3% |
| < ~2 km | 5,358 | 6.4% |
| < ~5 km | 5,507 | 6.6% |
| **> ~5 km or none found** | **5,133** | **6.2%** |

Two sharper cuts of the same data:

- **4,321 cooperatives have no road of *any* kind — not even a track — within
  ~5 km.**
- **812 have a track but no made road** within ~5 km. Reachable on foot or by
  motorbike in dry weather; not by a supply vehicle.

## Finding 2 — two independent datasets agree, which is the strongest evidence here

Road distance (crowdsourced OSM) and population (Kontur, from satellite imagery
and building footprints) are derived by completely different methods. They
converge:

| | Zero population in own cell | Has population |
|---|---|---|
| **No made road within 5 km** | **4,484** | 649 |
| Road within 5 km | 13,320 | 64,889 |

**87.4% of the no-road cooperatives also sit in a cell with zero recorded
population**, against a 21.4% baseline. Median population within ~5 km:

| | Median pop within ~5 km |
|---|---|
| No made road within 5 km | **1,723** |
| All others | **87,991** |

A 51× difference. These are not scattered geocoding errors — they are a
coherent set of cooperatives in genuinely empty, roadless places.

## Finding 3 — the geography is exactly what the critique predicts

[`road_access_by_province.csv`](road_access_by_province.csv) — share more than
~1 km from a made road, or with none found:

| Province | Cooperatives | % far from road |
|---|---|---|
| Papua Selatan | 628 | **71.3%** |
| Papua Tengah | 1,200 | 64.8% |
| Papua Barat Daya | 1,024 | 62.7% |
| Papua Pegunungan | 2,366 | 62.1% |
| Kalimantan Utara | 411 | 57.7% |
| Maluku | 1,236 | 56.1% |
| … | | |
| Jawa Timur | 8,494 | 1.7% |
| Jawa Barat | 5,968 | 1.7% |
| DKI Jakarta | 268 | 1.1% |
| Jawa Tengah | 8,524 | 1.0% |
| DI Yogyakarta | 438 | **0.0%** |

## Caveats — read before citing

- **OSM absence is not road absence.** OSM road coverage in Indonesia is good in
  Java and thinner in the Papua interior, which is precisely where the finding
  concentrates. The right claim is "no road **mapped in OSM** within 5 km",
  and every figure here is best read as an **upper bound on accessibility**.
- **The convergence in Finding 2 is supportive, not conclusive.** OSM and Kontur
  are methodologically independent but their biases may point the same way —
  both under-represent remote areas. Two sources being wrong in the same
  direction looks exactly like two sources agreeing.
- **Straight-line, not travel distance.** Ring distance is Euclidean on the H3
  grid; a river or ridge between the point and the road is invisible. Genuine
  accessibility needs routing, which is worth standing up only for the case
  studies (see [04](../04-siting-screen/)).
- **Ring distance is a band, not a metric.** Adjacent r10 cell centres are
  ~132 m apart, so `k × 0.132 km` is approximate and degrades slightly with
  latitude. Quote the bands, not `km_non_track` to three decimals.
- The OSM extract is a Geofabrik snapshot from 2026-08-07; OSM changes daily.

## Outputs

| File | Contents |
|---|---|
| [`road_access_bands.csv`](road_access_bands.csv) | national distribution |
| [`road_access_by_province.csv`](road_access_by_province.csv) | per-province far-from-road share |
| `kopdes_road_access.csv` | per-cooperative, joins to [03](../03-population-coverage/) on `cooperative_id` (gitignored, ~10 MB, rebuilds in seconds once the index is cached) |
