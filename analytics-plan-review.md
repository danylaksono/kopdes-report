# Review of `analytics-plan.md`

**Date**: 2026-08-09 · **Reviewer pass**: feasibility triage + architecture recommendation

Every number below was measured against the committed data, not estimated. The
analyses are reproducible under [`reports/`](reports/).

> **Revised 2026-08-09 after a second round of checks.** Three verdicts in the
> first pass were wrong and are corrected in place:
>
> 1. **§2 overstated what the zeros mean.** I framed 97%-zero as "the
>    cooperatives do nothing". That is not identifiable from a single snapshot —
>    a zero may be non-reporting on a system still being rolled out. See
>    §2 and [`reports/01-snapshot-drift/`](reports/01-snapshot-drift/).
> 2. **A3's terrain half should not be dropped.** I called nationwide DEM/land
>    cover infeasible. It is cheap if you *point-sample* cloud COGs instead of
>    processing rasters — verified working. See §5.5.
> 3. **The remoteness critique was mis-scoped**, by me and by the plan. It is an
>    existence claim about a tail, not a distributional one. See §4.4.

---

## TL;DR

The plan is ambitious in the right direction, but it rests on several factual
readings of the data that don't hold up, and about a third of the modules cannot
be executed as written — not because they're hard, but because the variable they
need is either constant, absent, or 97% zero.

The good news is the opposite of what I expected going in: **the spatial side is
easy and fast** (the whole population-catchment question runs in seconds via
DuckDB + H3 parquet), and **the hard part is the outcome side** — there is
almost no per-cooperative performance signal to correlate remoteness against.

That flips the plan's centre of gravity. The defensible investigation is
**"the state built 83k cooperatives that do essentially nothing, and the
placement critique is largely a red herring"** — which the data supports much
more strongly than the placement story the plan is organised around.

---

## 1. Corrections to the plan's stated facts

These are load-bearing. Several hypotheses are built on them.

### 1.1 The headline money figure is wrong by 1000×

The plan says **"IDR 179.5T total transaction volume"** (§Data Inventory, and
`AGENTS.md`). The actual value is:

```
landing_total_transaction = 179,554,188,112 IDR
```

That is **IDR 179.55 billion** (~179.6 *miliar*), not 179.5 *triliun*. Combined
with `landing_total_transaction_count = 70,633`:

| Metric | Value |
|---|---|
| Total transaction value, nationwide | IDR 179.55 billion (~USD 11M) |
| Total transactions, nationwide | 70,633 |
| Cooperatives | 83,382 |
| **Transactions per cooperative** | **0.85** |
| **Transaction value per cooperative** | **IDR 2.15M (~USD 130)** |

Fix this before it reaches a policy brief — but note it makes the critique
*stronger*, not weaker. Fewer than one transaction per cooperative, ever, is the
single most damning number in the dataset.

### 1.2 RAT: the two source files contradict each other

The plan (C3, H4) states "all 38 provinces show `total_rat = 0`". Only one file
says that:

| Source | Field | Value |
|---|---|---|
| `kopdes_province_rat_and_construction.csv` | `total_rat` | 0 in all 38 provinces |
| `kopdes_province_rat_and_construction.csv` | `total_no_rat` | 83,382 (i.e. all of them) |
| `kopdes_stats_province.csv` | `rat_count` | **nonzero in all 38 provinces, sums to 50,174** |

So one export says zero cooperatives have held an RAT and another says 50,174
have. C3 cannot be written up until this is resolved — most likely `rat_count`
means "cooperatives *due* an RAT" or "RAT records created", but that's a guess.
**Resolve it against the raw API responses first**; C3's deliverable is currently
a coin flip between "total governance failure" and "field misread".

### 1.3 Health score has zero variance — D1 is undefined as written

| Field | Reality |
|---|---|
| `health_score` | **constant 30** across all 38 provinces |
| `health_status` | `unhealthy` × 38 |
| `average_health_index` | varies 50–57 (a 7-point spread over 38 rows) |
| `health_total_cooperative` | sums to **31,322**, i.e. only **37.6%** of the 83,382 cooperatives are scored at all |
| per-coop breakdown | 693 healthy / 2,086 fairly healthy / 28,543 unhealthy |

D1 proposes correlating the health index against other stats and running PCA.
You cannot correlate against a constant, and PCA on 38 rows × ~10 collinear
financial columns will not produce a stable factor structure — it will produce
one component that is "province size" and noise after that.

There *is* a real finding hiding here, but it's a different one: **62% of
cooperatives were never scored**, and the province-level "unhealthy" label is
computed on the 38% that were. Whether the unscored ones are excluded because
they're too new or because they have no data at all is worth chasing.

### 1.4 The population grid is H3 **resolution 8**, not 10, and has 874,919 cells, not 1.8M

`data/population/kontur_population_ID.gpkg`: 874,919 rows, `h3` values prefixed
`88…` (= res 8, ~0.46 km² per cell, ~460 m edge — which is what "Kontur 400m"
means). Total population 277,542,182, which matches Indonesia. Resolution 8 is
also what your joyplot app already uses, so the two projects agree.

This matters for A1/A2: the plan's "index into H3 resolution 9" step is a
*downsample-then-upsample* round trip that adds error for nothing. Just work at
res 8 natively and use k-rings for distance bands.

### 1.5 `kopdes_locations.csv` has no `village` column — the key join is capped at 79%

This is the most consequential structural problem in the plan and it isn't
mentioned anywhere in it.

```
kopdes_locations.csv    : cooperative_id, name, province, district, subdistrict, lat, lon
kopdes_stats_village.csv: province_id … village_id, village, <all the performance columns>
kopdes_land_assets.csv  : asset_id, cooperative, province, district, subdistrict, village, status, …
```

Coordinates live in `locations`. Performance lives in `stats_village`. **They
share no key.** The only bridge is `land_assets`, which has both the cooperative
name and the village. So any "does remoteness predict performance" analysis
needs a two-hop join:

| Hop | Match rate |
|---|---|
| `locations.name` → `land_assets.cooperative` (gives village) | 65,910 / 83,342 = **79.1%** |
| → `stats_village` on (province, district, subdistrict, village) | 65,905 / 83,342 = **79.1%** |

The 17,432 cooperatives that drop out are exactly the ones with **no land-asset
record** — which is itself a status, not random missingness. Any correlation
computed on the surviving 79% is conditioned on "has a land record", and that
almost certainly correlates with the outcomes you're testing. State this as a
limitation everywhere it applies; don't quietly analyse the 79%.

### 1.6 Road network was never actually extracted

The plan marks OSM roads **"✅ Acquired (4.5M segments, 1.6 GB GPKG)"**. What's
on disk is:

```
data/osm/indonesia-latest.osm.pbf        1.73 GB   (raw, unextracted)
data/osm/indonesia_minimarkets.gpkg      1.79 MB
```

`indonesia_roads.gpkg` does not exist. A3 is unstarted, not ready.

### 1.7 Coordinate quality is *better* than H5 assumes

H5 predicts ">5% of KDMP coordinates do not fall within their claimed province".
Without boundary polygons I used distance from the claimed province's own
centroid (from `kopdes_stats_province.csv`) as a cheap proxy:

| Threshold | Cooperatives | Share |
|---|---|---|
| > 300 km from claimed province centroid | 4,284 | 5.14% |
| > 500 km | 1,018 | 1.22% |
| > 800 km | 219 | **0.26%** |
| > 1,500 km | 23 | 0.03% |

Provinces are large (the >300 km bucket is mostly legitimately big provinces),
and the >800 km tail is dominated by the new Papua provinces, where the
*centroid in the stats file* is the more likely error. Duplicate coordinates are
also rare: 82,928 unique pairs for 83,342 rows, and only 802 rows (1.0%) share a
coordinate with anything else. 79% of coordinates carry 8 decimal places.

**H5 is probably false.** Keep E1 — do the real point-in-polygon test — but
budget it as a one-day sanity check that clears the data, not as a phase-blocking
risk.

---

## 2. The blocker nobody costed: the outcome variable is 97% zero — and we can't yet say why

`kopdes_stats_village.csv`, 84,624 rows, one row per village (84,291 villages
have exactly 1 cooperative — so village-level ≈ cooperative-level, which is the
good news):

| Column | Share that are exactly zero |
|---|---|
| `transaction_value` | **97.0%** |
| `savings_total_amount` | 87.7% |
| `accounts_count` | 4.9% |

**97% of the outcome variable is zero.** Every hypothesis phrased as "remote /
clustered KDMP have *lower transaction volumes*" (H1, H2, and the analytic core
of A4, B1, B2, D3, F1) is comparing one near-empty distribution against another
near-empty distribution. Kruskal-Wallis across accessibility bands (A4's stated
test) on a 97%-zero variable will either return a meaningless p-value driven by
tie structure, or nothing.

### 2a. What a zero means is *not yet identifiable* — and that changes the write-up, not the method

SIMKOPDES is a live system under active rollout, so a zero has two readings with
opposite implications: genuine inactivity, or activity that hasn't been entered
yet. **A single snapshot cannot separate them**, and the first pass of this
review was wrong to imply otherwise.

What the checks in [`reports/01-snapshot-drift/`](reports/01-snapshot-drift/)
established:

- **There is no per-record timestamp to appeal to.** `/cooperatives/get-all-nested`
  returns exactly `cooperative_id`, `name`, `latitude`, `longitude` — the
  extractor isn't dropping anything. The `updated_at` on the readiness endpoints
  is the **API response time**, not a data-freshness stamp (ten sequential
  queries returned ten timestamps incrementing with the wall clock).
- **The system is genuinely live**: over 4 days, transaction values moved, and
  only ever upward — the figures are cumulative.
- **But zeros did not convert**: of 332 zero-transaction subdistricts sampled,
  **0** reported any activity 4 days later.

That last number is suggestive and **not sufficient**. By the rule of three,
0/332 bounds the conversion rate at ~0.9% per 4 days (95%), which is not
negligible if sustained. It rules out a *fast* backlog release, not a slow or
quarterly-batched one.

**Consequences:**

1. **A dated snapshot series is infrastructure, not a Phase-3 nicety.** It is
   the only instrument that can resolve this, and every month without one is a
   month of resolution permanently lost. Do it first.
2. **Never regenerate `data/raw/` in place.** `scripts/extract_kopdes.py`
   overwrites the snapshot, which destroys the baseline the diff depends on.
   Snapshots should be written to `data/snapshots/YYYY-MM-DD/`.
3. **Phrase every finding accordingly.** "Only 3% of cooperatives have *reported*
   any transaction" is defensible today. "97% of cooperatives are inactive" is
   not.
4. The extractor will currently **fail** on a re-run: `/statistics/land-mapping`
   returns HTTP 500 consistently, and it is called unguarded. Make per-endpoint
   failure non-fatal and record which endpoints were unavailable per snapshot.

**This is fixable by reframing, not by more data.** Replace "how much did it
transact" with a binary and model it properly:

- Outcome: `any_activity = transaction_value > 0` — roughly 2,500 positives out
  of ~84k. That is a perfectly workable rare-event logistic regression.
- Secondary outcome: `accounts_count > 0` (95% positive — use this as the
  "exists administratively" control).
- Then: `logit(any_activity) ~ remoteness_band + population_in_catchment +
  minimarket_nearby + province` with province fixed effects.

Reporting "cooperatives >5 km from population are X% less likely to have *ever*
transacted" is both defensible and more striking than a mean comparison.

---

## 3. Module-by-module triage

| Module | Verdict | Why |
|---|---|---|
| **A1** Distance to settlement | ✅ **Do — cheap** | Runs in seconds (§5). Use res 8 natively, not res 9. |
| **A2** Population catchment | ⚠️ **Rescope** | Already answered, and it's a null result — see §4. Reframe as redundancy, not coverage. |
| **A3** Terrain & road access | ✅ **Do — cheaper than it looks** (revised) | DEM/slope **and** land cover are point-sampled from cloud COGs in minutes, no download (§5.5). Road-distance: viable, but extract highways from the 1.7 GB PBF to parquet first. Island isolation and true isochrones: still **drop nationally** — do them only for the shortlist from 04. |
| **A4** Remoteness vs. performance | ⚠️ **Rescope** | Blocked by §2 (97% zeros) and §1.5 (79% join). Recast as rare-event logistic on `any_activity`. |
| **B1** KDMP-to-KDMP proximity | ✅ **Do — cheap** | Measured below; no pairwise distance matrix needed, H3 co-location does it in 0.3 s. |
| **B2** Overlap with existing coops | ❌ **Drop for now** | Depends entirely on a pre-KDMP cooperative registry from Kemenkop/PODES that you do not have and have no acquisition path for. Everything downstream of it is speculative. Park it in the wishlist, don't roadmap it. |
| **B3** Minimarket proximity | ❌ **Drop as stated** | Fatal coverage bias — see §4.2. |
| **C1** Construction vs. output | ⚠️ **Weak — do, but downgrade** | n = 38 provinces. A correlation on 38 points with no confounder control is a scatter plot, not evidence. Present it as descriptive. |
| **C2** Land verification | ✅ **Do** | Clean, self-contained, 66k rows with status + surveyor. The strongest "ready to write" module in the plan. |
| **C3** RAT compliance | 🛑 **Blocked pending §1.2** | Resolve the file contradiction before touching this. |
| **C4** Per-unit efficiency | ⚠️ **Partial** | Per-unit normalisation is fine and cheap. The ROI half needs APBN/DIPA per-cooperative allocation, which is not in hand — don't roadmap the ROI deliverable. |
| **D1** Health decomposition | ❌ **Drop as written** | Zero-variance dependent variable (§1.3). Replace with "who got scored at all" (37.6%). |
| **D2** Product mix | ✅ **Do — cheap** | 262 rows. Shannon diversity on top-N-truncated lists is biased, so just report category composition; skip the diversity index. |
| **D3** NPWP/NIB compliance | ✅ **Do** | Present at all four admin levels, no join needed. The "zombie" test inherits §2's reframing. |
| **E1** Coordinate validation | ✅ **Do — but descope** | Cheap, and likely to clear the data (§1.7). |
| **E2** Name-matching audit | ✅ **Do** | Necessary given §1.5 — the two-hop join *is* the name-matching risk. |
| **E3** Temporal consistency | ✅ **Do** | Just re-run the extractor and diff. Highest value-per-hour item in the whole plan; do it now so the clock starts. |
| **F1** Transaction anomaly detection | ❌ **Drop** | Outlier detection on a 97%-zero variable finds only the nonzero ones. That's not anomaly detection, that's a filter. |
| **F2** Savings behaviour | ✅ **Do** | 87.7% zeros is less degenerate than transactions, and the pokok-vs-wajib ratio is a genuine dormancy signal. |
| **F3** Island group comparison | ✅ **Do — cheap** | Descriptive, no new data. |
| **F4** Product overlap (Jaccard) | ⚠️ **Low value** | Jaccard on truncated top-10 lists mostly measures list length. Cheap, but don't expect a finding. |

**Count**: 11 do · 5 rescope · 6 drop · 1 blocked.

---

## 4. Two findings the plan should be restructured around

I ran these while assessing feasibility; they're real results, not estimates.

### 4.1 Population coverage is a solved problem — 95% within 1.4 km

Union of H3 catchments (deduplicated — see the trap in §5.3), against Kontur's
277,542,182 total:

| Catchment radius | Population covered | Share of national |
|---|---|---|
| own cell only (~0.2 km) | 64,927,494 | 23.4% |
| ~1.4 km (k=3) | 263,687,843 | **95.0%** |
| ~2.8 km (k=6) | 274,452,461 | 98.9% |
| ~5.1 km (k=11) | 276,989,563 | 99.8% |
| ~10.2 km (k=22) | 277,492,598 | 100.0% |

A2 asks "what % of the population lives within reasonable reach of a KDMP" and
proposes a deliverable listing "coverage deserts" and "top-100 most underserved
subdistricts". **There are no meaningful coverage deserts.** Ninety-five percent
of Indonesians live within 1.4 km of one of these things.

Don't bury this — it's a finding. It reframes the whole investigation: the
program's failure is not that it missed people. It's that it reached essentially
everyone and still produced 0.85 transactions per cooperative. Invert A2 from
*coverage* to *saturation*.

The mirror statistic is the one worth keeping from A1: **21.4% of KDMP (17,804)
sit in an H3 cell with zero recorded population**, and the median own-cell
population for the rest is 502 people. That's the actual remoteness signal, and
it costs 30 ms to compute.

### 4.2 B3 cannot be done with OSM minimarkets — the bias runs the wrong way

`data/osm/indonesia_minimarkets.gpkg` holds 10,580 POIs:

| Brand | Count in OSM |
|---|---|
| other | 4,539 |
| Indomaret | 3,030 |
| Alfamart | 2,181 |
| Circle K | 242 |
| Alfamidi | 219 |
| FamilyMart | 68 |

Alfamart and Indomaret each operate on the order of **20,000 outlets**
nationally. OSM has 5,211 of the two combined — roughly **12% coverage**. Worse,
OSM POI density tracks mapper density, which tracks urbanisation — so coverage is
*best* in cities and *worst* in exactly the villages where KDMP sit.

Measured against this dataset, 2.8% of KDMP have a minimarket within ~0.4 km and
16.4% within ~1.8 km. Those numbers are floors of unknown tightness, and the
undercount is **systematically concentrated in the rural areas the analysis is
about**. Publishing "only 2.8% of KDMP face direct minimarket competition" from
this data would be wrong in a way that happens to exonerate the program — the
worst kind of error to make in a critical investigation.

Either source real retail locations (Alfamart/Indomaret store locators are
publicly scrapeable, ~40k records, and would make B3 the strongest module in the
plan), or drop B3. Don't run it on OSM.

### 4.3 Clustering (B1) — cheap, and there is a signal

Co-location at three H3 resolutions, 0.3 s total, no distance matrix:

| Resolution | ~cell width | KDMP sharing a cell with ≥1 other | Max in one cell |
|---|---|---|---|
| r9 | ~0.7 km | 1,254 (1.5%) | 12 |
| r8 | ~1.4 km | 6,381 (7.7%) | 17 |
| r7 | ~3.6 km | 35,832 (43.0%) | 23 |

The plan's proposed method — "pairwise distance matrix for all ~83k points" —
is 3.5 billion pairs. Don't. H3 co-location plus k-ring neighbours gives the same
answer in under a second, and DBSCAN, if you still want it, should run on the
~6k already-clustered points, not all 83k.

### 4.4 The remoteness critique is an existence claim, and both the plan and my first pass mis-scoped it

The public criticism is not "the average KDMP is far from people". It is
"*this* one was built on burial ground, *that* one in the middle of a paddy
field, *this* one on a hilltop with no road" — the argument being that a program
producing such sites was pushed through on a quota rather than on need.

That is an **existence claim**. It is established by a handful of
well-evidenced, nameable cases, and it is *not* weakened by those cases being
0.2% of the program — a quota-driven rollout is exactly what a small tail of
absurd sites indicates. Conversely, no distributional statistic can establish
it, which is why §4.1's finding (95% coverage) neither confirms nor refutes it.

The plan's A1/A3 are written as distributional analyses and so answer the wrong
question. The right instrument is a **screen**: rank all 83k by implausibility,
then verify the top of the list by eye. That is
[`reports/04-siting-screen/`](reports/04-siting-screen/), and the tail it has to
work with is real — 174 cooperatives with nobody within 5 km, 17,804 with an
empty own cell.

**The one thing that must be built into the write-up**: an implausible
surrounding has two causes — bad siting and a bad coordinate — and no automated
screen can separate them. Both are publishable, and they are *different
stories* ("they built it in a swamp" vs. "they don't know where it is"). Every
cited case needs imagery review first.

---

## 5. Architecture: yes to DuckDB, and here's the shape

Your joyplot pattern is the right one and it transfers almost unchanged. Two
tiers.

### 5.1 Tier 1 — offline prep (Python `duckdb`), output = small parquet

The point of this tier is to **never ship a GPKG to the browser**. Converting
Kontur costs one line and pays enormously:

| Format | Size |
|---|---|
| `kontur_population_ID.gpkg` | 172.4 MB |
| same data → parquet + zstd | **3.0 MB** |

That's 57× smaller, and it's smaller than joyplot's current 7.2 MB copy (zstd
over the default snappy, and dropping the empty geometry column). 3 MB is
comfortably a static asset — it can live in `data/web/` and be fetched by the
app directly.

Proposed tables, all parquet, all in `data/web/`:

| Table | Grain | Est. size | Built from |
|---|---|---|---|
| `population_h3.parquet` | H3 r8 cell | 3 MB | Kontur GPKG |
| `kopdes.parquet` | cooperative | ~4 MB | `locations.csv` + `h3_8` + `h3_7` + joined verification status |
| `kopdes_metrics.parquet` | cooperative | ~2 MB | remoteness band, catchment pop, neighbour count, minimarket flag |
| `village_stats.parquet` | village | ~3 MB | `stats_village.csv`, joined via the §1.5 two-hop key |
| `admin_stats.parquet` | province/district/subdistrict | <1 MB | the three stats CSVs, stacked with a `level` column |

Everything the app needs then totals ~13 MB, versus the current single 25 MB
`points.geojson`. Net win even before the analytics.

### 5.2 Tier 2 — in-browser (`duckdb-wasm`), copy joyplot's `lib/duckdb.ts`

Same manual-bundle setup, same `registerFileBuffer` + `read_parquet` flow. Two
upgrades over what joyplot does today:

- **`CREATE INDEX idx_h3` is close to useless in DuckDB** — it's a zonemap-backed
  ART index that doesn't accelerate hash joins, which is what a `USING (h3)` join
  compiles to. Drop it; DuckDB is already fast here. Your joyplot `initializeDuckDB`
  creates one, and it's costing load time for nothing.
- **Store `h3` as `UBIGINT`, not the 15-char hex string.** Kontur ships strings;
  convert once during prep. Halves the column and makes joins integer-comparisons.

### 5.3 The H3 extension works — use SQL, not Python loops

```sql
INSTALL h3 FROM community; LOAD h3;
SELECT h3_latlng_to_cell(-6.2, 106.8, 8);        -- → 614953583411986431 (UBIGINT)
SELECT len(h3_grid_disk(<cell>, 3));              -- → 37
```

Verified working on DuckDB 1.5.5 here. This means the entire A1/A2/B1 pipeline is
expressible in SQL with no Python H3 loop, which is what makes it portable to
duckdb-wasm. **Verify the h3 community extension has a wasm build matching your
duckdb-wasm version before committing the browser side to it** — if it doesn't,
fall back to `h3-js` for cell math (as joyplot already does) and keep DuckDB for
the joins.

**One trap, and it is easy to fall into.** Catchments overlap. Summing population
over per-cooperative k-rings double-counts massively:

| Approach at k=11 (~5 km) | Result |
|---|---|
| `SUM(population)` over all ring rows | **17,220,119,767** ← 62× the population of Indonesia |
| `SUM` over the **DISTINCT union** of cells | 276,989,563 ✓ |

Any "total population served" figure must be a union. Per-cooperative catchment
population (for the regression in §2) is the *other* query and legitimately does
double-count — just never sum that column.

Also watch materialisation cost: naive ring expansion at k=11 is 33 M rows and
~30 s. Do the union with a `DISTINCT` in SQL rather than building the row set in
pandas, or cap catchments at k≤6 where it's 10 M rows / 10 s.

### 5.5 Terrain and land cover are cheap — *sample* rasters, don't process them

This corrects the first pass, which called A3's DEM/slope work infeasible and
recommended dropping it. That was wrong, and the mistake was assuming a raster
job means downloading rasters.

You need elevation and land cover **at 83,000 points**, not over 1.9M km². Both
datasets are published as cloud-optimised GeoTIFFs on open S3 buckets, so GDAL
fetches a few KB around each point over HTTP range requests:

| Dataset | Resolution | Answers | Verified |
|---|---|---|---|
| Copernicus GLO-30 DEM | 30 m | elevation, local relief → "on a hilltop" | ✅ 1.5–4.6 s per tile open, then free |
| ESA WorldCover 2021 v200 | 10 m | cropland / forest / water / built-up → "in a paddy field" | ✅ same |

No download, no storage, no GDAL install beyond `rasterio`. Group the points by
tile so each tile opens once. **This makes "localise the analysis to one area"
unnecessary** — you can screen nationally and reserve the expensive, genuinely
local work (isochrones, imagery review) for the shortlist the screen produces.

The one thing that stays expensive is **routing**. Isochrones need a routable
network and a routing engine; that is worth standing up for a handful of case
studies, not for 83k points. The cheap national proxy is straight-line distance
to the nearest road *vertex*, which fits the H3 pattern exactly: extract
highways from the PBF once → vertices → H3 r10 → k-ring outward search. That
gives a national "no road within X" flag; true accessibility modelling then runs
only on the flagged cases.

### 5.4 What DuckDB does *not* solve

- **The 1.7 GB PBF.** DuckDB won't read PBF. You still need osmium/pyosmium to
  extract roads once; then write parquet and never touch the PBF again.
- **Point-in-polygon for E1.** DuckDB's `spatial` extension can do this
  (`ST_Within`), and it's the right tool — but it needs the boundary GeoJSON that
  `geo/run_pipeline.py` produces, and `geo/output/` is currently empty.
- **The §1.5 join.** No engine fixes a missing key.

---

## 6. Revised roadmap

The plan's Phase 0→3 ordering front-loads data quality and back-loads the
findings. Given §1.7 (coordinates are fine) and §4.1 (coverage is solved), I'd
reorder so that the two cheapest, highest-signal results land in week 1.

### Week 1 — establish the spine
- [x] Convert Kontur → `population_h3.parquet` (3.0 MB) — `reports/03-population-coverage/`
- [ ] Store `h3` as UBIGINT rather than the hex string
- [ ] **Move snapshots to `data/snapshots/YYYY-MM-DD/` and stop overwriting `data/raw/`** — the drift baseline depends on it (§2a)
- [ ] Make `extract_kopdes.py` tolerate per-endpoint failure (`/statistics/land-mapping` is 500ing today) and log which endpoints were down
- [ ] Build the §1.5 two-hop join, **and publish its match rate as a limitation**
- [ ] Resolve §1.2 (RAT contradiction) against raw API responses
- [ ] Correct the IDR 179.5T figure everywhere it appears

### Week 2 — the two cheap findings
- [ ] A1 remoteness bands + the 21.4%-in-unpopulated-cells statistic
- [ ] A2 **reframed as saturation**, leading with 95% @ 1.4 km
- [ ] B1 co-location at r7/r8/r9
- [ ] C2 land verification (already ready to write)

### Week 3–4 — the modelling
- [ ] Rare-event logistic: `any_activity ~ remoteness + catchment_pop + province`
- [ ] D3 NPWP/NIB, F2 savings dormancy, F3 island groups, D2 product mix
- [ ] E1 point-in-polygon once `geo/output/` exists

### Week 5+ — only if the data arrives
- [ ] B3, **conditional on scraping real Alfamart/Indomaret locations**
- [ ] A3 road access, conditional on extracting roads from the PBF
- [ ] C4 ROI, conditional on APBN/DIPA data
- [ ] B2, conditional on a pre-KDMP cooperative registry

Dropped outright: D1 as written, F1, A3's DEM/slope and island-isolation
sub-parts.

---

## 7. Hypotheses, restated

| # | Original | Verdict |
|---|---|---|
| H1 | Remote KDMP have lower transaction volumes | **Restate**: remote KDMP are less likely to have *ever* transacted. Volume is 97% zero. |
| H2 | Clustered KDMP have lower per-unit volume | **Restate** the same way, on the 6,381 r8-clustered cooperatives. |
| H3 | Construction ≠ transaction activity | Keep, but n=38 — descriptive only. |
| H4 | "Unhealthy" is driven by zero RAT | **Suspend** pending §1.2. And `health_score` is constant, so the original test is undefined. |
| H5 | >5% of coords outside claimed province | **Likely false** (§1.7). Verify and clear it. |
| H6 | KDMP near minimarkets sell a different mix | **Untestable** on OSM data (§4.2). Also note product data is province-level, so it cannot be joined to a per-KDMP proximity flag at all — this hypothesis has a grain mismatch independent of the coverage problem. |

A hypothesis worth adding — since first drafting this I measured it, and it is
the strongest result in the dataset ([`reports/02-zero-inflation/`](reports/02-zero-inflation/)):

> **H7 — confirmed.** Reported activity is concentrated to an extraordinary
> degree. **100 villages out of 84,624 (0.12%) carry 37.3% of all national
> transaction value; 1,000 carry 92.9%.**
>
> The program's reported output is not "low across the board" — it is absent
> everywhere except a few hundred sites. What those sites have that the other
> 82,000 don't is the research question the placement data can actually answer,
> and it should lead the investigation.

One more worth adding, because it is the claim the public critique actually
makes and no hypothesis currently states it:

> **H8**: A non-trivial number of KDMP sit somewhere no village shop could
> function — open water, closed forest, steep terrain, active paddy — and the
> existence of such sites, rather than their frequency, is evidence of a
> quota-driven rollout. Tested by screening, then case-by-case imagery review
> ([`reports/04-siting-screen/`](reports/04-siting-screen/)), and reported with
> the siting-vs-geocoding ambiguity stated explicitly (§4.4).

---

## Appendix: how these were measured

All figures above came from ad-hoc probes against `data/raw/*.csv`,
`data/population/kontur_population_ID.gpkg`, and
`data/osm/indonesia_minimarkets.gpkg` using pandas + duckdb 1.5.5 + h3 4.5.0
(installed into `.venv` during this review, along with pyarrow).

None of the probe scripts were committed — they were throwaway. If any figure
here matters enough to cite, re-derive it in a committed script under `analysis/`
so it's reproducible. The three worth promoting to real scripts first are the
§4.1 coverage table, the §1.5 join-rate check, and the §2 zero-inflation table.
