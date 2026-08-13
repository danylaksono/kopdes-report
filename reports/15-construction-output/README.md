# 15 — Construction progress vs economic output

**Run**: `python reports/15-construction-output/run.py` · No network · **Last run**: 2026-08-12
**Source**: `kopdes_province_rat_and_construction.csv` + `kopdes_stats_province.csv`

C1 of `analytics-plan.md`, deliberately downgraded. n = 38 provinces, no
confounder control — the plan-review's verdict is explicit: _"a correlation on
38 points with no confounder control is a scatter plot, not evidence."_ This
report is that scatter plot, printed because two structural facts in the same
file need stating once, not because it proves anything.

## Structural fact 1 — fewer than a quarter of cooperatives are at 100% construction

[`construction_vs_output.csv`](construction_vs_output.csv)

- **20,221 of 83,379 cooperatives (24.3%)** are at 100% construction.
- **38,005 (45.6%)** have _any_ construction stage recorded — more than half
  of the program has no construction record at all.
- ~30% are at ≥76% (built, or nearly so).

## The scatter, stated honestly

| Province-level correlation (n = 38)          | Spearman  |
| -------------------------------------------- | --------- |
| % at 100% construction vs Rp per cooperative | **0.189** |
| % with any stage vs Rp per cooperative       | 0.170     |

Weakly positive, and confounded: both variables track economic geography. Java
Timur/Tengah top the construction table _and_ the output table; Papua is at
the bottom of both. The counter-example that breaks a causal reading is
**DKI Jakarta**: 2.6% at 100% construction (its construction data is barely
recorded) but the **highest** output per cooperative in the country
(Rp 17.5M). Construction data being missing tracks where the program stopped
recording, not where it stopped building.

## Verdict

No claim beyond description. What is supportable: construction completion and
reported output co-vary across provinces in the direction of "built and
operating are both Java things", and the construction channel does not support
a picture of a fully delivered program — a quarter completed, half undocumented.

> **Correction (2026-08-13):** an earlier version of this report claimed RAT
> compliance was zero in all 38 provinces. That was a field misread — `total_rat`
> from the province readiness endpoint is empty on every pull, while the real
> RAT channel (`rat_count` in the stats file) shows ~60% compliance. See
> [16-rat-compliance](../16-rat-compliance/).

## Caveats

- n = 38, no confounders; the correlation is an island/geography artefact
  ([14](../14-island-comparison/)).
- `build_*` columns are counts of cooperatives per stage; coops with no stage
  recorded are neither "not started" nor "unreported" — they are simply absent
  from the construction channel.
- `economic_total_value` in the construction file duplicates the province
  transaction figure; the province stats file was used as canonical.
