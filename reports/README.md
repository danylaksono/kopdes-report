# Reports

Findings from the KDMP investigation. One directory per question, each
self-contained and reproducible.

```
reports/NN-slug/
    run.py      the analysis, runnable from the repo root
    README.md   the write-up - what was found, and what it does not support
    *.csv       outputs, committed so findings survive without a re-run
```

Run any of them with `python reports/NN-slug/run.py`. Dependencies:
`pip install -r reports/requirements.txt`.

## Index

| # | Report | Question | Network | Status |
|---|---|---|---|---|
| 01 | [snapshot-drift](01-snapshot-drift/) | Is SIMKOPDES still being filled in? Are the zeros temporary? | **live API** | run 2026-08-09 |
| 02 | [zero-inflation](02-zero-inflation/) | How much of the performance data is actually zero? | no | run 2026-08-09 |
| 03 | [population-coverage](03-population-coverage/) | Who is within reach of a KDMP, and which KDMP are near nobody? | first run only | run 2026-08-09 |
| 04 | [siting-screen](04-siting-screen/) | Which KDMP sit somewhere physically implausible? | cloud rasters | run 2026-08-09, top 2,500 |

**Next screen to write**: 04 selects for *isolation*, so it structurally cannot
find the "built in the middle of a paddy field" cases — those sit next to a
village and score zero on its Stage A. A separate screen for **cropland cover
while close to population** is needed to test that half of the critique.

## What we can and cannot say right now

Read this before quoting any number out of these reports.

**Established:**

- Reported economic activity is extraordinarily concentrated — **100 villages
  out of 84,624 carry 37% of all national transaction value**, 1,000 carry 93%
  (02).
- **Coverage is not the problem**: 95% of Indonesians live within ~1.4 km of a
  KDMP (03). The "they built them where nobody can reach them" claim does not
  hold as a mass phenomenon.
- There is a **real tail**: 21.4% of cooperatives sit in a 400 m cell with zero
  recorded population, and 174 have nobody within 5 km (03).
- That tail contains **concrete, nameable candidates**: of the 2,500 most
  isolated, 2,346 are in closed forest, 69 on water/mangrove/wetland, 993 on
  steep ground — and **401 of them carry an officially `Terverifikasi` land
  asset**, 171 both verified and steep (04).
- SIMKOPDES **carries no per-record timestamp**, and its `updated_at` is the API
  response time, not a data-freshness stamp (01). Dated snapshots plus diffing
  is the only way to measure currency.

**Not established, and currently unidentifiable:**

- **Whether a zero means "no activity" or "not yet reported".** This is the
  single biggest open question and it gates most of `analytics-plan.md`. Four
  days of observation showed 0 of 332 zero-transaction subdistricts converting,
  which rules out a *fast* data backlog but not a slow or batched one (01).
  Until there are several monthly snapshots, every write-up must say zero is
  ambiguous rather than assert inactivity.
- **Whether flagged sites are badly sited or badly geocoded.** The screen in 04
  cannot tell a cooperative built in a forest from one whose coordinate is
  wrong. Both are findings; they are different findings. Each case needs
  imagery before it is cited.

## Conventions

- **Never regenerate `data/raw/` in place.** The drift measurement in 01
  compares the live API against the committed snapshot; overwriting the
  snapshot destroys the baseline. Copy the old snapshot aside first.
- Scripts write only inside their own report directory.
- Anything hitting the live API says so in its README, because re-running will
  legitimately produce different numbers than the committed CSVs.
- Every claim in a report README should trace to a committed CSV in the same
  directory.
