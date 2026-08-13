# 01 — Snapshot drift: are the zeros real, or just not entered yet?

**Primary**: `python reports/01-snapshot-drift/diff_snapshots.py data/raw data/snapshots/2026-08-09 --label-t0 2026-08-05`
— every village, no network, reproducible from committed files.
**Secondary**: `python reports/01-snapshot-drift/run.py` — samples 400
subdistricts against the **live API**; use when only one snapshot exists.
**Snapshots held**: 2026-08-05 (`data/raw/`, frozen) · 2026-08-09 (`data/snapshots/2026-08-09/`)

## The headline

**Of 80,553 villages reporting zero transactions on 2026-08-05, exactly one
reported any activity four days later.**

Full population, every village matched on `village_id`
([`snapshot_diff_summary.csv`](snapshot_diff_summary.csv)):

| Measure                | Changed | Was zero | 0 → positive | Conversion | Net delta        |
| ---------------------- | ------- | -------- | ------------ | ---------- | ---------------- |
| `transaction_value`    | 31      | 80,553   | **1**        | 0.0012%    | +IDR 235,573,832 |
| `transaction_volume`   | 31      | 80,553   | 1            | 0.0012%    | +7,268           |
| `savings_total_amount` | 150     | 72,697   | 6            | 0.0083%    | +IDR 172,615,000 |
| `accounts_count`       | 0       | 3,490    | 0            | 0%         | 0                |
| `npwp_count`           | 1       | 2,336    | 1            | 0.043%     | +1               |
| `nib_count`            | 4       | 22,346   | 4            | 0.018%     | +4               |

At the rate observed, ~91 villages a year would begin reporting, and clearing
the current 80,553 would take **~883 years**.

> **Read that horizon carefully.** It assumes the backlog drains at a constant
> trickle. A single batch upload would invalidate it completely, and four days
> is a short window. What it _does_ establish is that **no backlog is currently
> draining** — the state of the system today is not "mid-rollout", it is
> static.

> **Addendum 2026-08-13:** the constant-trickle assumption did not hold. The
> third snapshot (`data/snapshots/2026-08-13/`) shows **+209 villages** began
> reporting between 08-09 and 08-13 (2,517 → 2,726) — two orders of magnitude
> above the 08-05→08-09 rate — while value grew a further 12.7%. The "no
> backlog is draining" claim is true of the first window and _not_ of the
> second. Whether the burst is a one-off entry or the start of a real drain is
> exactly what the monthly series is designed to settle. Do not extend this
> report's ~91/year rate to 08-13; see [09](../09-external-corroboration/)
> Finding 3.

Every village whose transactions moved is listed in
[`snapshot_diff_changed_villages.csv`](snapshot_diff_changed_villages.csv) — 31
rows, auditable by hand.

Meanwhile the registry itself keeps growing: **+40 cooperatives** and **+23 land
assets** over the same four days. Records are being added; activity is not being
reported against them.

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

| Endpoint                                          | Fields returned per record                                               |
| ------------------------------------------------- | ------------------------------------------------------------------------ |
| `/cooperatives/get-all-nested`                    | `cooperative_id`, `name`, `latitude`, `longitude` — **that's all**       |
| `/cooperative-assets/get-all`                     | `asset_id`, `cooperative`, `status`, `surveyor`, `latitude`, `longitude` |
| `/statistics/national-readiness/subdistrict/{id}` | carries an `updated_at`…                                                 |

…but that `updated_at` is **the API's response time, not a data-freshness
stamp**. Ten subdistricts queried in sequence returned
`2026-08-10T01:12:19` … `:23` — incrementing with the wall clock as the
requests went out. It tells you when you asked, not when the data changed.

**Consequence**: there is no way to ask the data how current it is. The only
way to measure freshness is to keep dated snapshots and diff them. That makes
the snapshot series infrastructure, not a nice-to-have.

## Finding 1b — the 2026-08-05 export contains 1,555 duplicate villages

Found by this comparison: the 2026-08-09 pull came back 1,555 village rows
shorter with an **identical `village_id` set**. Nothing disappeared — the older
export was duplicated.

| File                           | 2026-08-05 rows | Duplicate ids | 2026-08-09 rows |
| ------------------------------ | --------------- | ------------- | --------------- |
| `kopdes_stats_village.csv`     | 84,624          | **1,555**     | 83,069          |
| `kopdes_stats_subdistrict.csv` | 7,425           | 148           | 7,277           |
| `kopdes_stats_district.csv`    | 525             | 5             | 514             |

They matter: summing over rows double-counts, which put the village-level
transaction total **IDR 18.8M above** the province-level total (179,574,847,612
vs 179,555,998,112). Deduplicating brings it to 179,559,332,612, within IDR 3.3M.

**Always `drop_duplicates` on the id before comparing or summing.**
[02-zero-inflation](../02-zero-inflation/) was corrected for this; its headline
moved only from 97.02% to 96.97% zero, and the concentration result did not move
at all.

## Finding 2 — the sampled version (superseded, kept for the record)

The original measurement sampled 400 subdistricts against the live API rather
than diffing two snapshots. It agreed — 0 of 332 zero-transaction subdistricts
converted — but the full-population diff above is strictly better: complete
coverage, no network, and reproducible by anyone with the repo.

400 random subdistricts, snapshot (2026-08-05) vs. live (2026-08-09), 4 days
apart. Full numbers in [`drift_summary.csv`](drift_summary.csv), the rows that
moved in [`drift_changed_rows.csv`](drift_changed_rows.csv).

|                       | `transaction_value` | `savings_total_amount` |
| --------------------- | ------------------- | ---------------------- |
| sampled               | 400                 | 400                    |
| changed at all        | 3 (0.8%)            | 9 (2.2%)               |
| **was 0, now > 0**    | **0**               | **0**                  |
| was > 0, increased    | 3                   | 8                      |
| was > 0, decreased    | 0                   | 1                      |
| net delta over 4 days | +IDR 15,138,350     | +IDR 6,270,000         |

Two things follow:

1. **The data is genuinely live.** Values moved in 4 days, and transaction
   figures only ever increased — they are cumulative, not periodic.
2. **Activity accretes only where it already exists.** Of 332 subdistricts that
   reported zero transactions on 2026-08-05, **zero** reported any by
   2026-08-09.

## How far does this let us go?

Much further than the earlier sample did, but still not all the way.

**What it now supports.** With the full population there is no sampling
uncertainty left: 1 conversion in 80,553 villages is an observation, not an
estimate. Any claim that SIMKOPDES is "mid-rollout" and steadily filling in
predicts a visible flow of zeros turning positive. Over four days, that flow was
one village. **No backlog is draining.**

**What it still does not support.**

- **Four days is a short window.** If the ministry uploads in quarterly batches,
  a four-day window sees nothing by construction. The 883-year horizon is a way
  of expressing the observed rate, _not_ a forecast.
- **Non-reporting and non-activity remain formally indistinguishable.** This
  measurement narrows the gap hard — a system being actively populated should
  show movement — but it does not close it. A cooperative could be trading
  briskly and reporting nothing at all, and nothing here would reveal it.
- **One interval, one pair of snapshots.** Two points give a rate; they do not
  give a trend.

**What would settle it**: monthly snapshots. Three or four intervals distinguish
a steady trickle from a flat line from a batch release, and if a batch does
arrive, the series captures it rather than being blindsided by it. Until then,
write "has not **reported** any transaction", not "is inactive" — the honest
claim is strong enough on its own.

## Finding 3 — an endpoint is down, and the extractor now survives it

`/statistics/land-mapping` returns HTTP 500 consistently (verified over 2.5
hours on 2026-08-09). It was called unguarded, so a re-run would have crashed
before writing anything.

Fixed: non-essential endpoints now degrade instead of raising, and every failure
is recorded in the snapshot's `_manifest.json`. The 2026-08-09 snapshot carries
one recorded hole rather than not existing. The cost is visible —
`kopdes_national_summary.csv` has 14 rows instead of 26, missing the `land_*`
metrics — which is exactly the kind of thing a manifest should make obvious
rather than silent.

## How snapshots are kept

```text
data/raw/                     2026-08-05 — frozen, never regenerate in place
data/snapshots/2026-08-09/    + _manifest.json
data/snapshots/<next>/        run monthly
```

Capture a new one with:

```bash
python scripts/extract_kopdes.py data/snapshots/$(date +%F)
```

`_manifest.json` records pull start/finish times, the period, which endpoints
failed, and per-file row counts and SHA-256 hashes. The hashes make "did
anything change at all?" a one-line check — necessary because the API carries
**no per-record freshness field**: its `updated_at` is the response time, not a
data timestamp (Finding 1a).

### Snapshot CSVs are held locally, not committed

Each pull is ~28 MB, and the project publishes findings as pages rather than raw
exports. Snapshots are available on request. `.gitignore` drops
`data/snapshots/**/*.csv` but **keeps every `_manifest.json`**, and that
distinction is deliberate.

**Be clear-eyed about what this costs.** A SIMKOPDES snapshot cannot be
re-fetched — the API serves current state only, so the 2026-08-05 baseline is
gone the moment it changes. Once the CSVs are out of the repository, a third
party cannot independently verify the central drift finding. What survives in
git is:

- the **committed manifests**, whose SHA-256 hashes pin exactly which bytes were
  compared and when;
- the **derived outputs** — [`snapshot_diff_summary.csv`](snapshot_diff_summary.csv)
  and [`snapshot_diff_changed_villages.csv`](snapshot_diff_changed_villages.csv),
  31 auditable rows;
- `diff_snapshots.py`, so the method is inspectable even where the inputs are not.

That is provenance, not verification. If the finding is challenged, the answer
is to hand over the snapshots and let the challenger check them against the
committed hashes — so **do not delete or move the local copies**, and back them
up outside this working tree.

## Caveats

- **Never regenerate `data/raw/` in place.** It is the t0 baseline; overwriting
  it destroys the only measurement that answers the "not entered yet" rebuttal.
- Row counts are not comparable across snapshots without deduplication
  (Finding 1b).
- `run.py`'s sampled variant uses seed 7 over 400 of 7,425 subdistricts; a
  different `--seed` gives slightly different counts. Prefer `diff_snapshots.py`
  whenever two snapshots exist.
- `kopdes_stats_village.csv` has one row per village, and 82,763 of 83,069
  villages hold exactly one cooperative — so village ≈ cooperative, but not
  exactly.
