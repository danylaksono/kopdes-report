# 02 — Zero inflation: there is almost no outcome variable

**Run**: `python reports/02-zero-inflation/run.py` · No network, deterministic ·
**Source**: `data/raw/kopdes_stats_village.csv` (2026-08-05 snapshot, 84,624 villages)

## Finding 1 — activity fields are ~97% zero; administrative fields are ~96% filled

[`zero_inflation_by_field.csv`](zero_inflation_by_field.csv)

| Field | Kind | Non-zero |
|---|---|---|
| `npwp_count` | administrative | **96.4%** |
| `accounts_count` | administrative | **95.2%** |
| `nib_count` | administrative | 72.3% |
| `savings_total_amount` | activity | 12.3% |
| `simpanan_pokok_amount` | activity | 11.7% |
| `simpanan_wajib_amount` | activity | 9.1% |
| `transaction_value` | activity | **3.0%** |
| `transaction_volume` | activity | **3.0%** |

The split is the interesting part. Fields written **once at registration** are
nearly complete. Fields that require **ongoing operational reporting** are
nearly empty. Conditioning on the village having an account doesn't change it —
of the 80,517 villages that have one, 98.6% have an NPWP but only 3.1% have ever
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

1. **Binary**: `any_activity = transaction_value > 0`, 2,521 positives out of
   84,624. Rare-event logistic regression with province fixed effects.
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
| 2,521 (all non-zero) | 100% |

**100 villages out of 84,624 — 0.12% — carry 37% of the program's entire
reported economic output.** A thousand carry 93%.

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
