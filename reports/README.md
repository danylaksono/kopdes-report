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
| 08 | [exact-geometry](08-exact-geometry/) | How far is it *really*? Are the coordinates even possible? | no | run 2026-08-10 |
| 09 | [external-corroboration](09-external-corroboration/) | Does the ministry's own public figure match its dashboard? | sources cited, not scraped | run 2026-08-10 |
| 10 | [coop-clustering](10-coop-clustering/) | Do KDMP cluster on top of each other, and does it hurt? | no | run 2026-08-12 |
| 11 | [savings-behaviour](11-savings-behaviour/) | Are members actually saving, or are the accounts dormant? | no | run 2026-08-12 |
| 12 | [product-mix](12-product-mix/) | What does the program actually sell? | no | run 2026-08-12 |
| 13 | [compliance-npwp-nib](13-compliance-npwp-nib/) | Is the paperwork real, and is anyone operating under it? | no | run 2026-08-12 |
| 14 | [island-comparison](14-island-comparison/) | Whose program is this — Java or Indonesia? | no | run 2026-08-12 |
| 15 | [construction-output](15-construction-output/) | Does construction track output? | no | run 2026-08-12 |

## What we can and cannot say right now

Read this before quoting any number out of these reports.

**Established:**

- Reported economic activity is extraordinarily concentrated — **100 villages
  out of 84,624 carry 37% of all national transaction value**, 1,000 carry 93%
  (02).
- **Savings are reported ~4× more often than transactions, and the money is
  one-time capital, not ongoing saving.** 12.5% of villages report any savings
  (vs 3.0% transactions) and 14.1% report *some* financial footprint; 9,192
  villages report savings with zero transactions. Of those reporting both pokok
  and wajib, median wajib/pokok = 0.28 and only 15.7% have wajib > pokok — the
  plan's own "wajib ≫ pokok = active" test fails. The field tiers (accounts
  ~96% > pokok 11.9% > wajib 9.2% / transactions 3.0%) are the shape a real
  activity funnel would produce (11).
- **Savings spread far less concentrated than transactions** (top-100 = 24.4%
  vs 37%; top-1,000 = 56.9% vs 93%), consistent with capital being collected at
  registration rather than through operations (11).
- **Savings uptake has a ~400× province gradient** — 31.3% of villages in
  Yogyakarta down to 0.08% in Papua Pegunungan — tracking economic geography,
  not randomness (11).
- **The program sells staple groceries and farm inputs.** 75% of reported
  sales value is rice + cooking oil; fertilizer is the main input, present in
  24 provinces. KDMP are positioned as village grocery shops (12).
- **The license exists; the operations don't.** 97.1% of cooperatives hold
  NPWP, 72.9% NIB (totals reconcile with the national summary). Only 23
  villages (0.03%) report a transaction without a license, while 70.1% of
  villages hold the license and report no transaction — paperwork present,
  operations absent (13).
- **The program is a Java phenomenon.** Java holds 30% of cooperatives but
  ~68% of reported transaction value; Papua 8.5% of cooperatives and 0.2% of
  value (~85× per-cooperative gap). The remoteness tail, the land-verification
  gap (3.2% verified in Papua) and the activity gap are all eastern-Indonesia
  phenomena (14).
- **Construction is a quarter done; the RAT channel is empty.** 23.0% of
  cooperatives nationally are at 100% construction and 45.5% have any
  construction stage recorded; `total_rat` is zero in all 38 provinces. The
  construction-vs-output correlation (ρ = 0.34, n = 38) is a geography
  confound, not evidence (15).
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
- **KDMP are near-continuous, not clustered.** 91.2% of cooperatives have
  another KDMP within 5 km (exact geodesic), 58.9% within 2 km, 22.1% within
  1 km, 4.6% within 500 m; 6.7% share the same ~1 km H3 cell — but most of that
  is pairs (2,100 of 2,501 cells hold exactly two), maximum 17 in one cell near
  Wamena (Papua Pegunungan) (10).
- **About two-thirds of apparent fine-scale co-location is a coordinate
  artefact.** 821 cooperatives — 19 with impossible coordinates (08) plus 802
  sharing an exact duplicate coordinate (388 groups, up to 11 at one point;
  concentrated in Aceh and Papua) — are set aside in 10. At the ~350 m scale
  they are 64% of apparent co-location, so same-cell figures must be read from
  the clean set. Write "recorded at", never "built at".
- **Clustering does not measurably hurt performance (null).** Cooperatives that
  share a cell report transactions at the same rate as isolated ones (3.9% vs
  3.5%), and cluster size does not correlate with per-cooperative value
  (Spearman −0.02 all, +0.05 reporting-only). B1's "clustered → lower per-unit
  output" hypothesis is not supported (10).
- **The "too close together" claim does not hold as a mass phenomenon either.**
  At any linking radius ≥ ~1 km, density-connected components chain across Java
  (55–82% of cooperatives merge), so KDMP form a saturated field in populated
  Indonesia rather than discrete over-concentrated pockets. The honest
  short-range footprint is 22% within 1 km (10).
- **The "the website isn't up to date" rebuttal is closed.** On 2026-08-09 the
  press reported the national total as **Rp 179.72 miliar**; our own API pull the
  same day gives **Rp 179.79 miliar** — a **0.042%** difference (09). The
  ministry quotes this dashboard, so whatever it says about activity is the
  government's own public account of it. Independently, the head of Bakom put
  **1,061 cooperatives operating** on 2026-06-08 (1.3% of the registry) against
  our 3.0% reporting any transaction, in the same two provinces.
- **The headline is Rp 179.5 *billion* (miliar), ~USD 11 million — about
  Rp 2.15 million (~USD 130) per cooperative to date.** Any "179.5T" is wrong by
  1000× (09).
- **19 cooperatives are not in Indonesia**, and 18 are a latitude sign error
  (08). All 19 sit in 04's candidate list and 05's roadless set, so: 04's
  land-verified candidates **401 → 388**, its water/mangrove cases **69 → 67**,
  05's no-made-road set **5,133 → 5,114**, no-road-at-all **4,321 → 4,302**.
- **The roadless set, measured exactly**: median **9.7 km** to the nearest made
  road, 90th percentile 26.5 km, maximum 292 km; 600 are beyond 25 km (08).
- **05's ring distances are sound; 06's are biased.** Re-measured against real
  geometry: roads median absolute error **34 m** (92% within one cell width);
  minimarkets **+169 m median signed error**, i.e. 06 *overstated* distance and
  undercounted proximity (08). 06's null-model comparison is unaffected — both
  arms used the same method — but its absolute bands are superseded.
- SIMKOPDES **carries no per-record timestamp**, and its `updated_at` is the API
  response time, not a data-freshness stamp (01). Dated snapshots plus diffing
  is the only way to measure currency.
- **Value grows; participation does not.** Comparing two full snapshots four days
  apart: of 80,553 villages reporting zero transactions on 2026-08-05, **exactly
  one** reported any activity by 2026-08-09 (01). **09 refines this**: over a
  longer window the national total is *not* flat — it rose 13.8% between
  2026-07-31 and 2026-08-09 — but it rose inside an almost perfectly static set
  of reporting villages (2,516 → 2,517). The supportable claim is the reported
  total rises while the number of cooperatives reporting anything does not; it is
  concentration deepening, not a backlog draining. Do not write "nothing is being
  entered".
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
- **Whether the densest co-location cells are real.** 17 cooperatives recorded
  in one ~1 km cell near Wamena (and the other dense cells in Papua, Aceh,
  Jambi) are as likely to be many desa geocoded to a town as 17 physically
  co-located buildings. Same imagery bar as 04/07 before any name is cited (10).
- **Cannibalisation.** 06 establishes *proximity*, which is a precondition for
  competition, not evidence of it. The claim is about trade, and trade data is
  97% zero. Nor can any of this establish intent — KDMP and minimarkets may
  simply both target the village focal point.
- **Anything from OSM stated as an absence.** OSM coverage in rural Indonesia is
  partial and urban-biased (13.8% of Indomaret outlets, 10.9% of Alfamart).
  Presence is evidence; absence is not. Write "no road *mapped in OSM* within
  5 km", and treat retail proximity figures as lower bounds.

## Backlog — cleared

The plan-review's *do* list is now fully built: [08](08-exact-geometry/),
[09](09-external-corroboration/), [10](10-coop-clustering/),
[11](11-savings-behaviour/), [12](12-product-mix/), [13](13-compliance-npwp-nib/),
[14](14-island-comparison/) and [15](15-construction-output/).

What is left is not analysis but operations and one upstream fix:

- **The report site itself** — the scrollytelling investigative report decided
  2026-08-09 (see AGENTS.md). All 15 reports are now its methodology appendix.
- **Start the monthly snapshot series** — the one irrecoverable item; see
  Conventions.
- **Fix `download_osm.py` upstream** (below), so the retail picture includes
  `shop=kiosk`/`general`.

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
