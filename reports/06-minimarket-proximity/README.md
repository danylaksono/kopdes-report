# 06 — Minimarket proximity: were KDMP built on top of existing retail?

**Reproduce**: `KOPDES_RAW=data/snapshots/2026-08-13 python reports/06-minimarket-proximity/run.py` ·
No network · **Last run**: 2026-08-15
**Source**: `data/osm/indonesia_minimarkets.gpkg` (10,580 POIs) + Kontur population + the
road cell index from [05](../05-road-access/), with KDMP coordinates from the
**2026-08-13** snapshot. Hashes in [`_source.json`](_source.json).

> **This report is built around two known problems in its own data**: the source
> is incomplete and urban-biased (§2), and it is not actually a minimarket
> dataset until it is re-tiered (§1). Read both before quoting any number. Every
> forward figure is a **lower bound**, never a point estimate.

## 1. What is actually in this dataset

The file is named `minimarkets` but it is an Overpass pull of
`shop=convenience|supermarket|department_store`. Before measuring anything, it
has to be split into formats that a village cooperative actually competes with
([`retail_tiers.csv`](retail_tiers.csv)):

| Tier                                 | POIs      | Share     | Used for proximity? |
| ------------------------------------ | --------- | --------- | ------------------- |
| 0 traditional warung / toko          | 858       | 8.1%      | no — see §5         |
| **1 convenience / minimarket**       | **7,617** | **72.0%** | **yes, primary**    |
| 2 supermarket (town-level)           | 1,838     | 17.4%     | reported separately |
| 3 department store (not food retail) | 267       | 2.5%      | excluded            |

**28% of the file is not a minimarket.** A Matahari or a Ramayana is not
competition for a village cooperative selling rice and LPG, and a Hypermart
serves a town, not a desa. An earlier version of this report measured against
all 10,580 POIs and consequently **overstated every forward figure by roughly
a quarter** (e.g. 3.22% within 500 m, against 2.48% correctly tiered).

`run.py` also repairs `scripts/download_osm.py`'s `classify_brand()`, which
misses spelling variants and regional chains and dumps them in `other`:
76 Alfamart-group (`Alfa Express`, `Alfa Midi`), 54 Bali chains (Pepito, Coco),
33 Yomart, 17 Hero, 10 7-Eleven.

## 2. The coverage problem, measured

OSM POI coverage in rural Indonesia is poor **and urban-biased** — mapper
density tracks urbanisation, the opposite of where KDMP sit. A naive point
estimate from this source would undercount by an unknown margin, in the
direction that **exonerates the programme**.

**Deficit against published outlet counts**
([`osm_brand_coverage.csv`](osm_brand_coverage.csv)):

| Brand     | In OSM | Published outlets | OSM share |
| --------- | ------ | ----------------- | --------- |
| Indomaret | 3,030  | ~22,000           | **13.8%** |
| Alfamart  | 2,181  | ~20,000           | **10.9%** |

> Published totals are hardcoded in `run.py` as `PUBLISHED_OUTLETS`, from
> company reporting. **Verify and cite before publication.** No downstream
> number depends on them — they size the deficit statement only.

**Urban bias, measured from the data itself**, needing no external benchmark
([`urban_bias_diagnostic.csv`](urban_bias_diagnostic.csv)):

|                         | Median population in own 400 m cell | Share in a zero-population cell |
| ----------------------- | ----------------------------------- | ------------------------------- |
| KDMP                    | 261                                 | 21.3%                           |
| OSM minimarket (tier 1) | **3,786**                           | **0.1%**                        |

Mapped minimarkets sit in cells ~15× more populous than cooperatives do, and
essentially never in an empty one. Provincial density says the same
([`osm_density_by_province.csv`](osm_density_by_province.csv)): 365 minimarkets
per 100 KDMP in DKI Jakarta, 0.15 in Sulawesi Barat, **0 in Papua Tengah**.

## 3. Forward direction — lower bounds only

**At least** this many KDMP have a mapped tier-1 minimarket nearby
([`kdmp_near_minimarket_lower_bounds.csv`](kdmp_near_minimarket_lower_bounds.csv)):

| Within | Cooperatives (≥) | Share (≥) |
| ------ | ---------------- | --------- |
| ~500 m | 2,068            | **2.5%**  |
| ~1 km  | 4,150            | 5.0%      |
| ~2 km  | 7,425            | 8.9%      |
| ~5 km  | 16,505           | 19.8%     |

Supermarkets separately
([`kdmp_near_supermarket_lower_bounds.csv`](kdmp_near_supermarket_lower_bounds.csv)):
1.0% within ~500 m, 2.6% within ~1 km, 12.6% within ~5 km.

Restricting to the 27 provinces where OSM retail density is at least a quarter
of the national median barely moves it — 2.9% / 5.8% / 10.4% / 23.1%
([`scope_restricted_lower_bounds.csv`](scope_restricted_lower_bounds.csv)).

**These are floors and the true values are materially higher.** Write "at least
2.5%", never "only 2.5%".

## 4. Reverse direction, and the null models that make it interpretable

Turning the question around removes most of the coverage bias, because the
statistic is conditional on the store existing
([`minimarket_near_kdmp.csv`](minimarket_near_kdmp.csv)): **78.3% of mapped
minimarkets have a KDMP within ~1 km**, 95.7% within ~2 km.

On its own that proves nothing — KDMP are one-per-village and cover 95% of the
population within ~1.4 km ([03](../03-population-coverage/)), so _any_ populated
point has one nearby almost by construction. Three controls, each matched to the
minimarket count ([`null_model_comparison.csv`](null_model_comparison.csv)):

- **Population-weighted random** — a location sampled proportional to Kontur population.
- **Road-constrained population-weighted random** — a location on a non-track
  road cell inside a populated area, i.e. a plausible retail site.
- **Road-constrained, population-_matched_** — the same road-cell pool, but
  sampled to reproduce the minimarkets' own population distribution. **This is
  the primary control.**

### Why the third null exists (corrected 2026-08-15)

The road+pop null was described in this README as answering "if minimarkets and
KDMP both simply sit on the village road, that alone would manufacture apparent
co-location." It only half answered it. Measured on the same grid
([`null_density_match.csv`](null_density_match.csv)):

| Points                        | Median population in own 400 m cell |
| ----------------------------- | ----------------------------------- |
| Minimarket (tier 1)           | 3,786                               |
| Null: road + pop-**weighted** | **2,374**                           |
| Null: road + pop-**matched**  | 3,786                               |

Weighting by population is not the same as matching it. The old null stood in
for the minimarkets in places roughly a third less dense, and since KDMP
coverage rises with density, that gap was scored as co-location. Matching the
distribution removes it, and takes the ~500 m excess from **+9.6 to +6.7 pts**.

| Within | Minimarkets | Pop null | Road+pop null | **Road+pop-matched** | **Excess (primary)** |
| ------ | ----------- | -------- | ------------- | -------------------- | -------------------- |
| ~500 m | 43.8%       | 27.3%    | 34.7%         | 37.1%                | **+6.7 pts**         |
| ~1 km  | 78.3%       | 62.2%    | 70.9%         | 74.6%                | **+3.7 pts**         |
| ~2 km  | 95.7%       | 87.0%    | 92.9%         | 94.2%                | +1.5 pts             |
| ~5 km  | 99.6%       | 98.2%    | 99.4%         | 99.4%                | +0.2 pts             |

The residual is real but modest, and it **decays with distance**
(+6.7 → +3.7 → +1.5 → +0.2) — the signature of genuine short-range catchment
overlap rather than a global artefact.

### The nulls are draws, not constants

Two further corrections from the same pass:

- **The published figure was one sample.** `null_stability.csv` redraws each
  null 40 times: the ~500 m excess spans **5.7–7.7** for the matched null and
  **8.2–10.4** for the old road null. Quote the mean and the range, never a
  single draw to one decimal. The figures the site prints come from
  [`null_excess_published.csv`](null_excess_published.csv) for exactly this
  reason; the ~2 km and ~5 km rows there are still single draws, and say so.
- **The fixed seed never made this reproducible.** The nulls draw integer
  indices into DuckDB result sets, and DuckDB does not guarantee row order, so
  re-running with no code change to the null moved the ~500 m road null from
  34.41% to 33.79%. The candidate queries now carry `order by`, and two
  consecutive runs are byte-identical.

An earlier robustness note claimed these figures were "essentially unchanged by
the §1 re-tiering (previously +9.4 / +6.7 / +2.3 / +0.1 on the untiered set)".
That comparison is withdrawn: the untiered run exists nowhere in the repo, and
the numbers it quoted are indistinguishable from ordinary redraw noise.

### What this does and does not establish

**Does**: KDMP and existing modern retail overlap at short range more than
chance placement on the road network would produce.

**Does not**: establish intent, or cannibalisation. Both formats plausibly
target the same village focal point — market, junction, balai desa — a sub-cell
feature no null at this resolution can control for. And cannibalisation is a
claim about _trade_, which needs the transaction data that is 97% zero
([02](../02-zero-inflation/)). Proximity is a precondition for competition, not
evidence of it.

## 5. The limitation that matters most: the real incumbent is invisible

The competitor a village cooperative actually displaces is the **warung / toko
kelontong**, not an Alfamart. OSM has **858 of them nationally** — against a
true population in the millions (BPS counts micro and small retail units in the
millions, not thousands).

So "cannibalisation of existing retail", properly framed, is **largely
untestable with this data**. What §3 and §4 measure is one visible slice —
branded modern retail — of a much larger informal-retail question that OSM
cannot reach. This belongs in the write-up as a **scope statement**, not as a
buried caveat: otherwise the paper implicitly claims to have tested competition
when it has tested a minority of it.

Sourcing traditional retail would need a different instrument entirely — BPS
PODES village-facility counts, or field survey.

## Caveats

- Every forward number is a lower bound of unknown tightness (§2).
- Ring distance is a band: adjacent r10 cell centres are ~132 m apart, so
  `k × 0.132 km` is approximate and degrades slightly with latitude.
- Province is assigned to each POI from its **nearest KDMP**, not a boundary
  polygon — adequate for a density diagnostic, not for exact attribution.
- The nulls are population- and road-weighted but otherwise uniform; they do not
  model the commercial siting logic a retail chain actually uses, so the residual
  excess is an **upper bound** on deliberate co-location.
- Tier assignment leans on the `shop` tag and brand names; the 3,450 unbranded
  `other` POIs are assigned by `shop` tag alone.
- OSM extract is a Geofabrik/Overpass snapshot from 2026-08-07.

## Outputs

| File                                                                               | Contents                                         |
| ---------------------------------------------------------------------------------- | ------------------------------------------------ |
| [`retail_tiers.csv`](retail_tiers.csv)                                             | what the dataset actually contains               |
| [`osm_brand_coverage.csv`](osm_brand_coverage.csv)                                 | OSM counts vs published outlets                  |
| [`urban_bias_diagnostic.csv`](urban_bias_diagnostic.csv)                           | population context, KDMP vs minimarket           |
| [`osm_density_by_province.csv`](osm_density_by_province.csv)                       | minimarkets per 100 KDMP                         |
| [`kdmp_near_minimarket_lower_bounds.csv`](kdmp_near_minimarket_lower_bounds.csv)   | forward, tier 1                                  |
| [`kdmp_near_supermarket_lower_bounds.csv`](kdmp_near_supermarket_lower_bounds.csv) | forward, tier 2                                  |
| [`minimarket_near_kdmp.csv`](minimarket_near_kdmp.csv)                             | reverse direction                                |
| [`null_model_comparison.csv`](null_model_comparison.csv)                           | both nulls                                       |
| [`scope_restricted_lower_bounds.csv`](scope_restricted_lower_bounds.csv)           | 27-province subset                               |
| `kopdes_minimarket_distance.csv`                                                   | per-cooperative (gitignored, rebuilds in ~1 min) |
