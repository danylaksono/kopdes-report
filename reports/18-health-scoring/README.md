# 18 — The health index: what "unhealthy ×38" actually says

**Run**: `python reports/18-health-scoring/run.py` · No network · **Last run**: 2026-08-13
**Source**: `kopdes_stats_province.csv` (`health_score`, `health_status`,
`average_health_index`, `health_total_cooperative`, `healthy_count`,
`fairly_healthy_count`, `unhealthy_count`)

## The claim this report re-checks

The project plan and data notes carried a one-line health story: **"all 38
provinces are unhealthy"**, health scores clustered 51–57, "likely driven by
zero RAT". Report 16 — which established that RAT is **60%, not zero** — flagged
that this needed re-checking: if RAT feeds the health index, a populated RAT
channel changes what "unhealthy" means.

The short version: the "×38 unhealthy" label is an **artifact**, the real index
says something narrower and more interesting, and the "driven by zero RAT"
hypothesis is **rejected**. This report does not change any published claim —
the site never made the "×38 unhealthy" claim — it closes the last unresolved
item in the evidence base.

## Finding 1 — "unhealthy ×38" is a constant, not a finding

[`health_index_by_province.csv`](health_index_by_province.csv)

`health_score` = **30 for all 38 provinces** and `health_status` = **"unhealthy"
for all 38** — zero variance, from the map endpoint
(`/cooperative-financial/statistics/national/map`), which returns province
centroids, not a scored discriminator. You cannot compare provinces on a
constant. Anyone quoting "all provinces unhealthy" is quoting a placeholder,
not a measurement.

The _real_ per-province index the dashboard computes is `average_health_index`:
**50–57, mean 53.2** (DKI Jakarta 57, Jawa 55–56 cluster, Papua Selatan 50).
That is the 7-point spread the old note called "clustered 51–57".

## Finding 2 — the bigger fact is coverage: 62% of cooperatives were never scored

|                                |                              |
| ------------------------------ | ---------------------------- |
| Scored cooperatives (national) | 31,354 of 83,379 = **37.6%** |
| Never scored                   | **52,025 (62.4%)**           |
| Healthy                        | 697 (2.2% of scored)         |
| Fairly healthy                 | 2,089 (6.7%)                 |
| Unhealthy                      | 28,568 (**91.1%**)           |

Scoring is wildly uneven: **DKI Jakarta scored 79.1%** of its cooperatives
(212/268, index 57), while **Papua Pegunungan scored 0.7%** (16/2,387) and Papua
Tengah 4.2% (51/1,202). The province "unhealthy" label is computed on the 38%
that were scored — and in Papua Pegunungan that is 16 cooperatives out of 2,387.
Why 62% were never scored (too new? no financial data at all?) is not exposed by
this API — but the "all provinces unhealthy" reading of it is not defensible.

## Finding 3 — what the index actually tracks: completeness first, compliance second

[`index_drivers.csv`](index_drivers.csv) — Spearman vs `average_health_index`, n = 38

| Driver                               | ρ          | p       |
| ------------------------------------ | ---------- | ------- |
| scored_share (share of coops scored) | **+0.850** | <0.0001 |
| savings per cooperative              | +0.822     | <0.0001 |
| NIB share                            | +0.807     | <0.0001 |
| **RAT compliance**                   | **+0.801** | <0.0001 |
| transaction value per coop           | +0.487     | 0.0019  |
| NPWP share                           | +0.351     | 0.031   |
| number of cooperatives               | +0.175     | 0.293   |

The strongest correlate is **how many cooperatives got scored at all**
(ρ = 0.85) — a completeness artifact, not a health signal: provinces that scored
more of their coops end up with higher average indices. Savings, NIB and RAT
all co-vary at ~0.80, which is the familiar economic-geography gradient (14, 15,
16). Crucially, the RAT and completeness correlations **survive controlling for
island** (within-island ρ = 0.56 and 0.55, both p < 0.001) — they are not just
Java-vs-Papua.

## Finding 4 — report 16's question, answered

Report 16 asked whether a real (60%) RAT channel changes what "unhealthy"
means. It does not rescue the old claim, but it does kill the hypothesis behind
it:

- RAT is **not** zero — it is 60% nationally — yet **91.1% of scored
  cooperatives are still "unhealthy"** on the ministry's own rubric.
- So "unhealthy" is **not** "driven by zero RAT" (analytics-plan H4). RAT
  co-varies with the index (ρ = 0.80 full, 0.56 within-island) but the index is
  dominated by _who got scored_ (ρ = 0.85) and by the same compliance/savings
  gradient that shows up in every measure.
- The defensible reading: the health index mostly reflects **data completeness
  and administrative formality**, not an independent health assessment. A
  low index says "this province's cooperatives have not reported the inputs the
  index needs", which is a finding about the data, not necessarily about the
  cooperatives.

## What this means for the report

- **Do not publish "all 38 provinces unhealthy"** — it is a constant-field
  artifact. The health index belongs in the methodology appendix, with the
  coverage caveat, not in the narrative.
- The honest one-liner, if health is mentioned at all: _the ministry's health
  index covers 38% of cooperatives, and even among those, 91% score
  "unhealthy" — but the score is dominated by who reported, not by an
  independent measure of health._
- The 52,025 never-scored cooperatives are worth naming as a coverage gap
  (same class of caveat as "no _mapped_ house" in 17).

## Caveats

- n = 38, all correlations descriptive and confounded with economic geography
  (the island control only partials out the coarsest group).
- The index formula is **not exposed** by the API. "What tracks the index"
  (Finding 3) is correlation, not the rubric.
- `health_score`/`health_status` on the map endpoint may mean something in the
  dashboard UI that this static field does not encode; either way it carries no
  province-to-province information.

## Outputs

| File                                                           | Contents                                                                               |
| -------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| [`health_index_by_province.csv`](health_index_by_province.csv) | per-province index, coverage, healthy/fairly/unhealthy counts, drivers                 |
| [`index_drivers.csv`](index_drivers.csv)                       | Spearman correlations of index vs province stats (full + within-island in the run log) |
