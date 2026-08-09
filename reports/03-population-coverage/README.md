# 03 — Population coverage and remoteness

**Run**: `python reports/03-population-coverage/run.py` · No network after first
run · **Source**: Kontur 400m population (H3 r8) + `kopdes_locations.csv`

## The method, in one paragraph

Kontur's population grid is *already* H3 at resolution 8, so it needs no
spatial processing at all — drop the geometry column and it becomes a 3 MB
parquet keyed by cell id, and every question becomes a hash join in DuckDB.
Catchments are k-rings, not buffers. The whole national analysis runs in about
a minute on a laptop with no PostGIS, no rasters and no geometry library.

| | Size |
|---|---|
| `kontur_population_ID.gpkg` | 172.4 MB |
| `population_h3.parquet` (zstd, geometry dropped) | **3.0 MB** |

874,919 cells, 277,542,182 people — which matches Indonesia's population, so
the grid is complete.

## Finding 1 — coverage is not the problem. 95% of Indonesians live within 1.4 km of a KDMP.

[`coverage_by_radius.csv`](coverage_by_radius.csv)

| Catchment | Population covered | Share of national |
|---|---|---|
| own 400 m cell | 64,927,494 | 23.4% |
| ~0.5 km | 203,140,113 | 73.2% |
| **~1.4 km** | **263,687,843** | **95.0%** |
| ~2.8 km | 274,452,461 | 98.9% |
| ~5.1 km | 276,989,563 | 99.8% |

`analytics-plan.md` §A2 asks what share of the population is within reach of a
KDMP and proposes to deliver a list of "coverage deserts" and the "top-100 most
underserved subdistricts". **There aren't any at a meaningful scale.**

This should be reported as a result, not quietly dropped. It reframes the
investigation: the program did not miss people. It reached essentially
everybody, and the reported output is still 0.85 transactions per cooperative
(see [02-zero-inflation](../02-zero-inflation/)). Saturation, not coverage, is
the story.

> **Method note.** Catchments overlap heavily, so coverage must be computed
> over the **distinct union** of cells. Summing per-cooperative catchment
> populations gives 17.2 billion at k=11 — 62× the population of Indonesia.
> The script does the union; don't "simplify" it into a sum.

## Finding 2 — the mirror statistic: 21.4% of KDMP have nobody in their own cell

[`remoteness_bands.csv`](remoteness_bands.csv),
[`kopdes_remoteness.csv`](kopdes_remoteness.csv) (per-cooperative)

- **17,804 cooperatives (21.4%)** sit in a 400 m cell with **zero** recorded
  population.
- Median own-cell population for the remaining 78.6%: **502 people**.

By population within ~5 km:

| Band | Cooperatives | Share |
|---|---|---|
| nobody within 5 km | 174 | 0.21% |
| < 500 | 1,574 | 1.89% |
| 500 – 2k | 2,408 | 2.89% |
| 2k – 10k | 8,133 | 9.76% |
| > 10k | 71,053 | 85.25% |

Read these two findings together and the honest summary is: **the placement
critique is not a mass phenomenon, but it has a real tail.** 174 cooperatives
with nobody within 5 km is 0.2% of the program — and it is also 174 concrete,
nameable, checkable cases. That tail is what
[04-siting-screen](../04-siting-screen/) is built to surface.

## Caveats

- "Zero population in the cell" is a Kontur modelling output, not ground truth.
  Kontur fuses GHSL, Facebook HRSL, Microsoft Buildings and OSM; all four
  under-detect in forest and on small islands. Some of the 21.4% will be real
  settlements the model missed.
- It also catches **coordinate errors**, not just remote siting — a cooperative
  whose lat/lon is wrong lands wherever the wrong coordinate points, often in
  water or forest. Distinguishing the two needs imagery. See 04.
- k-ring distance is approximate (an r8 cell is ~0.46 km across, so k rings
  ≈ 0.46·k km) and degrades slightly with latitude. Fine for banding, not for
  a published "exactly 1.4 km" claim.

## Output for later

[`kopdes_remoteness.csv`](kopdes_remoteness.csv) is per-cooperative with
`h3_8`, `own_cell_pop`, catchment populations and `remoteness_band`. It is the
intended input for the screengrid views — it already carries the H3 cell id, so
it joins to anything else keyed the same way.
