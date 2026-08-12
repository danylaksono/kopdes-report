# 13 — NPWP/NIB compliance: is the paperwork real, and is anyone operating under it?

**Run**: `python reports/13-compliance-npwp-nib/run.py` · No network · **Last run**: 2026-08-12
**Source**: `kopdes_stats_village.csv` (deduplicated) + national summary

D3 of `analytics-plan.md` — the "zombie" test. NPWP is the tax id, NIB is the
business identification number; in Indonesia a cooperative without an NIB
cannot legally transact. The question is whether the paperwork exists and
whether operations happen under it.

Totals reconcile with the ministry's own national summary: village sums differ
by **−2 (NPWP)** and **−1 (NIB)** — effectively exact.

## Finding 1 — the registration machinery worked for most, and failed hardest in Papua

[`compliance_by_level.csv`](compliance_by_level.csv) · [`compliance_by_province.csv`](compliance_by_province.csv)

| Document               | Cooperatives holding it | Share     |
| ---------------------- | ----------------------- | --------- |
| NPWP (tax id)          | 80,976                  | **97.1%** |
| NIB (business license) | 60,806                  | **72.9%** |

Compliance is identical at every admin level (the sums are the same numbers
rolled up). Province spread of NIB: **99.3%** (DKI Jakarta) down to **5.6%**
(Papua Pegunungan); Papua Selatan has only **40.5%** NPWP. The registration
machinery itself failed in Papua — 27% of villages nationally have no
cooperative holding an NIB, and a cooperative without NIB cannot legally
transact.

## Finding 2 — the zombie test: the license exists, the operations don't

[`nib_vs_transaction.csv`](nib_vs_transaction.csv) · per village

|            | no transaction  | transaction   |
| ---------- | --------------- | ------------- |
| **NIB**    | 58,230 (70.10%) | 2,493 (3.00%) |
| **no NIB** | 22,323 (26.87%) | 23 (0.03%)    |

- **70.1% of villages hold the NIB and report no transaction.** The state has
  licensed them as businesses; they show no business.
- Only **23 villages (0.03%)** report a transaction _without_ an NIB — nobody
  is operating outside the licensing system.
- 26.9% have neither license nor transaction.

Read with [02](../02-zero-inflation/) and [11](../11-savings-behaviour/): the
administrative layer (accounts 96%, NPWP 97%) and the licensing layer (NIB 73%)
are populated, while the operating layer (transactions 3%, wajib dues 9%) is
not. The zombie is not "paperwork missing"; it is "paperwork present, operations
absent".

## Caveats

- Village-level aggregation: a village counts as "NIB" if _any_ cooperative in
  it holds one. The 70.1% figure is therefore a lower bound on licensed-but-
  silent villages in cooperative terms.
- `npwp_count`/`nib_count` count documents held, not necessarily current/valid
  ones.
- The cross-tab is village-level: a village with a transaction and a village
  with an NIB may be different cooperatives within the same village.
- The zero-meaning caveat (01) applies to the transaction side.

## Output for later

[`compliance_by_province.csv`](compliance_by_province.csv) and
[`nib_vs_transaction.csv`](nib_vs_transaction.csv) are the "paperwork vs
operations" two-liner for the report.
