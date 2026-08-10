# Reports

Findings from the KDMP investigation. One directory per question, each
self-contained and reproducible.

```
reports/NN-slug/
    run.py      the analysis, runnable from the repo root
    README.md   the write-up - what was found, and what it does not support
    *.csv       outputs, committed so findings survive without a re-run
```

Run any of them with `python reports/NN-slug/run.py`. Dependencies:
`pip install -r reports/requirements.txt`.

## Index

| # | Report | Question | Network | Status |
|---|---|---|---|---|
| 01 | [snapshot-drift](01-snapshot-drift/) | Is SIMKOPDES still being filled in? Are the zeros temporary? | **live API** | run 2026-08-09 |
| 02 | [zero-inflation](02-zero-inflation/) | How much of the performance data is actually zero? | no | run 2026-08-09 |
| 03 | [population-coverage](03-population-coverage/) | Who is within reach of a KDMP, and which KDMP are near nobody? | first run only | run 2026-08-09 |
| 04 | [siting-screen](04-siting-screen/) | Which KDMP sit somewhere physically implausible? | cloud rasters | run 2026-08-09, top 2,500 |
| 05 | [road-access](05-road-access/) | How far is each KDMP from a road? | no | run 2026-08-09 |
| 06 | [minimarket-proximity](06-minimarket-proximity/) | Were KDMP built on top of existing modern retail? | no | run 2026-08-09 |
| 07 | [landuse-polygons](07-landuse-polygons/) | On a graveyard? In a paddy field? | cloud rasters | run 2026-08-10, 536 candidates |

## What we can and cannot say right now

Read this before quoting any number out of these reports.

**Established:**

- Reported economic activity is extraordinarily concentrated — **100 villages
  out of 84,624 carry 37% of all national transaction value**, 1,000 carry 93%
  (02).
- **Coverage is not the problem**: 95% of Indonesians live within ~1.4 km of a
  KDMP (03). The "they built them where nobody can reach them" claim does not
  hold as a mass phenomenon.
- There is a **real tail**: 21.4% of cooperatives sit in a 400 m cell with zero
  recorded population, and 174 have nobody within 5 km (03).
- That tail contains **concrete, nameable candidates**: of the 2,500 most
  isolated, 2,346 are in closed forest, 69 on water/mangrove/wetland, 993 on
  steep ground — and **401 of them carry an officially `Terverifikasi` land
  asset**, 171 both verified and steep (04).
- **6.2% of cooperatives (5,133) have no made road within ~5 km**; 4,321 have no
  road of any kind, not even a track (05). Two methodologically independent
  sources agree: 87.4% of those also sit in a zero-population cell, against a
  21.4% baseline.
- **The paddy-field claim holds; the graveyard claim does not.** KDMP fall inside
  a mapped `landuse=farmland` polygon at **2.65%** against **1.10%** for OSM's own
  village-centre nodes — 2.4× — and **448** are placed on cropland by OSM *and* by
  ESA WorldCover independently, ≥100 m from the field edge, with people living
  around them (07). Burial ground is the opposite: **22 cases, a rate
  indistinguishable from village nodes** (0.026% vs 0.022%), only 7 of them more
  than 25 m inside, 16 of 22 in cities where a TPU is a city block. Two
  individual cases remain worth chasing; the pattern is not there.
- **Short-range overlap with existing modern retail is real but modest.** After
  controlling for both sitting on roads in populated areas, a mapped minimarket
  is ~9.6 pts more likely to have a KDMP within 500 m than a comparable random
  roadside location; the excess decays to nothing by 2 km (06). This survives
  re-tiering the retail data, so it does not depend on where the format
  boundary is drawn.
- SIMKOPDES **carries no per-record timestamp**, and its `updated_at` is the API
  response time, not a data-freshness stamp (01). Dated snapshots plus diffing
  is the only way to measure currency.
- **No reporting backlog is draining.** Comparing two full snapshots four days
  apart: of 80,553 villages reporting zero transactions on 2026-08-05, **exactly
  one** reported any activity by 2026-08-09 (01). Meanwhile the registry grew by
  40 cooperatives. Records are added; activity is not reported against them.
- The 2026-08-05 export contains **1,555 duplicate village rows** (plus 148
  subdistricts, 5 districts), which inflate any sum over rows. Always
  `drop_duplicates` on the id (01).

**Not established, and currently unidentifiable:**

- **Whether a zero means "no activity" or "not yet reported".** Much narrower
  than it was — a system being actively populated should show zeros converting,
  and over four days exactly one did out of 80,553 (01). But formally the two
  remain indistinguishable: a cooperative could be trading briskly and reporting
  nothing, and nothing in this data would reveal it. Write "has not **reported**
  any transaction", never "is inactive". Monthly snapshots are what close this.
- **Whether flagged sites are badly sited or badly geocoded.** The screen in 04
  cannot tell a cooperative built in a forest from one whose coordinate is
  wrong. Both are findings; they are different findings. Each case needs
  imagery before it is cited.
  **07 sharpened this into a specific worry and could not resolve it**: if a
  SIMKOPDES coordinate is a desa centroid, a desa that is mostly rice fields
  lands in a rice field automatically — and would beat the village-node baseline
  by roughly the margin observed. The road test leans the wrong way: the
  candidates are *less* likely to be near a road than comparable cooperatives
  (59.5% vs 72.5%), not more. So write "**recorded at** a location inside a
  paddy field", never "built in a paddy field". If the ministry answers that the
  coordinates are wrong, that is a different story, not a smaller one.
- **Cannibalisation.** 06 establishes *proximity*, which is a precondition for
  competition, not evidence of it. The claim is about trade, and trade data is
  97% zero. Nor can any of this establish intent — KDMP and minimarkets may
  simply both target the village focal point.
- **Anything from OSM stated as an absence.** OSM coverage in rural Indonesia is
  partial and urban-biased (13.8% of Indomaret outlets, 10.9% of Alfamart).
  Presence is evidence; absence is not. Write "no road *mapped in OSM* within
  5 km", and treat retail proximity figures as lower bounds.

## Backlog — agreed, not yet built

### 08 — Exact-geometry refinement of 05 and 06

**H3 to rank, exact geometry to report.** Ring distance is hex-grid distance
with ~15% directional error, quantised to ~132 m — right for sorting 83k into
bands, wrong for a published sentence about a named place. The narrative needs
"the nearest road is 3.2 km away", not "in the >2 km band".

Stage 2 over the shortlists only (~5k points): `pyogrio` bbox-filtered reads to
pull local geometry, then `shapely` distance against actual LineStrings and
polygons. **Scope is now roads and retail only** — [07](07-landuse-polygons/)
already ships geodesic distance to the nearest marketplace and village centre
for all 83,342 cooperatives, so that half is done.

Two things to get right:

- **Never buffer in degrees.** A 0.01° buffer is a different size in Aceh than
  in Papua. Use a projected CRS per UTM zone or geodesic distance (`pyproj.Geod`).
- **Don't over-promise precision.** OSM road geometry is good to ~5–15 m, worse
  for rural tracks. 132 m bands → ~15 m truth is a real gain; decimals of a
  metre are theatre.

### 09 — External corroboration of the transaction figures

The single weakest point in the whole investigation: the government can answer
"0.85 transactions per cooperative" with *"the website simply isn't up to
date"*, and [01](01-snapshot-drift/) cannot yet refute it.

Two independent lines of defence:

1. **The snapshot series** (01) — time-sensitive, see Conventions below.
2. **External figures**: Kemenkop press releases and ministerial statements,
   DPR Komisi VI hearing records, BPS, and reporting from Kompas / Tempo /
   Katadata / CNBC Indonesia / Bisnis.com. Either the ministry's own public
   claims match its dashboard — in which case the rebuttal collapses and the
   dashboard is the official number — or they diverge wildly, which is a story
   in itself. Both outcomes are useful.

### Known data gap to fix upstream

`scripts/download_osm.py` pulls `shop=convenience|supermarket|department_store`,
so it **excludes `shop=kiosk` (6,464) and `shop=general` (797) by query design**
— categories that are exactly village retail. This is separate from, and
additional to, OSM's coverage problem. `classify_brand()` also misses spelling
variants (`Alfa Express`, `Alfa Midi`, Yomart, 7-Eleven, Bali chains); the
report layer repairs these in `06/run.py`, but the fix belongs upstream.

## Conventions

- **Never regenerate `data/raw/` in place.** It is the 2026-08-05 baseline for
  the drift measurement in 01; overwriting it destroys the only evidence that
  answers the "not entered yet" rebuttal. New pulls go to
  `data/snapshots/YYYY-MM-DD/` via
  `python scripts/extract_kopdes.py data/snapshots/$(date +%F)`.
- **Snapshot CSVs are held locally and never committed** (~28 MB each); findings
  are published as pages, and raw snapshots go out on request. The
  `_manifest.json` files **are** committed — their SHA-256 hashes are the only
  provenance record, because a SIMKOPDES snapshot cannot be re-fetched once the
  API moves on. **Back the local snapshots up outside this working tree**; if
  they are lost, the central finding becomes unverifiable by anyone, including
  us.
- **Deduplicate on the id before comparing or summing** any `kopdes_stats_*`
  file. The 2026-08-05 export has 1,555 duplicate villages.
- **Start the monthly snapshot series now — this is the one irrecoverable
  item.** "The website simply isn't up to date" is the strongest rebuttal
  available to the ministry, and today we cannot refute it. Four monthly
  snapshots showing zeros not converting turns the investigation's weakest
  claim into one of its strongest. Every month not captured is lost permanently,
  and no amount of later work recovers it.
- Scripts write only inside their own report directory.
- Anything hitting the live API says so in its README, because re-running will
  legitimately produce different numbers than the committed CSVs.
- Every claim in a report README should trace to a committed CSV in the same
  directory.
