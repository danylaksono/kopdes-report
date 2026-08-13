"""
Report 18 - the health index: what "unhealthy x 38" actually says (and doesn't).

The published data layer carries a per-province "health_score" that is constant
30 / "unhealthy" for all 38 provinces. This report separates what that field
really is (a placeholder on the map endpoint) from what the ministry's own
health index does say (average_health_index 50-57, 91% of scored cooperatives
"unhealthy", only 37.6% of cooperatives ever scored).

Answers the question report 16 raised: does the real RAT channel (60%, not 0%)
change what "unhealthy" means? Short answer: RAT co-varies with the index
(rho ~0.80) but is not the driver - the index tracks who got scored at all and
the same economic geography as every other measure.

Run:  python reports/18-health-scoring/run.py
No network. Reads kopdes_stats_province.csv (committed baseline or KOPDES_RAW).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_lib"))
from common import RAW, out_dir, write_csv  # noqa: E402

OUT = out_dir(__file__)

ISLAND = {
    "ACEH": "Sumatera", "SUMATERA UTARA": "Sumatera", "SUMATERA BARAT": "Sumatera",
    "RIAU": "Sumatera", "JAMBI": "Sumatera", "SUMATERA SELATAN": "Sumatera",
    "BENGKULU": "Sumatera", "LAMPUNG": "Sumatera", "KEPULAUAN BANGKA BELITUNG": "Sumatera",
    "KEPULAUAN RIAU": "Sumatera",
    "DKI JAKARTA": "Jawa", "JAWA BARAT": "Jawa", "JAWA TENGAH": "Jawa",
    "DAERAH ISTIMEWA YOGYAKARTA": "Jawa", "JAWA TIMUR": "Jawa", "BANTEN": "Jawa",
    "BALI": "BaliNusa", "NUSA TENGGARA BARAT": "BaliNusa", "NUSA TENGGARA TIMUR": "BaliNusa",
    "KALIMANTAN BARAT": "Kalimantan", "KALIMANTAN TENGAH": "Kalimantan",
    "KALIMANTAN SELATAN": "Kalimantan", "KALIMANTAN TIMUR": "Kalimantan",
    "KALIMANTAN UTARA": "Kalimantan",
    "SULAWESI UTARA": "Sulawesi", "SULAWESI TENGAH": "Sulawesi", "SULAWESI SELATAN": "Sulawesi",
    "SULAWESI TENGGARA": "Sulawesi", "GORONTALO": "Sulawesi", "SULAWESI BARAT": "Sulawesi",
    "MALUKU": "MalukuPapua", "MALUKU UTARA": "MalukuPapua",
    "PAPUA": "MalukuPapua", "PAPUA BARAT": "MalukuPapua", "PAPUA TENGAH": "MalukuPapua",
    "PAPUA PEGUNUNGAN": "MalukuPapua", "PAPUA SELATAN": "MalukuPapua",
    "PAPUA BARAT DAYA": "MalukuPapua",
}


def main():
    src = RAW / "kopdes_stats_province.csv"
    d = pd.read_csv(src)
    d["rat_share"] = d.rat_count / d.cooperatives
    d["nib_share"] = d.nib_count / d.cooperatives
    d["npwp_share"] = d.npwp_count / d.cooperatives
    d["tx_per_coop"] = d.transaction_value / d.cooperatives
    d["savings_per_coop"] = d.savings_total_amount / d.cooperatives
    d["scored_share"] = d.health_total_cooperative / d.cooperatives
    d["island"] = d.province.map(ISLAND)
    d["unhealthy_share_of_scored"] = d.unhealthy_count / d.health_total_cooperative

    # -- the artifact: health_score is constant
    const_score = sorted(d.health_score.unique())
    const_status = sorted(d.health_status.unique())
    print(f"health_score unique: {const_score}")
    print(f"health_status unique: {const_status}")

    # -- coverage
    scored = int(d.health_total_cooperative.sum())
    total = int(d.cooperatives.sum())
    print(f"scored {scored:,} / {total:,} = {scored/total*100:.1f}%  (never scored: {total-scored:,})")

    # -- per-coop breakdown (sums across provinces; healthy/fairly/unhealthy counts)
    healthy, fairly, unhealthy = (int(d[k].sum()) for k in
                                  ("healthy_count", "fairly_healthy_count", "unhealthy_count"))
    print(f"scored breakdown: healthy {healthy:,} ({healthy/scored*100:.1f}%), "
          f"fairly {fairly:,} ({fairly/scored*100:.1f}%), "
          f"unhealthy {unhealthy:,} ({unhealthy/scored*100:.1f}%)")

    # -- index band
    print(f"average_health_index: min {d.average_health_index.min()} max "
          f"{d.average_health_index.max()} mean {d.average_health_index.mean():.1f}")

    # -- correlations vs average_health_index
    from scipy.stats import spearmanr
    drivers = []
    for c in ["rat_share", "nib_share", "npwp_share", "tx_per_coop",
              "savings_per_coop", "scored_share", "cooperatives"]:
        rho, p = spearmanr(d.average_health_index, d[c])
        drivers.append({"driver": c, "spearman_rho": round(rho, 3), "p_value": round(p, 4)})
        print(f"  spearman(index, {c:16s}) = {rho:+.3f}  p={p:.4f}")

    # -- within-island control (demean by island, then correlate)
    g = d.groupby("island")[["average_health_index", "rat_share", "scored_share"]].transform("mean")
    dc = d[["average_health_index", "rat_share", "scored_share"]] - g
    for c in ["rat_share", "scored_share"]:
        rho, p = spearmanr(dc.average_health_index, dc[c])
        print(f"  within-island spearman(index, {c:14s}) = {rho:+.3f}  p={p:.4f}")

    write_csv(pd.DataFrame(drivers), OUT / "index_drivers.csv",
              "Spearman correlations of average_health_index vs province stats")

    cols = ["province_id", "province", "island", "cooperatives", "health_total_cooperative",
            "scored_share", "healthy_count", "fairly_healthy_count", "unhealthy_count",
            "unhealthy_share_of_scored", "average_health_index", "health_score", "health_status",
            "rat_share", "nib_share", "tx_per_coop", "savings_per_coop"]
    write_csv(d[cols].sort_values("average_health_index", ascending=False),
              OUT / "health_index_by_province.csv", "per-province health index, coverage, drivers")


if __name__ == "__main__":
    main()
