# 12 — Product mix: what does the KDMP program actually sell?

**Run**: `python reports/12-product-mix/run.py` · No network · **Last run**: 2026-08-12
**Source**: `kopdes_province_top_products.csv` (261 rows, 33 of 38 provinces)

D2 of `analytics-plan.md`. This is the only transaction-*content* data in the
export — the top products each province reports selling. Per the plan-review:
report composition, skip the diversity index (it is biased on top-N-truncated
lists). Product names are inconsistent in the source (`BERAS SPHP` vs
`BERAS MEDIUM SPHP 5 KG`), so products are bucketed into categories by keyword.

## Finding 1 — the program is a staple-goods shop, not a specialised service

[`product_categories.csv`](product_categories.csv) — national composition by value

| Category | Share of reported value | Provinces |
|---|---|---|
| **rice** | **48.2%** | 29 |
| **cooking oil** | **26.9%** | 24 |
| **fertilizer** | 16.5% | 24 |
| other | 6.8% | 29 |
| sugar | 0.8% | 18 |
| dairy | 0.6% | 2 |
| LPG | 0.3% | 16 |

Three-quarters of reported sales value is **rice and cooking oil**; fertilizer
is the main agricultural input, present in 24 provinces. KDMP are positioned as
village grocery + farm-input shops — which is exactly the role they would
compete for with existing minimarkets and warungs (the cannibalisation
question, [06](../06-minimarket-proximity/)).

## Finding 2 — the top of the list is highly consistent across provinces

[`province_top_product.csv`](province_top_product.csv) ·
[`product_rankings.csv`](product_rankings.csv) (50 distinct product names)

- The per-province top seller is almost always **BERAS SPHP** (the subsidised
  rice), **MINYAK GORENG** (cooking oil) or **Pupuk NPK Phonska** (fertilizer).
- In 7 of 33 provinces a single item is over half the province's reported value
  (e.g. BERAS SPHP at 73.6% of Sumatera Selatan, Pupuk NPK at 100% of Bangka
  Belitung).
- The whole table is dominated by ~25 products; the long tail is one-off lines
  (`BUAH ANGGUR`, `DAGING SAPI`, `LOIN TUNA`) that appear in a single province.

## Caveats

- The source is a per-province **top-products** list, so this is the composition
  of what was reported as top sellers, not a complete sales ledger. Volumes and
  shares should be read as "among reported top products".
- 5 provinces (Papua, Papua Barat, Papua Selatan, Papua Tengah, Papua Pegunungan
  under their grouped names) have no product rows — the product channel is
  empty in the same places every other activity channel is empty (13, 14).
- "BARANG LAINNYA" ("other goods") is the export's own catch-all and carries
  6.8% of value.
- No causal or welfare reading is possible from this alone: it shows *what was
  sold*, not *who bought it* or at what margin.

## Output for later

[`product_categories.csv`](product_categories.csv) and
[`province_top_product.csv`](province_top_product.csv) give the "what do they
actually sell" one-pager for the money act of the report.
