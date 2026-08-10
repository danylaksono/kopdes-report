# 07 — Land use: is the KDMP standing on a graveyard, or in a paddy field?

**Run**: `python reports/07-landuse-polygons/run.py` · Samples cloud rasters over
HTTP (`--skip-rasters` to go fully offline) · **Last run**: 2026-08-10
**Source**: `data/osm/indonesia-latest.osm.pbf` (Geofabrik, 2026-08-07) +
`kopdes_locations.csv`

> **Candidates, not findings** — the same rule as [04](../04-siting-screen/).
> Read [What this cannot settle](#what-this-cannot-settle) before citing any row.

## Why this screen exists

Two accusations in the public critique are invisible to every analysis we have
run so far:

- ***"dibangun di tanah kuburan"*** — built on burial ground. ESA WorldCover has
  no cemetery class at all, so [04](../04-siting-screen/) is structurally blind
  to it. OSM has the polygons.
- ***"dibangun di tengah sawah"*** — built in the middle of a paddy field. 04
  found **exactly one** cropland case in 2,500 candidates, and said so as a
  known limit: it ranks by *isolation*, and a shop in a paddy field sits right
  next to a village by construction. This screen has no isolation term, so it
  can see them.

Both verdicts came back — and they point in opposite directions.

## Method — point-in-polygon, and two ways to be wrong about distance

Different machinery from 04. These are vector polygons, not raster pixels.

1. **One pass over the 1.73 GB PBF**, assembling closed ways and multipolygon
   relations into areas, with the tag filter applied on the C++ side in both the
   area-candidate pass and the output stream. **258,224 features in 100 s** →
   `data/osm/indonesia_landuse.parquet` (50 MB, cached; rebuild with
   `--rebuild-index`). Iterating tags in a Python callback instead is the 92-minute
   mistake recorded in `AGENTS.md`.
2. **An STRtree per class.** `query(predicate="within")` answers "is this KDMP
   inside a cemetery?" for all 83,342 points at once.
3. **Distance in two steps.** The tree ranks candidates in degree space — near
   the equator that is within ~2% of isotropic, fine for *which* polygon is
   closest and useless as a published number. The winner is then re-measured
   **geodesically** (`pyproj.Geod`) against the actual nearest point on the
   geometry. Nothing is ever buffered in degrees: 0.01° is a different distance
   in Aceh than in Papua.

| Class | OSM features | Polygons | Points |
|---|---|---|---|
| `landuse=farmland` | 77,075 | 77,038 | 37 |
| `amenity=place_of_worship` | 89,339 | 66,023 | 23,316 |
| `place=village` | 76,973 | 1,128 | 75,845 |
| `landuse=cemetery` + `amenity=grave_yard` | 9,095 | 8,413 | 682 |
| `amenity=marketplace` | 5,742 | 4,270 | 1,472 |

## The comparator, without which none of this means anything

"2,206 cooperatives are inside farmland" is not a finding on its own. If village
institutions in general land inside mapped farmland at that rate, the number
describes how OSM draws Indonesia, not where KDMP were built.

**OSM's own `place=village` nodes** are the natural comparator: they are what
"the right spot for a village institution" looks like, placed by mappers with no
stake in this argument, at roughly the same national density (75,845 vs 83,342).
The identical screen runs over them.

[`null_comparison.csv`](null_comparison.csv)

| Inside a… | KDMP | OSM village nodes | Excess |
|---|---|---|---|
| farmland polygon | **2.647%** (2,206) | 1.097% (832) | **+1.55 pts — 2.4×** |
| cemetery polygon | 0.026% (22) | 0.022% (17) | +0.004 pts — **nil** |
| marketplace polygon | 0.019% (16) | 0.021% (16) | −0.002 pts — nil |

A second comparator — **10,580 mapped minimarkets**, sited by companies that care
only about footfall — is in the same file and looks far more dramatic (0.151%
against a province-reweighted KDMP rate of 3.399%, a 22× gap). **Do not quote
it.** Province-reweighting fixes the between-province confound and does nothing
about the one that matters: within any province, minimarkets are in towns and
KDMP are in desa. It belongs in the file as an upper bound, not in a sentence.

## Finding 1 — the paddy-field claim survives, with a nameable shortlist

[`farmland_funnel.csv`](farmland_funnel.csv) ·
[`farmland_candidates.csv`](farmland_candidates.csv)

Being inside a farmland polygon is not enough on its own, so the funnel strips
out everything that could be an artefact:

| Step | Cooperatives |
|---|---|
| inside a mapped farmland polygon | 2,206 |
| ≥ 100 m from the field edge (in it, not on the verge of it) | 1,023 |
| … and ≥ 100 people within 1.4 km (the ones 04 discards) | 1,023 |
| … and the polygon is not a coarsely-drawn whole plain | **536** |

That last step removed **487 of 1,023** — nearly half. Some contributors trace an
entire agricultural landscape as a single `landuse=farmland` way, settlements
included, and a point 3 km "deep" inside one of those is in a village, not a
field. Any polygon containing 2 or more OSM village nodes is dropped for that
reason. Without this check the headline number would have been twice as large
and wrong.

**Independent confirmation.** The OSM polygon is one person's tracing. ESA
WorldCover is a 10 m satellite classification produced with no knowledge of OSM.
Sampling all 536 candidate points (reusing 04's COG range-request sampler):

| Land cover at the point | Candidates |
|---|---|
| **Cropland** | **448 (83.6%)** |
| Tree cover | 50 |
| Grassland | 25 |
| Built-up | 7 |
| Water / wetland / shrub / mangrove | 6 |

**448 cooperatives are placed on agricultural land by two independent sources,
at least 100 m from the nearest edge of the field, in a desa with people living
around them.** 209 of them carry a land-asset status of `Terverifikasi` — the
land was officially signed off.

The geography is not where 04 looked at all: **Aceh (92), Jawa Tengah (60), Jawa
Timur (58)** lead the confirmed-and-roadside set, against 04's Papua-and-Maluku
concentration. These are two different phenomena, and only this screen sees the
second one.

### The ten deepest, confirmed by both sources, next to a mapped road

| Cooperative | District | Depth into field | Polygon | Land status |
|---|---|---|---|---|
| KDMP KARANGSEGAR PEBAYURAN | Jawa Barat, Kab. Bekasi | **1,067 m** | 28 km² | Sedang Diverifikasi |
| KDMP CERUKCUK | Banten, Kab. Serang | 1,027 m | 28 km² | Sedang Diverifikasi |
| KDMP BENA | NTT, Kab. Timor Tengah Selatan | 974 m | 14 km² | Sedang Diverifikasi |
| KDMP SUKAMURNI SUKAKARYA | Jawa Barat, Kab. Bekasi | 735 m | 17 km² | **Terverifikasi** |
| KDMP PILANGSARI JATITUJUH | Jawa Barat, Kab. Majalengka | 708 m | 117 km² | Sedang Diverifikasi |
| KDMP SUKAWANGI | Jawa Barat, Kab. Bekasi | 693 m | 17 km² | Tidak Ada Lahan |
| KDMP PASURUHAN | Jawa Tengah, Kab. Pati | 691 m | 14 km² | — |
| KDMP SAMBIREJO SARADAN | Jawa Timur, Kab. Madiun | 620 m | 4.6 km² | Dipertimbangkan |
| KDMP SRIKATON KAYEN | Jawa Tengah, Kab. Pati | 608 m | 14 km² | **Terverifikasi** |
| KDMP GROBOGAN | Jawa Timur, Kab. Madiun | 576 m | 2.3 km² | **Terverifikasi** |

Every row in [`farmland_candidates.csv`](farmland_candidates.csv) carries an
`imagery_url`.

## Finding 2 — the burial-ground claim does not hold up

[`cemetery_candidates.csv`](cemetery_candidates.csv)

**22 cooperatives out of 83,342 sit inside a mapped burial ground — a rate
statistically indistinguishable from where OSM puts its own village centres**
(0.026% against 0.022%; 22 cases against 17). And the 22 do not survive
inspection as a group:

- **Only 7 are more than 25 m inside**, and only 2 more than 100 m. The rest are
  boundary effects — a kelurahan office next to the wall of a cemetery.
- **16 of the 22 are in a *kota*, not a *kabupaten*.** These are large urban TPU
  polygons in Jakarta, Surabaya, Semarang, Bengkulu — dense places where a public
  cemetery is a city block and everything is next to everything.

| Cooperative | Burial ground | Depth | Land status |
|---|---|---|---|
| KDMP MARGAMULYA TELUKJAMBE BARAT | **San Diego Hills Cemetery** (Karawang) | **481 m** | **Terverifikasi** |
| KOP. KEL. SEMPER TIMUR | TPU Semper (Jakarta Utara) | 129 m | Sedang Diverifikasi |
| KOP. KEL. PANDAN KASTURI | Ambon War Cemetery | 82 m | Sedang Diverifikasi |
| KOP. KEL. SEMABUNG BARU | Pekuburan Sentosa (Pangkal Pinang) | 82 m | Sedang Diverifikasi |
| KDMP BARON | Makam Bong Cina Baron (Nganjuk) | 80 m | **Terverifikasi** |
| KOP. KEL. PUTAT JAYA | TPU Putat Jaya (Surabaya) | 65 m | — |
| KOP. KEL. SUNGAI PANAS | Pekuburan Sei.Panas (Batam) | 51 m | — |

**The honest verdict: *"dibangun di tanah kuburan"* is not supported as a
pattern.** Two cases are individually striking — a `Terverifikasi` land asset
481 m inside a private memorial park is a hard thing to explain — and they are
worth chasing on imagery. But an existence claim needs the individual case to
survive verification, and the rate carries no signal at all.

## Finding 3 — groundwork for [08](../README.md#08--exact-geometry-refinement-of-05-and-06)

Distance to the nearest *pasar* (`amenity=marketplace`), now measured exactly
rather than in H3 bands: median **10.5 km**, with 689 KDMP within 250 m, 1,806
within 500 m and 9,716 within 2 km. The village-centre reference is in the same
table for every cooperative.

## What this cannot settle

**A coordinate in a field may never have been a building.** This is 04's
ambiguity in a new place, and the evidence here leans *against* the reassuring
reading. If SIMKOPDES coordinates were desa centroids, a desa that is mostly
rice fields would produce a point in the middle of a rice field automatically —
and would land inside farmland far more often than an OSM village node does,
which is exactly the 2.4× we measured.

The sharpest available test is road distance, from [05](../05-road-access/): a
building stands next to a road, a centroid need not. It does not clear them.

| | Within ~140 m of a mapped road |
|---|---|
| All KDMP, reweighted to the candidates' provinces | **72.5%** |
| The 536 candidates | **59.5%** |

**The candidates are *less* roadside than comparable cooperatives, not more.**
That is consistent with genuine placement out in the fields, and equally
consistent with coordinates that were never buildings. 276 candidates are both
roadside and confirmed cropland — 133 of them `Terverifikasi` — and that subset
is where the centroid explanation is weakest, but "weakest" is not "excluded".

**No aggregate from this report should be written as "N cooperatives were built
in paddy fields."** The supportable sentence is *"N cooperatives are **recorded
at** a location inside a paddy field"* — and if the ministry answers that the
coordinates are wrong, that is a different story, not a smaller one: it means
the registry does not know where its own cooperatives are.

### Other limits

- **The asymmetry rule, harder here than anywhere else.** OSM maps ~9,100 burial
  grounds against ~84,000 desa — roughly 10% coverage. A hit is strong evidence;
  a miss is *no* evidence. Every "distance to nearest X" column is an **upper
  bound** on the truth. [`osm_landuse_coverage_by_province.csv`](osm_landuse_coverage_by_province.csv)
  is the check: Gorontalo has **no** KDMP with a mapped burial ground within
  2 km, and the Papua provinces sit at 1–2%. Absence there is absence of mappers.
- **The village-core distance is weak and is not used as a screen.** `place=village`
  is one node for a desa that may be kilometres across, so the "49.3% of KDMP are
  more than 800 m from any village node or place of worship" figure in the
  per-cooperative table mostly measures where mappers drop a label. It is in the
  output for context; do not build a claim on it.
- **`landuse=farmland` is not `sawah`.** OSM Indonesia tags wet rice fields as
  farmland (`landuse=paddy` is effectively unused), so this cannot separate a
  paddy field from a dry field or a plantation edge. The WorldCover cross-check
  says "cropland", not "rice".
- **Polygon quality is uneven even after filtering.** The 2-village threshold
  catches the worst tracings; a 117 km² "field" in Majalengka is still a large
  object to call one field, even with no village node inside it.
- OSM changes daily; this is a 2026-08-07 snapshot.

## Outputs

| File | Contents |
|---|---|
| [`farmland_candidates.csv`](farmland_candidates.csv) | **536 rows** — the shortlist, with depth, polygon quality, WorldCover class, road distance, land status, `imagery_url` |
| [`cemetery_candidates.csv`](cemetery_candidates.csv) | all 22 burial-ground hits |
| [`farmland_funnel.csv`](farmland_funnel.csv) | the 2,206 → 536 filter chain |
| [`null_comparison.csv`](null_comparison.csv) | KDMP vs village nodes vs minimarkets, per class |
| [`landuse_pip_summary.csv`](landuse_pip_summary.csv) | national counts and distance bands per class |
| [`osm_landuse_coverage_by_province.csv`](osm_landuse_coverage_by_province.csv) | **read before treating any absence as evidence** |
| `kopdes_landuse_context.csv` | per-cooperative, all classes, joins to [03](../03-population-coverage/)/[05](../05-road-access/) on `cooperative_id` (gitignored, ~28 MB, rebuilds in ~1 min once the index is cached) |
