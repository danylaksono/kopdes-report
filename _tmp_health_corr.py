import pandas as pd, numpy as np
from scipy.stats import spearmanr
d = pd.read_csv("data/raw/kopdes_stats_province.csv")
d["rat_share"] = d.rat_count / d.cooperatives
d["nib_share"] = d.nib_count / d.cooperatives
d["npwp_share"] = d.npwp_count / d.cooperatives
d["tx_per_coop"] = d.transaction_value / d.cooperatives
d["savings_per_coop"] = d.savings_total_amount / d.cooperatives
d["scored_share"] = d.health_total_cooperative / d.cooperatives
cols = ["average_health_index","rat_share","nib_share","npwp_share","tx_per_coop","savings_per_coop","scored_share","cooperatives"]
print("=== Spearman correlations vs average_health_index (n=38) ===")
for c in cols:
    if c == "average_health_index": continue
    rho, p = spearmanr(d.average_health_index, d[c])
    print(f"  {c:22s} rho={rho:+.3f}  p={p:.4f}")
print("\n=== raw means ===")
print("  avg_health_index mean:", round(d.average_health_index.mean(),1))
print("  rat_share mean:", round(d.rat_share.mean(),3))
print("  scored_share mean:", round(d.scored_share.mean(),3), "min", round(d.scored_share.min(),3), "max", round(d.scored_share.max(),3))
print("\n=== per-province table (top 12 by index) ===")
t = d.sort_values("average_health_index", ascending=False)[["province","average_health_index","healthy_count","fairly_healthy_count","unhealthy_count","rat_share","scored_share"]]
print(t.head(12).round(3).to_string(index=False))
print("\n=== bottom 6 ===")
print(t.tail(6).round(3).to_string(index=False))
# island grouping (rough)
islands = {"SUMATERA UTARA":"Sumatera","ACEH":"Sumatera","SUMATERA BARAT":"Sumatera","RIAU":"Sumatera","JAMBI":"Sumatera","SUMATERA SELATAN":"Sumatera","BENGKULU":"Sumatera","LAMPUNG":"Sumatera","KEP. BANGKA BELITUNG":"Sumatera","KEP. RIAU":"Sumatera","DKI JAKARTA":"Jawa","JAWA BARAT":"Jawa","JAWA TENGAH":"Jawa","DI YOGYAKARTA":"Jawa","JAWA TIMUR":"Jawa","BANTEN":"Jawa","BALI":"BaliNusa","NUSA TENGGARA BARAT":"BaliNusa","NUSA TENGGARA TIMUR":"BaliNusa","KALIMANTAN BARAT":"Kalimantan","KALIMANTAN TENGAH":"Kalimantan","KALIMANTAN SELATAN":"Kalimantan","KALIMANTAN TIMUR":"Kalimantan","KALIMANTAN UTARA":"Kalimantan","SULAWESI UTARA":"Sulawesi","SULAWESI TENGAH":"Sulawesi","SULAWESI SELATAN":"Sulawesi","SULAWESI TENGGARA":"Sulawesi","GORONTALO":"Sulawesi","SULAWESI BARAT":"Sulawesi","MALUKU":"MalukuPapua","MALUKU UTARA":"MalukuPapua","PAPUA":"MalukuPapua","PAPUA BARAT":"MalukuPapua","PAPUA TENGAH":"MalukuPapua","PAPUA PEGUNUNGAN":"MalukuPapua","PAPUA SELATAN":"MalukuPapua","PAPUA BARAT DAYA":"MalukuPapua"}
d["island"] = d.province.map(islands)
print("\n=== mean index by island ===")
print(d.groupby("island").agg(idx=("average_health_index","mean"), n=("province","count"), rat=("rat_share","mean"), scored=("scored_share","mean")).round(2).to_string())
# partial: control for island
g = d.groupby("island")[["average_health_index","rat_share","tx_per_coop"]].transform("mean")
dc = d[["average_health_index","rat_share","tx_per_coop"]] - g
print("\n=== within-island (demeaned) Spearman ===")
for c in ["rat_share","tx_per_coop"]:
    rho, p = spearmanr(dc.average_health_index, dc[c])
    print(f"  {c:14s} rho={rho:+.3f} p={p:.4f}")
