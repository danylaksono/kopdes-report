# 11 — Savings behaviour: are members actually saving, or are the accounts dormant?

**Run**: `python reports/11-savings-behaviour/run.py` · No network · **Last run**: 2026-08-12
**Source**: `kopdes_stats_village.csv` (deduplicated, 83,069 villages)

F2 of `analytics-plan.md`. Transactions are 97% zero ([02](../02-zero-inflation/)),
which makes them a poor lens on whether KDMP are alive. Savings are the second
activity channel in the data, and they are structurally richer: they split into
**simpanan pokok** — the one-time capital a member pays at founding — and
**simpanan wajib** — the ongoing compulsory dues that keep coming only while a
cooperative actually operates. The pokok/wajib split is the dormancy signal the
plan asks for.

## The method, in one paragraph

All figures are village-level from the deduplicated `kopdes_stats_village.csv`
(1,555 duplicate `village_id`s removed, per 01). Integrity is checked first:
`savings_total_amount = pokok + wajib` holds for **all** 83,069 villages, so the
sub-splits are trustworthy. Seven views: zero-inflation per savings field,
a savings×transactions cross-tab, pokok/wajib dormancy bands, the wajib/pokok
ratio, per-member amounts, value concentration, and a province spread
cross-referenced to the official health index.

## Finding 1 — savings are reported four times more often than transactions, and still 87.5% of villages report zero

[`savings_zero_inflation.csv`](savings_zero_inflation.csv)

| Field | Villages non-zero | Share |
|---|---|---|
| accounts (admin, from 02) | — | ~96% |
| **pokok** (one-time capital) | 9,857 | **11.87%** |
| **wajib** (ongoing dues) | 7,666 | **9.23%** |
| **any savings** | 10,372 | **12.49%** |
| transactions (02) | 2,516 | **3.03%** |

The three tiers are the read: the *registration* machinery is populated for
~96% of villages, *one-time capital* was collected in ~12%, and *ongoing
operations* (wajib or transactions) in under 10%. A system that captured the
accounts field for 96% of villages did capture pokok for only 12% — the low
fields are not empty because the system cannot hold them.

## Finding 2 — even where savings exist, the money is one-time capital, not ongoing saving

[`dormancy_bands.csv`](dormancy_bands.csv) · [`wajib_pokok_ratio.csv`](wajib_pokok_ratio.csv)

| Dormancy band | Villages | Share |
|---|---|---|
| **no savings at all** | 72,697 | **87.51%** |
| pokok only (capital, no ongoing dues) | 2,706 | 3.26% |
| both pokok and wajib | 7,151 | 8.61% |
| wajib only | 515 | 0.62% |

Among the 7,151 villages reporting **both**:

- median **wajib/pokok = 0.28** (p25 0.11, p75 0.70)
- only **15.7%** have wajib > pokok

The plan's own test is explicit: *"if wajib >> pokok, it suggests active ongoing
saving."* That is not what the data shows. The typical reporting village has
roughly four times more pokok than wajib — the signature of a cooperative that
collected its founding capital and then stopped, not one whose members are
saving month to month.

## Finding 3 — savings reveal activity that transactions hide

[`savings_vs_transactions.csv`](savings_vs_transactions.csv)

| | no transaction | transaction |
|---|---|---|
| **savings** | 9,192 (11.07%) | 1,180 (1.42%) |
| **no savings** | 71,361 (85.91%) | 1,336 (1.61%) |

**14.1%** of villages report *some* financial footprint (savings or
transactions), against the 3.0% that report transactions. The two signals barely
overlap — 9,192 villages report savings with zero transactions. Transactions
alone understate the "anything is happening" share by a factor of ~4.7; savings
is the less degenerate activity channel (12.5% vs 3.0% non-zero).

## Finding 4 — where savings is reported, it is real money

[`savings_per_member.csv`](savings_per_member.csv)

| Type | Villages | per-member median | per-member mean |
|---|---|---|---|
| pokok | 9,857 | **Rp 50,000** | Rp 192,000 |
| wajib | 7,666 | **Rp 20,000** | Rp 39,000 |

These are plausible Indonesian cooperative figures — a one-time principal of
~Rp 50k and mandatory dues of ~Rp 20k are exactly the scale such programs
publish. Where the fields are filled, they describe real member money, not
placeholder values. (We cannot decompose wajib into a monthly rate: the data
has no time anchor, only a lifetime total.)

## Finding 5 — savings are less concentrated than transactions

[`savings_concentration.csv`](savings_concentration.csv)

| Top-N villages | Share of savings | Share of transactions (02) |
|---|---|---|
| 100 | 24.4% | 37% |
| 1,000 | 56.9% | 93% |

Savings spread much more evenly than transactions — consistent with savings
being a *registration-era* phenomenon (pokok collected across many villages at
founding) rather than the deep operating concentration of transactions.

## Finding 6 — national totals and the province gradient

[`savings_national.csv`](savings_national.csv) · [`savings_by_province.csv`](savings_by_province.csv)

Total savings **Rp 40.1 miliar (~USD 2.5M)** against total transactions
**Rp 179.6 miliar (~USD 11.2M)** — savings are about a fifth of reported
economic activity. Savings per village: ~Rp 483k.

Savings uptake has a **~400× geographic gradient**: 31.3% of villages in DIY
Yogyakarta report savings, down through Java and Bali (~17–22%) to 4.95% in
Aceh and **0.08% in Papua Pegunungan**. The gradient tracks economic geography,
not randomness — the same order as 02's transaction gradient. The official
health index is flat (50–57 across all 38 provinces, per the D1 finding in
`analytics-plan-review.md`), so it cannot discriminate; it is included in the
CSV for reference only.

## Caveats

- A zero is still ambiguous between "no activity" and "not yet reported" (01).
  What the savings channel adds is *structure*: the same system that recorded
  accounts for 96% of villages recorded pokok for 12% and wajib for 9%. That
  ordering — admin ≫ one-time capital ≫ ongoing operations — is what a real
  activity funnel looks like, and what a purely arbitrary data gap would not
  necessarily produce. It strengthens, but does not prove, the dormancy read.
- Per-member amounts assume the `*_members` columns are complete. Where they
  disagree with `*_tx`, the members figure was used.
- Wajib cannot be converted to a monthly due without a time anchor. The
  per-member figures are lifetime totals.
- The province table cross-references the official `average_health_index`
  descriptively; its variance is too small to support a correlation.

## Output for later

No per-cooperative table here — this is a village/aggregate analysis like 02.
Its numbers feed the money act of the report (budget-vs-output) alongside 02,
09 and the RAT finding.
