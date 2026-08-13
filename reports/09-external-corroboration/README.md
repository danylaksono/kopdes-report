# 09 — External corroboration: is the dashboard the official number?

**Run**: `python reports/09-external-corroboration/run.py` · No network at run
time · **Last run**: 2026-08-10
**Source**: [`external_figures.csv`](external_figures.csv) (hand-curated, committed)

- `data/raw/` and `data/snapshots/`

## The rebuttal this exists to answer

Every finding in this investigation rests on SIMKOPDES reporting almost no
economic activity — 97% of villages at exactly zero. The ministry has one very
strong answer available: **"the website simply isn't up to date."**

[01](../01-snapshot-drift/) narrowed that defence and could not close it. Four
days is a short window, and a system nobody has finished filling in looks
identical to a system with nothing to report. Closing it needs evidence from
outside the dashboard.

Either the ministry's own public statements match its dashboard — in which case
the dashboard _is_ the official number and the rebuttal collapses — or they
diverge wildly, which is a story in itself. This was worth running before
knowing which.

**The answer is the first one, and it is not close.**

## Finding 1 — the ministry publishes our number to within 0.04%

[`reconciliation.csv`](reconciliation.csv)

On 9 August 2026, Liputan6 reported the national total. We pulled our own
snapshot straight from the SIMKOPDES API on the same day, independently:

|                                             | 2026-08-09           |
| ------------------------------------------- | -------------------- |
| Published (Liputan6, quoting the dashboard) | **Rp 179.72 miliar** |
| Our own extraction, same day                | **Rp 179.79 miliar** |
| Difference                                  | **+0.042%**          |

> _"Total nilai transaksi di Koperasi Merah Putih telah menembus angka fantastis
> Rp 179,72 miliar dari keseluruhan 71.454 kali volume transaksi."_

A 0.04% gap is a few hours of drift between when the journalist read the figure
and when our extractor ran. **These are the same number.**

The consequence is direct: _"the website isn't up to date"_ is not available as
a rebuttal, because the government is quoting this website. Whatever the
dashboard says about activity is the ministry's own public account of it.

## Finding 2 — the government's own count of trading cooperatives agrees

[`provincial_cross_check.csv`](provincial_cross_check.csv)

This line of evidence does not touch the dashboard at all. On 11 June 2026 the
head of the Government Communications Agency (Bakom) said:

> _"Hingga 8 Juni 2026, sebanyak 1.061 unit Kopdes Merah Putih telah beroperasi,
> tersebar di dua provinsi, yaitu 530 unit di Jawa Timur dan 531 unit di Jawa
> Tengah."_ — Muhammad Qodari, [CNN Indonesia](https://www.cnnindonesia.com/ekonomi/20260611123103-92-1367861/12-ribu-gerai-kopdes-merah-putih-rampung-1061-sudah-beroperasi)

**1,061 cooperatives operating, out of a registry of roughly 80,000 — 1.3%.**
Our own measure, two months later, is 2,517 villages reporting any transaction
at all — **3.0%**. Two independent measures, produced by different methods for
different purposes, land in the same low single digits.

And the geography matches. The June statement named exactly two provinces:

| Province    | Government "operating" (2026-06-08) | Ours "has reported a transaction" (2026-08-09) |
| ----------- | ----------------------------------- | ---------------------------------------------- |
| Jawa Timur  | 530                                 | **733**                                        |
| Jawa Tengah | 531                                 | **602**                                        |

Same two provinces, larger two months later, in the right proportion. Nothing
about the near-total absence of trading is an artefact of how we read the API.

## Finding 3 — this refines 01 rather than confirming it

[`published_series.csv`](published_series.csv)

The press series is not flat:

| As of      | Published total  | Change                     |
| ---------- | ---------------- | -------------------------- |
| 2026-07-31 | Rp 157.90 miliar | —                          |
| 2026-08-09 | Rp 179.72 miliar | **+21.82 miliar (+13.8%)** |

**The national total does move — 01's four-day window was too short to see it.**
That matters, because 01's framing invites the reading that nothing is being
entered at all, and over nine days the figure grew by nearly 14%.

But set that against what our own three snapshots show:

|                                 | 2026-08-05       | 2026-08-09       | 2026-08-13           |
| ------------------------------- | ---------------- | ---------------- | -------------------- |
| Total value                     | Rp 179.56 miliar | Rp 179.79 miliar | **Rp 202.60 miliar** |
| **Villages reporting anything** | **2,516**        | **2,517**        | **2,726**            |

Value grows. **Participation does not** was true of the first window — one
village joined in four days — and it does **not** survive the third snapshot:
**+209 villages began reporting** (2,517 → 2,726, +8.3%) between 08-09 and
08-13 while value grew a further 12.7%. The honest claim is now narrower: the
reported total rises, and over the first window participation did not move
while over the second it expanded with the value. Whether that is a backlog
starting to drain or a one-off entry burst is what the monthly series will
show — 01's “one village in four days” framing must not be extended to 08-13.

## Finding 4 — the "IDR 179.5T" figure in our own notes was wrong by 1000×

`AGENTS.md` recorded the headline as **IDR 179.5T**. Every external source says
**miliar** — billion. The correct figure is **Rp 179.5 billion, roughly USD 11
million**, for the entire national programme.

Per cooperative that is about **Rp 2.15 million — roughly USD 130 — for the
whole life of the cooperative to date.** That is the number a reader can hold,
and it is the one to publish. (`analytics-plan-review.md` had already flagged
this as a correction to make; this closes it with an external source.)

## Finding 5 — the dashboard and the landing endpoint have diverged since 08-13

[`dashboard_series.csv`](dashboard_series.csv)

On 08-09 the figure our extractor pulls from `/cooperatives/landing-summary`
(Rp 179.75 miliar) matched both the press (Rp 179.72 miliar) and the per-province
stats rolled up (Rp 179.79 miliar). On 08-13 that identity broke:

| Source (2026-08-13)                                | Total value          | Transactions |
| -------------------------------------------------- | -------------------- | ------------ |
| `/cooperatives/landing-summary`                    | **Rp 180.74 miliar** | 72,106       |
| `nested_data.totals` (what the dashboard displays) | **Rp 202.60 miliar** | 74,265\*     |

\*74,265 is the dashboard's displayed volume; the API's `transaction_volume`
field (29,072,780) is a unit count, not the transaction count, so the two
sides are not directly comparable.

The dashboard renders the `nested_data` figure; `landing-summary` is now a
separate, lagging aggregate. The extractor now records **both** (`nested_*`
metrics in `kopdes_national_summary.csv`), so the divergence is visible in
every snapshot and no future pull can silently pick one side. Any reconciliation
must state which figure it is against — historically the press quoted the
figure that now lives in `nested_data`.

## What this does _not_ establish

- **It does not prove the underlying trade is small.** It proves the ministry's
  public account and its dashboard are the same account. A cooperative could be
  trading briskly and reporting nothing, and both sources would be equally blind
  to it. The zero remains "has not **reported**", never "is inactive".
- **"Operating" and "has reported a transaction" are different definitions.**
  They agree in magnitude, which is the point; they are not the same measure and
  should not be presented as one.
- **Two outlets, one language, one window.** The series rests on Liputan6 and CNN
  Indonesia between June and August 2026. Kemenkop press releases, DPR Komisi VI
  hearing records and BPS would all strengthen it, and none are in here yet.
- **Press figures cannot be re-derived.** They are transcribed by hand into
  [`external_figures.csv`](external_figures.csv) with a URL and a verbatim quote
  precisely so the transcription can be audited. Nothing is scraped at run time —
  a scraper would silently change the evidence base between runs.
- **The snapshot series is still the irreplaceable thing.** This report makes the
  monthly pull _more_ valuable, not less: it is now demonstrable that our
  snapshots reproduce the official figure, so a series of them is a record of the
  government's own account of its programme. Every month not captured is lost.

## Outputs

| File                                                       | Contents                                                                |
| ---------------------------------------------------------- | ----------------------------------------------------------------------- |
| [`external_figures.csv`](external_figures.csv)             | every published claim, with outlet, attribution, URL and verbatim quote |
| [`reconciliation.csv`](reconciliation.csv)                 | same-day published vs our own extraction                                |
| [`published_series.csv`](published_series.csv)             | the external transaction-value series                                   |
| [`provincial_cross_check.csv`](provincial_cross_check.csv) | the June per-province operating counts against ours                     |
| [`our_snapshot_totals.csv`](our_snapshot_totals.csv)       | what each snapshot we hold sums to                                      |
| [`dashboard_series.csv`](dashboard_series.csv)             | the 08-13 live-API observation: landing vs `nested_data` (divergence)   |
