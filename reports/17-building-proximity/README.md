# 17 — Building proximity: how far is each KDMP from the nearest house?

**Run**: `python reports/17-building-proximity/run.py` · No network · **Last run**: 2026-08-14 (on 08-13 coordinates)
**Source**: `data/osm/building_cells_vida_h3r10.parquet` (built by `python scripts/extract_buildings_vida.py`
from VIDA's **137,070,577 Indonesian building footprints** → 10.48M distinct H3 r10 cells) + `kopdes_locations.csv`

> **This report was corrected on 2026-08-14 and its headline reversed.** The
> published version said 62.6% of cooperatives had no mapped building within
> ~5 km. The true figure is **1.19%**. Two independent causes, quantified
> separately in "The correction" below: a band-assignment bug in this script,
> and an OSM building layer too sparse to support the claim. Any external
> citation of the 62.6% figure should be treated as withdrawn.

## Why this report exists

The placement critique has two halves. "You can't get there" we measure with
roads (05). "There's nobody there" we approximate with a population grid (03) —
but a 400 m population cell is an aggregate, not a house. A field check finds
cooperatives with **no building footprint anywhere near them**, and neither the
population grid nor the road measure captures that directly. This report
measures the literal thing: **distance to the nearest mapped building**, using
an independent source rather than the satellite-derived grid.

## The measure

`scripts/extract_buildings_vida.py` reduces the building layer to the
**distinct H3 r10 cells that contain at least one building centroid**. This
report then runs the same staged ring search as 05: for each cooperative, expand
H3 rings outward until one hits a building cell. Ring _k_ converts to distance
the same way as roads — adjacent r10 cell centres are ~132 m apart — so the
bands below are **identical to report 05's**, and "far from a road" and "no
house nearby" are directly comparable at the same cell scale.

### Which building layer

| Layer                             | Footprints | r10 cells  | Source                                                                      |
| --------------------------------- | ---------- | ---------- | --------------------------------------------------------------------------- |
| OSM only (used until 2026-08-14)  | ~43.9M     | 3.59M      | Geofabrik Indonesia PBF                                                     |
| **VIDA Google + Microsoft + OSM** | **137.1M** | **10.48M** | [source.coop](https://source.coop/vida/google-microsoft-osm-open-buildings) |

VIDA's combined layer carries 3.1× the footprints and 2.9× the r10 cells,
and the ML-derived footprints are dense exactly where OSM is thin: rural
Indonesia. Of the 10.48M cells, 85.8% are touched by a Google footprint, 36.1%
by Microsoft and 10.0% by OSM. `--buildings osm` still runs the old layer, which
is how the comparison below was produced.

Licence: CC-BY-4.0 for the combined product, with the OSM-derived rows carrying
ODbL. `bf_source` is preserved per cell for that reason.

## The correction

Both causes were found on 2026-08-14 while building `/periksa/`, which
recomputes this measure in the browser and disagreed with the published table.

**Cause 1 — a band-assignment bug in this script.** The ring search returns
whatever ring index it stopped at, any integer 0–38, while `BANDS` names only
six of them. The band was assigned with `hits.k.map(dict(BANDS))`, so every
cooperative whose nearest building sat on an off-key ring (1, 3, 5, 6, 7, 9–14,
16–37) produced `NaN` and was swept into "none found" by the `.fillna()` beneath
it. Report 05 always used a threshold walk and was never affected; only this
report used the dict. It is now a threshold function, and `run.py` carries a
comment saying why it must stay one.

**Cause 2 — the OSM layer's rural undercount**, which Finding 2 of the published
version had already identified as a lower bound of unknown looseness. It was
looser than anyone assumed.

| Version                             | on a building cell | no mapped building within ~5 km |
| ----------------------------------- | ------------------ | ------------------------------- |
| Published 2026-08-13 (buggy, OSM)   | 23.2%              | **62.6%**                       |
| Bug fixed, same OSM layer           | 23.2%              | 14.88%                          |
| Bug fixed + VIDA layer (**current**)| **44.36%**         | **1.19%**                       |

The bug accounted for roughly three quarters of the error and the data source
for most of the rest.

## Finding 1 — 44% of cooperatives sit on a mapped building cell

[`building_access_bands.csv`](building_access_bands.csv) ·
[`building_access_by_province.csv`](building_access_by_province.csv)

| Distance to nearest building | Cooperatives | Share     |
| ---------------------------- | ------------ | --------- |
| on a building cell (<70 m)   | 36,985       | 44.36%    |
| < ~260 m                     | 25,699       | 30.82%    |
| < ~530 m                     | 7,555        | 9.06%     |
| < ~1 km                      | 5,745        | 6.89%     |
| < ~2 km                      | 3,587        | 4.30%     |
| < ~5 km                      | 2,817        | 3.38%     |
| **> ~5 km / none found**     | **991**      | **1.19%** |

Three quarters of cooperatives (75.2%) have a mapped building within ~260 m.
**The "no houses around" claim is not supported at national scale by this
measure.** What remains is a tail, and the tail is where this report is now
useful.

## Finding 2 — the tail is small, and it is corroborated

[`building_overlap.csv`](building_overlap.csv)

**7,395 cooperatives (8.87%) have no mapped building within ~1 km.** Of those,
**7,263 (98.2%) still have people nearby** per the Kontur grid — the two sources
still disagree in most of the tail, which is the expected signature of residual
incompleteness even in a 137M-footprint layer.

The set where they **agree** is the finding:

| Case                                                  | Cooperatives |
| ----------------------------------------------------- | ------------ |
| no mapped building within ~1 km                       | 7,395        |
| ... and isolated (Kontur: nobody within 5 km)         | **132**      |
| ... and isolated **and** roadless                     | **128**      |
| no mapped building within ~5 km                       | 991          |
| ... and roadless                                      | 771          |

**128 cooperatives have no mapped house within 1 km, nobody within 5 km per an
independent satellite-derived population grid, and no made road within 5 km.**
Three independent sources agreeing on the same ~130 points is a far stronger
claim than the withdrawn 62.6% ever was, and it is the number this report should
be cited for.

## Finding 3 — the paddy-field connection has effectively disappeared

The published version reported 1,221 cooperatives with no mapped building within
~5 km sitting inside a farmland polygon (07). With the corrected bands and the
VIDA layer that intersection is **0**, and the isolated-and-in-farmland set is
also 0. The earlier figure was an artefact of the same two causes. There is no
"cooperative in an empty paddy field" pattern at scale in this data.

## Caveats — read these before quoting anything

- **Building coverage is still incomplete.** "No building within X" remains a
  **lower bound**: it means "no _mapped_ house", never "no house". ML-derived
  footprints miss buildings too, particularly under canopy and for small
  informal structures. Write "no mapped house", always.
- Building proximity is a _distance band_ (k × 132 m), not an exact metric —
  same as 05's road bands.
- A building is one footprint reduced to its bounding-box centroid. Large
  buildings are represented by one point; for "is there a house within 500 m"
  this is immaterial.
- **The layer is not a single vintage.** VIDA combines Google Open Buildings,
  Microsoft Building Footprints and OSM, each with its own capture date. Read a
  hit as "a building was mapped here at some point", not "a building stands here
  today".
- The `building_band` null in the mart means "no mapped building within ~5 km",
  not "unknown" (see `mart_manifest.json`). `km_to_building` carries the same
  semantics.

## Outputs

| File                                                                 | Contents                                                   |
| -------------------------------------------------------------------- | ---------------------------------------------------------- |
| [`building_access_bands.csv`](building_access_bands.csv)             | per-band counts and shares                                 |
| [`building_access_by_province.csv`](building_access_by_province.csv) | per-province share with no building within ~5 km           |
| [`kopdes_building_access.csv`](kopdes_building_access.csv)           | per-cooperative `building_band` + `km_to_building`         |
| [`building_overlap.csv`](building_overlap.csv)                       | no-house cases × roadless / isolated / farmland            |
