# 01 — Snapshot drift: are the zeros real, or just not entered yet?

**Run**: `python reports/01-snapshot-drift/run.py` · **Hits the live API** ·
**Last run**: 2026-08-09 against the 2026-08-05 snapshot

## Why this matters

97% of villages report `transaction_value = 0` (see
[02-zero-inflation](../02-zero-inflation/)). SIMKOPDES is a live system under
active rollout, so that zero has two readings with opposite implications:

- **(a) genuine inactivity** — the cooperative exists on paper and does nothing.
- **(b) reporting lag** — the activity happens but hasn't been entered yet.

Almost every hypothesis in [`analytics-plan.md`](../../analytics-plan.md) that
uses transaction volume as an outcome depends on which of these is true.

## Finding 1 — there is no per-record timestamp. Diffing snapshots is the only instrument.

I probed the live API to check whether the extractor was dropping any freshness
field. It isn't — the API simply doesn't carry one:

| Endpoint | Fields returned per record |
|---|---|
| `/cooperatives/get-all-nested` | `cooperative_id`, `name`, `latitude`, `longitude` — **that's all** |
| `/cooperative-assets/get-all` | `asset_id`, `cooperative`, `status`, `surveyor`, `latitude`, `longitude` |
| `/statistics/national-readiness/subdistrict/{id}` | carries an `updated_at`… |

…but that `updated_at` is **the API's response time, not a data-freshness
stamp**. Ten subdistricts queried in sequence returned
`2026-08-10T01:12:19` … `:23` — incrementing with the wall clock as the
requests went out. It tells you when you asked, not when the data changed.

**Consequence**: there is no way to ask the data how current it is. The only
way to measure freshness is to keep dated snapshots and diff them. That makes
the snapshot series infrastructure, not a nice-to-have.

## Finding 2 — the system *is* live, but zeros are not converting

400 random subdistricts, snapshot (2026-08-05) vs. live (2026-08-09), 4 days
apart. Full numbers in [`drift_summary.csv`](drift_summary.csv), the rows that
moved in [`drift_changed_rows.csv`](drift_changed_rows.csv).

| | `transaction_value` | `savings_total_amount` |
|---|---|---|
| sampled | 400 | 400 |
| changed at all | 3 (0.8%) | 9 (2.2%) |
| **was 0, now > 0** | **0** | **0** |
| was > 0, increased | 3 | 8 |
| was > 0, decreased | 0 | 1 |
| net delta over 4 days | +IDR 15,138,350 | +IDR 6,270,000 |

Two things follow:

1. **The data is genuinely live.** Values moved in 4 days, and transaction
   figures only ever increased — they are cumulative, not periodic.
2. **Activity accretes only where it already exists.** Of 332 subdistricts that
   reported zero transactions on 2026-08-05, **zero** reported any by
   2026-08-09.

## How far does this let us go? (Not as far as it looks)

It is tempting to read 0/332 as "the zeros are permanent". It does not support
that yet:

- **4 days is a short window.** By the rule of three, 0 conversions in 332
  observations puts the 95% upper bound at ~0.9% per 4-day period. Sustained,
  that is *not* a negligible annual rate. This rules out a **fast** rollout of a
  data backlog; it does not rule out a slow or batched one.
- **Subdistrict granularity helps but isn't free.** A zero subdistrict means all
  of its villages are zero, so any village activating would show. That part is
  sound.
- **One sample, one moment.** If SIMKOPDES releases data in quarterly batches,
  a 4-day window sees nothing by construction.

**What would settle it**: run this monthly. Three or four points make the
conversion rate estimable instead of bounded. Until then, every write-up that
uses transaction data must say that zero is *unidentifiable* between "no
activity" and "no reporting" — not assert the first.

## Finding 3 — the extractor will currently fail

`/statistics/land-mapping` returns HTTP 500 consistently (3/3 attempts,
2026-08-09). `scripts/extract_kopdes.py` calls it unguarded when building
`kopdes_national_summary.csv`, so a re-run today raises rather than degrading.
This is exactly the kind of breakage a live, in-progress source produces, and
it argues for the extractor tolerating per-endpoint failure and recording which
endpoints were unavailable in that snapshot.

## Caveats

- Sample is 400 of 7,425 subdistricts (5.4%), seed 7. Re-running with a
  different `--seed` will give slightly different counts.
- The comparison baseline is the committed CSV; if `data/raw/` is regenerated,
  the "snapshot" side moves and the drift measurement is destroyed. **Do not
  re-run `scripts/extract_kopdes.py` over `data/raw/` without first copying the
  old snapshot aside** — see the recommendation in
  [`analytics-plan-review.md`](../../analytics-plan-review.md).
