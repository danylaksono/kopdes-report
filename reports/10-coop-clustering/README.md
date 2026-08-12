# 10 — KDMP-to-KDMP clustering: how much does the program overlap with itself?

**Run**: `python reports/10-coop-clustering/run.py` · No network · **Last run**: 2026-08-12
**Source**: `kopdes_locations.csv`, `kopdes_land_assets.csv`, `kopdes_stats_village.csv`,
08's [`suspect_coordinates.csv`](../08-exact-geometry/suspect_coordinates.csv)

This is B1 of `analytics-plan.md`: _how many KDMP are built close enough to
each other that they compete for the same population?_ The plan proposed an
83k × 83k pairwise distance matrix — 3.5 billion pairs, which is why this
report does not build one.

## The method, in one paragraph

Three instruments, in order of how defensible the number is. **(1) Exact
nearest-neighbour distance**: a `cKDTree` on the unit sphere gives every
cooperative's true geodesic distance to its closest sibling, so the
"within 500 m / 1 km / 2 km / 5 km" counts are exact. **(2) H3 co-location**:
how many cooperatives share the same H3 cell at r7/r8/r9 — the plan-review's
recommended replacement for the pairwise matrix, which reproduces that review's
published numbers exactly. **(3) Clusters**: groups of ≥2 cooperatives in the
same r8 cell (~1 km hexagon), which is the plan's "densest KDMP clusters"
deliverable at the finest resolution that does not chain (see Finding 5).

Performance is joined through the two-hop village link (cooperative name →
land asset → village stats), which reaches **79.3%** of cooperatives.

## The load-bearing caveat, up front

**821 cooperatives (1.0%) are excluded from every "clean" number here and
reported separately in [`coord_artifacts.csv`](coord_artifacts.csv):**

- **19** have impossible coordinates (08's lat-sign flips and the Papua garbage
  point);
- **802** share an _exact duplicate coordinate_ with another cooperative — 388
  groups, up to 11 cooperatives at one point, concentrated in ACEH (119),
  PAPUA PEGUNUNGAN (82), JAWA BARAT (62).

Exact duplicates are the signature of a geocoding fallback — cooperatives
snapped to an admin centroid, not physically co-located. **At the fine r9 scale
(~350 m), 64% of apparent co-location is these artifacts.** Any sentence about
cooperatives "on top of each other" must be written against the clean set.

## Finding 1 — most KDMP have a sibling nearby; few are stacked on top of each other

[`nn_bands.csv`](nn_bands.csv) · [`nn_within.csv`](nn_within.csv) · exact geodesic, 82,521 clean cooperatives

| Another cooperative within | Cooperatives | Share      |
| -------------------------- | ------------ | ---------- |
| **500 m**                  | 3,826        | **4.64%**  |
| **1 km**                   | 18,238       | **22.10%** |
| **2 km**                   | 48,596       | **58.89%** |
| **5 km**                   | 75,291       | **91.24%** |

Read both ends. 91% having a sibling within 5 km is the program's
1-per-desa saturation in populated Indonesia — the same geometry that produced
03's "95% of people within 1.4 km of a KDMP". But it is not nothing: **one in
five cooperatives has another one within a kilometre**, and 4.6% within 500 m —
which is the real footprint of the "they built them too close together" claim.

## Finding 2 — true co-location is 6.7% of cooperatives, and most of it is pairs

[`co_location.csv`](co_location.csv) (clean set) · [`clusters.csv`](clusters.csv) · [`cluster_size_distribution.csv`](cluster_size_distribution.csv)

| H3 res | cell edge | coops sharing a cell with ≥1 other | share    | max in one cell |
| ------ | --------- | ---------------------------------- | -------- | --------------- |
| r7     | ~1.2 km   | 34,966                             | 42.4%    | 23              |
| **r8** | ~0.5 km   | 5,546                              | **6.7%** | **17**          |
| r9     | ~0.2 km   | 450                                | 0.55%    | 12              |

5,546 cooperatives sit in 2,501 r8 cells with at least one sibling. The
distribution is dominated by pairs — 2,100 cells hold exactly 2, and only 8
cells hold 10 or more. The maximum is **17 cooperatives in one ~1 km cell**.

## Finding 3 — the densest clusters are not where you would expect

[`densest_cells.csv`](densest_cells.csv) — top 20 r8 cells by cooperative count

| Size   | Where                                                                                        | Notes                                 |
| ------ | -------------------------------------------------------------------------------------------- | ------------------------------------- |
| **17** | PAPUA PEGUNUNGAN, Kab. Jayawijaya (Wamena area)                                              | 17 _recorded_ at one spot, ~1 km cell |
| 12     | PAPUA PEGUNUNGAN, Kab. Lanny Jaya                                                            |                                       |
| 8      | ACEH, Kab. Aceh Barat Daya                                                                   | all "Syariah" named                   |
| 7      | JAMBI, Kab. Kerinci                                                                          |                                       |
| 6 ×4   | Manado & Sungai Penuh (kelurahan coops in city centres), Kerinci, and a Papua (Pyramid) cell |                                       |

None are in Java's cities. The densest cell is in the Papua highlands, which is
the same _badly sited or badly geocoded_ ambiguity as 04: a cluster of 17
distinct-but-adjacent coordinates in the Wamena area is more plausibly many
desa geocoded to a town than 17 physically co-located buildings. **Every cell
in this table needs imagery before any name is cited.** The `member_cooperatives`
column is the checklist.

## Finding 4 — clustering carries no measurable performance penalty (null result)

[`cluster_vs_isolated.csv`](cluster_vs_isolated.csv) · [`cluster_size_vs_value.csv`](cluster_size_vs_value.csv)
· village-linked cooperatives only (79.3%)

| group                    | n linked | pct reporting a transaction | mean Rp/coop | share of linked value |
| ------------------------ | -------- | --------------------------- | ------------ | --------------------- |
| clustered (same r8 cell) | 3,928    | **3.92%**                   | 2.35M        | 5.84%                 |
| isolated                 | 61,516   | **3.47%**                   | 2.42M        | 94.16%                |
| all                      | 65,444   | 3.50%                       | 2.42M        | 100%                  |

Spearman correlation between cluster size and per-cooperative transaction
value: **−0.016** over all clustered cooperatives, **+0.045** over those
reporting at all. There is no signal in either.

The plan's B1 hypothesis — _clustered KDMP have lower per-unit transaction
volumes_ — **is not supported**. Cooperatives that share a cell report at the
same rate as isolated ones (if anything slightly more often), and being in a
bigger cluster does not depress the per-cooperative figure. Read this with 02's
caveat in mind: the outcome is 97% zero, so "no penalty" is the strongest
statement this data permits, not a measured absence of competition.

## Finding 5 — why there is no DBSCAN-style cluster map

[`chaining_check.csv`](chaining_check.csv)

A density-connected partition (the plan's DBSCAN, eps≈2 km) is not a meaningful
object in this data. At any linking radius, components chain across dense Java:

| linking radius (r8 k-rings) | coops inside a ≥3 component | largest component |
| --------------------------- | --------------------------- | ----------------- |
| ~0.9 km                     | 25.5%                       | 631               |
| ~1.4 km                     | 55.7%                       | 2,652             |
| ~1.8 km                     | 82.3%                       | 23,129            |

The 23k-member component is essentially "all of Java". That is itself a finding:
**the populated half of Indonesia is a near-continuous field of KDMP, not a set
of discrete clusters** — the program saturated the landscape rather than
concentrating in pockets. Same-cell co-location (Finding 2) is the honest unit
for "on top of each other".

## Caveats

- "Co-located" here means _recorded at_ the same cell, not _built_ there. The
  821 artifacts show how often the data itself is the explanation; dense Papua
  cells are the open question. Same imagery bar as 04.
- An r8 cell is ~0.46 km edge length; two cooperatives in one cell can be up to
  ~0.9 km apart (opposite corners). The nearest-neighbour distances are exact
  geodesic; the cell-based statements are approximate by construction.
- The performance comparison covers only the 79.3% of cooperatives reached by
  the two-hop village link. Clustered and isolated coops are both ~6% of their
  respective sets, so the comparison is not imbalanced by reach.
- A zero transaction is "has not **reported**", never "is inactive" (01).
- [`nn_distances.csv`](nn_distances.csv) is the clean set only;
  [`coord_artifacts.csv`](coord_artifacts.csv) lists every excluded
  cooperative and why.

## Output for later

[`nn_distances.csv`](nn_distances.csv) is per-cooperative and map-ready:
`m_to_nearest_other`, `nn_band`, `cluster_id`, `cluster_size`, plus the
village-linked performance columns. It is the intended input for a screengrid
view showing self-overlap alongside the population and retail layers.
