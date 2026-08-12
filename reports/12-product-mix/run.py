#!/usr/bin/env python3
"""
12-product-mix - what does the KDMP program actually sell?

D2 of analytics-plan.md. The per-province top-products table is the only
transaction-content data in the export. The plan-review's instruction is
explicit: report category composition, skip the diversity index (it is biased
on top-N-truncated lists).

Product names in the export are inconsistent ("BERAS SPHP" vs "BERAS MEDIUM
SPHP 5 KG"), so products are bucketed into categories by keyword before any
composition is read. The raw rankings are reported too, with the inconsistency
left visible.

Reads only committed CSVs; no network; deterministic.

Usage: python reports/12-product-mix/run.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.common import RAW, out_dir, write_csv  # noqa: E402

OUT = out_dir(__file__)

# Ordered rules: first match wins. `other_misc` catches the export's own
# catch-all "BARANG LAINNYA"; everything else lands in `other`.
CATEGORY_RULES = [
    ("rice", lambda s: "beras" in s),
    ("cooking_oil", lambda s: "minyak" in s),
    ("fertilizer", lambda s: "pupuk" in s),
    ("lpg", lambda s: "lpg" in s or "elpiji" in s),
    ("sugar", lambda s: "gula" in s),
    ("dairy", lambda s: "susu" in s),
    ("other_misc", lambda s: s == "BARANG LAINNYA"),
]


def categorize(product: str) -> str:
    s = str(product).strip().lower()
    for name, rule in CATEGORY_RULES:
        if rule(s):
            return name
    return "other"


def main():
    t = pd.read_csv(RAW / "kopdes_province_top_products.csv")
    t["category"] = t["product"].map(categorize)
    print(f"{len(t):,} product rows, {t['province'].nunique()} provinces, "
          f"{t['product'].nunique()} distinct product names\n")

    # --- national composition by category -----------------------------------
    cat = (
        t.groupby("category", as_index=False)
        .agg(value=("value", "sum"), volume=("volume", "sum"),
             n_provinces=("province", "nunique"), n_product_names=("product", "nunique"))
        .assign(share_of_value=lambda d: (100 * d.value / d.value.sum()).round(2))
        .sort_values("value", ascending=False)
    )
    print("Category composition (national):\n")
    print(cat.to_string(index=False))
    write_csv(cat, OUT / "product_categories.csv")

    # --- national composition by raw product name ----------------------------
    prod = (
        t.groupby("product", as_index=False)
        .agg(value=("value", "sum"), volume=("volume", "sum"), n_provinces=("province", "nunique"))
        .assign(share_of_value=lambda d: (100 * d.value / d.value.sum()).round(2))
        .sort_values("value", ascending=False)
    )
    write_csv(prod, OUT / "product_rankings.csv", f"{len(prod)} distinct product names")

    # --- per-province top product by value ------------------------------------
    idx = t.groupby("province")["value"].idxmax()
    top = t.loc[idx, ["province", "product", "category", "value"]].reset_index(drop=True)
    prov_total = t.groupby("province")["value"].sum()
    top["province_total_value"] = top["province"].map(prov_total)
    top["top_product_share"] = (100 * top.value / top.province_total_value).round(2)
    top = top.sort_values("province_total_value", ascending=False)
    write_csv(top, OUT / "province_top_product.csv", "per province")
    print("\nPer-province top product by value:\n")
    print(top[["province", "product", "category", "top_product_share"]].to_string(index=False))

    # --- category share by province -------------------------------------------
    share = (
        t.pivot_table(index="province", columns="category", values="value", aggfunc="sum", fill_value=0)
        .pipe(lambda d: d.div(d.sum(axis=1), axis=0) * 100)
        .round(2)
        .reset_index()
    )
    write_csv(share, OUT / "province_category_share.csv", "percent of value, per province")


if __name__ == "__main__":
    main()
