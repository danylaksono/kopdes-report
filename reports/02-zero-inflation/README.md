# 02 — Zero inflation: there is almost no outcome variable

**Run**: `python reports/02-zero-inflation/run.py` · No network, deterministic ·
**Source**: `data/raw/kopdes_stats_village.csv` (2026-08-05 snapshot, **83,069
villages after deduplication**)

> **Corrected 2026-08-09.** The 2026-08-05 export contains **1,555 duplicate
> `village_id`s**, found when the 2026-08-09 snapshot came back 1,555 rows
> shorter with an identical id set. Left in, they double-count: the
> village-level transaction total came out IDR 18.8M above the province-level
> total. All figures below are now deduplicated. The headline barely moved
> (97.02% → 96.97% zero; top-100 concentration unchanged at 37.31%), but the
> denominators did.

## Finding 1 — activity fields are ~97% zero; administrative fields are ~96% filled

[`zero_inflation_by_field.csv`](zero_inflation_by_field.csv)

| Field | Kind | Non-zero |
|---|---|---|
| `npwp_count` | administrative | **97.2%** |
| `accounts_count` | administrative | **95.8%** |
| `nib_count` | administrative | 73.1% |
| `savings_total_amount` | activity | 12.5% |
| `simpanan_pokok_amount` | activity | 11.9% |
| `simpanan_wajib_amount` | activity | 9.2% |
| `transaction_value` | activity | **3.0%** |
| `transaction_volume` | activity | **3.0%** |

The split is the interesting part. Fields written **once at registration** are
nearly complete. Fields that require **ongoing operational reporting** are
nearly empty. Conditioning on the village having an account doesn't change it —
of the 79,579 villages that have one, 98.9% have an NPWP but only 3.2% have ever
recorded a transaction ([`zero_inflation_given_account.csv`](zero_inflation_given_account.csv)).

**This is consistent with both explanations** and does not settle the question:

- *Genuine inactivity*: registration completed, operations never started.
- *Reporting lag*: registration is a one-off form that got filled; transaction
  reporting needs a working POS/reporting channel that isn't live yet.

See [01-snapshot-drift](../01-snapshot-drift/) for the only test that can
separate them, and its limits.

## Finding 2 — the consequence for the analytics plan

`transaction_value` **cannot be used as a continuous outcome**. Kruskal-Wallis
or ANOVA across accessibility bands — the method
[`analytics-plan.md`](../../analytics-plan.md) specifies for A4, and the basis
of H1 and H2 — is comparing two distributions that are each 97% ties at zero.

Workable reframings, in order of preference:

1. **Binary**: `any_activity = transaction_value > 0`, 2,516 positives out of
   83,069. Rare-event logistic regression with province fixed effects.
2. **Savings as secondary outcome**: 12.3% non-zero is far less degenerate, and
   `simpanan_pokok` vs `simpanan_wajib` is a real dormancy signal.
3. **Conditional magnitude**: among the 2,521 active villages only, model the
   amount. Small n, but it answers "where activity happens, what shapes it".

## Finding 3 — activity is extraordinarily concentrated

[`transaction_concentration.csv`](transaction_concentration.csv)

| Top N villages | Share of all national transaction value |
|---|---|
| 10 | 13.1% |
| 50 | 26.2% |
| **100** | **37.3%** |
| 500 | 76.7% |
| 1,000 | 92.9% |
| 2,516 (all non-zero) | 100% |

**100 villages out of 83,069 — 0.12% — carry 37% of the program's entire
reported economic output.** A thousand carry 93%. (Unchanged by the
deduplication correction, which is a useful robustness check in itself.)

This is the finding that should lead the investigation. Whatever the zeros
turn out to mean, the program's *reported* output is not "low across the
board"; it is absent everywhere except a few hundred sites. The research
question that follows is what those sites have that the other 82,000 don't —
and that is a question the placement data can actually answer.

## Finding 4 — the province gradient runs the wrong way for a simple story

[`zero_inflation_by_province.csv`](zero_inflation_by_province.csv). Non-zero
transaction rate ranges from **17.2% (DKI Jakarta)** and 16.5% (Banten) down to
**0.0%** in all four Papua provinces and Kepulauan Riau. Median province: 0.8%.

Note this gradient tracks urbanisation and connectivity — which is exactly what
*both* explanations predict (richer, better-connected places both transact more
**and** report better). It is not evidence for either. Don't cite it as such.

## Caveats

- Village rows total 84,624 against 83,382 cooperatives; 84,291 villages have
  exactly one cooperative, so village ≈ cooperative but not exactly.
- These village rows cannot be joined to coordinates for ~21% of cooperatives —
  see §1.5 of [`analytics-plan-review.md`](../../analytics-plan-review.md).
