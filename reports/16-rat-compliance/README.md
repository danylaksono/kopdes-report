# 16 — RAT compliance: the "zero" was a field misread

**Reproduce**: `KOPDES_RAW=data/snapshots/2026-08-13 python reports/16-rat-compliance/run.py` ·
No network · **Last run**: 2026-08-15
**Source**: `kopdes_stats_province.csv` (`rat_count`) from the **2026-08-13** snapshot,
plus `reports/15-construction-output` for the old claim. Hashes in [`_source.json`](_source.json).

## The correction this report exists to make

Every report written before 2026-08-13 — and the published report site — stated
that **RAT (the annual member meeting) compliance is zero in all 38 provinces**.
That claim rested on `total_rat` in `kopdes_province_rat_and_construction.csv`,
a field sourced from the per-province `/statistics/national-readiness/province/{id}`
`rat_summary` object, which returns all zeros (period 2024) on every pull.

**That field is the wrong one, and the claim is false.** The real RAT channel is
`rat_count` in the stats endpoint (`kopdes_stats_province.csv`), which is what
the ministry's own dashboard displays per province ("Koperasi Telah Melaksanakan
RAT"). `analytics-plan-review.md` flagged exactly this contradiction on 2026-08-09
("C3 cannot be written up until this is resolved… a coin flip between 'total
governance failure' and 'field misread'") and report 15 published the misread
anyway. This report closes the blocker.

## Finding 1 — 60% of cooperatives have conducted an RAT

[`rat_by_province.csv`](rat_by_province.csv)

|                           | Cooperatives | RAT conducted | Share     |
| ------------------------- | ------------ | ------------- | --------- |
| **National (2026-08-13)** | 83,379       | **50,200**    | **60.2%** |

The count is stable and real, not a one-off artefact: 50,174 (08-05 baseline) →
50,188 (08-09 snapshot) → 50,200 (live 08-13 pull, where the dashboard displays
the same 50,200). RAT compliance is a populated, moving channel — the opposite
of the "empty governance channel" the plan feared.

The dashboard's own breakdown of the 50,200: 5,297 RAT _dilaporkan_ (reported)
plus 44,903 _diverifikasi Dinas_ (verified by the service) = 50,200 "telah
melaksanakan". The `rat_count` field is the "telah melaksanakan" number.

## Finding 2 — the gradient is the familiar Java/east-Indonesia one

Compliance runs 99.3% (DKI Jakarta) and 98.9% (Sumatera Barat) down to **6.1% (Papua
Pegunungan)**, 16.0% (Papua Selatan), 21.3% (Papua Barat Daya). The same
eastern-Indonesia shortfall that shows up in transactions (14), construction
(15) and compliance (13) shows up in governance too. And it tracks activity:
Spearman(rat compliance, transaction value per cooperative) = **0.438** (n = 38) —
governance and operations co-vary, both with economic geography.

## Finding 3 — data availability is province-level only

`rat_count` is populated **only at province level**. The district, subdistrict
and village stats all return 0 on every pull (verified 08-05, 08-09, live
08-13). No finer-grained RAT analysis is possible from this API — do not attempt
a village-level RAT map.

## What this means for earlier work

- **Report 15's "Structural fact 1 — RAT compliance is zero everywhere" is
  withdrawn.** Construction analysis stands on its own; the RAT claim is wrong.
- **The "all provinces unhealthy" health-score story needs re-checking.** If
  RAT feeds the health index, a 60% RAT channel changes what "unhealthy" means.
  Health scoring only covers 37.6% of cooperatives (per `analytics-plan-review.md`
  §1.3), which is a separate data problem — but it should not be read as "no
  governance anywhere".
- The remaining ~40% (≈33,200 cooperatives, 08-05) have **not** conducted an RAT
  (dashboard: 18,721 belum RAT + 14,458 draft). That is still a real, large gap —
  it is just not "zero", and it is concentrated in eastern Indonesia.

## Caveats

- `rat_count` semantics come from the dashboard label ("Koperasi Telah
  Melaksanakan RAT"); the field name alone does not prove what was counted.
- n = 38 for the correlation; no confounder control — the ρ = 0.438 is
  descriptive, consistent with the island/geography artefact in 14, not causal.
- A cooperative "conducting" an RAT is a report to SIMKOPDES, not an audited
  meeting. The same zero-meaning caveat (01) applies in reverse: the count is
  "reported", never "independently verified".
- The 08-13 corroboration figures are from a live API pull, not the committed
  CSVs; re-running this report later will legitimately produce a different
  national count.

## Outputs

| File                                         | Contents                                                 |
| -------------------------------------------- | -------------------------------------------------------- |
| [`rat_by_province.csv`](rat_by_province.csv) | per-province rat_count, compliance %, tx per cooperative |
