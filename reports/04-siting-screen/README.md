# 04 — Siting screen: which KDMP sit somewhere implausible?

**Run**: `python reports/04-siting-screen/run.py --top 2500` · Samples cloud
rasters over HTTP · **Last run**: 2026-08-13 (2,500 candidates, on 08-13 coordinates)

> **These are candidates, not findings.** Read
> [Verification is mandatory](#verification-is-mandatory) before citing any row.

## Why a screen and not a statistic

The public critique — *"dibangun di tanah kuburan / di tengah sawah / di atas
bukit"* — is an **existence claim**. It is established by a handful of
well-evidenced, nameable cases, and it is not weakened by those cases being 0.2%
of the program: a small tail of absurd sites is exactly what a quota-driven
rollout produces. No national average can establish or refute it, which is why
[03's](../03-population-coverage/) 95%-coverage result is beside the point here.

So this is a ranking tool. It sorts 83,342 cooperatives by how implausible their
surroundings look, so a human only has to eyeball the top.

## Method — and why "nationwide terrain analysis" isn't the huge job it sounds like

Two stages, because the cheap signal is free and the expensive one isn't.

**Stage A** (free, offline, all 83,342): an isolation score from Kontur
population — empty own cell, <100 people within 1.4 km, <1,000 within 5.1 km.

| Isolation score | Cooperatives |
|---|---|
| 5 (worst) | 2,183 |
| 4 | 4,051 |
| 3 | 327 |
| 2 | 11,836 |
| 1 | 149 |
| 0 | 64,796 |

**Stage B** (shortlist only): elevation, local relief and land cover
**point-sampled** from Copernicus GLO-30 and ESA WorldCover 10m COGs on open S3.

The key point: you never process a raster, you *sample* one. GDAL issues an HTTP
range request for the few KB around each point, so there is no download and no
storage — 2,500 points across 255 DEM tiles and 72 land-cover tiles resolved
2,475 and 2,490 points respectively. Group points by tile and each tile opens
once.

**This is why the analysis does not need to be localised.** Screening is
national and cheap; only the genuinely expensive work (isochrones, imagery
review) needs to be local, and by then it runs on a few dozen cases.

## What the top 2,500 look like

[`candidates.csv`](candidates.csv) · [`flag_summary.csv`](flag_summary.csv)

| Land cover | Candidates |
|---|---|
| Tree cover | 2,346 |
| Grassland | 46 |
| Mangrove | 30 |
| Water | 30 |
| (unresolved) | 26 |
| Shrubland | 11 |
| Herbaceous wetland | 9 |
| Bare / sparse | 1 |
| **Cropland** | **1** |

| Flag | Candidates |
|---|---|
| `flag_no_population` | 2,500 |
| `flag_not_builtup` | 2,500 |
| `flag_implausible_cover` | 2,440 |
| `flag_steep` (>60 m relief over ~200 m) | 1,008 |

**The sharpest subset**: of the 2,500, **384 carry a land-asset status of
`Terverifikasi`** — the land was officially signed off — and **175 are both
land-verified and on steep ground**. A verified land asset in closed forest at
1,700 m is a much harder thing to explain than an unverified one.

### Extreme cases, land-verified, ranked by local relief

All have **zero recorded population in their own 400 m cell**.

| Cooperative | Province | Elev (m) | Relief/200 m | Cover | Surveyor |
|---|---|---|---|---|---|
| KDMP BARA (Kec. Airbuaya) | Maluku, Kab. Buru | 1,760 | 210 m | Tree cover | Agrinas |
| KDMP SUKA RAMI (Kec. Air Nipis) | Bengkulu, Kab. Bengkulu Selatan | 1,756 | 206 m | Tree cover | Agrinas |
| KDMP SUBAYO | Papua Pegunungan, Kab. Yahukimo | **2,805** | 205 m | Grassland | KOPERASI |
| KDMP MANTANGISI | Sulawesi Tengah, Kab. Tojo Una Una | 1,379 | 189 m | Tree cover | Agrinas |
| KDMP SYARIAH EKAN | Aceh, Kab. Gayo Lues | 1,495 | 187 m | Tree cover | Agrinas |
| KDMP BATU AMPAR (Kec. Kedurang) | Bengkulu, Kab. Bengkulu Selatan | 1,849 | 178 m | Tree cover | KOPERASI |

### On water, mangrove or wetland (69 candidates, 13 land-verified)

| Cooperative | Province | Cover | Elev (m) | Surveyor |
|---|---|---|---|---|
| KDMP SENARU | NTB, Kab. Lombok Utara | Water | **1,998** | BUSINESS ASSISTANCE |
| KDMP BUKU LIMAU | Bangka Belitung, Kab. Belitung Timur | Mangrove | 2.2 | BUSINESS ASSISTANCE |
| KDMP PENAAH | Kepulauan Riau, Kab. Lingga | Mangrove | 0.0 | KOPERASI |
| KDMP CIKONENG (Kec. Anyar) | Banten, Kab. Serang | Water | 4.0 | Agrinas |
| KDMP MINDAHAN KIDUL (Kec. Batealit) | Jawa Tengah, Kab. Jepara | Water | 0.0 | Agrinas |
| KDMP KARANGREJO (Kec. Gumukmas) | Jawa Timur, Kab. Jember | Water | 0.0 | KOPERASI |

Every one of these carries a satellite-imagery link in
[`candidates.csv`](candidates.csv) (`imagery_url`).

## Method validation: is one 10 m pixel enough?

`python reports/04-siting-screen/sensitivity_check.py` · outputs
[`sensitivity_window_agreement.csv`](sensitivity_window_agreement.csv),
[`sensitivity_builtup_within_250m.csv`](sensitivity_builtup_within_250m.csv)

A single-pixel sample is only sound if the answer survives (a) a coarser window
and (b) positional error in the SIMKOPDES coordinate, which is unstated and
could be tens of metres. Re-sampling 248 random candidates at three window
sizes:

| Window | Centre 10 m class == window majority |
|---|---|
| 110 m (11×11 px) | **98.8%** |
| 250 m (25×25 px) | **98.4%** |

The classification is **not an artefact of pixel size**. These sites sit in
homogeneous landscapes, so a ±100 m coordinate error would not change the
verdict.

Stronger still, and the statistic to quote in prose because a reader can
picture it:

> **All 248 sampled candidates have a built-up fraction of exactly 0% within
> 250 m** — not one built-up 10 m pixel anywhere in a 500 m × 500 m box.

These are not cooperatives sitting 30 m off the edge of a village. There is
nothing built within a quarter-kilometre of any of them.

## Verification is mandatory

**An implausible surrounding has two causes and this screen cannot tell them
apart:**

1. the cooperative really was sited there, or
2. **the coordinate in SIMKOPDES is wrong.**

Both are publishable and they are *different stories* — "they built it in a
swamp" versus "the ministry doesn't know where it is". Neither can be asserted
from this table alone.

A worked example of the ambiguity: KDMP SENARU (Lombok Utara) samples at
1,998 m on land cover "Water". Senaru village sits at roughly 600 m on the flank
of Rinjani; 1,998 m and water together point at Segara Anak, the crater lake.
That is either a cooperative registered at a crater lake or a badly wrong
coordinate — and only imagery plus the village boundary settles which.

Before any case is written up: open `imagery_url`, confirm what is actually on
the ground, and check the point against the claimed desa boundary.

## Known limits of this screen

- **It selects for isolation, so it cannot find the paddy-field cases.** Only
  **1** of 2,500 candidates is on Cropland — not because those sites don't
  exist, but because a cooperative in a paddy field is *near a village* and so
  scores low on Stage A by construction. The *"dibangun di tengah sawah"* claim
  needs a second, separate screen: **built on cropland while close to
  population**. That screen is not written yet and is the obvious next step.
- **Kontur under-detects population** in forest and on small islands (it fuses
  GHSL, HRSL, Microsoft Buildings and OSM). Some "zero population" cells are
  real settlements the model missed.
- **WorldCover is 10 m**: a point 15 m off can land in a fishpond or a river and
  read as Water. `flag_steep` uses max−min elevation over a 7×7 window of 30 m
  DEM (~200 m), which is a relief proxy, not a true slope.
- 25 of 2,500 points fell outside available DEM tiles and 10 outside land-cover
  tiles; they carry `NaN` rather than being dropped.
- `land_status` is missing for 1,170 of the 2,500 — those cooperatives have no
  land-asset record at all, which is itself informative.
