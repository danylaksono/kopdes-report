#!/usr/bin/env python3
"""
10-coop-clustering - how much does the KDMP program overlap with itself?

B1 of analytics-plan.md: how many KDMP are built close enough to each other
that they compete for the same population, and does clustering show up in
performance?

Three instruments, in order of how defensible the number is:

  1. Exact nearest-neighbour distance - a cKDTree on the unit sphere gives
     every cooperative's true geodesic distance to its closest sibling, so the
     "within 500 m / 1 km / 2 km / 5 km" counts the plan asked for are exact,
     not ring guesses.
  2. H3 co-location - how many cooperatives share the same H3 cell at r7/r8/r9.
     The plan's proposed 83k x 83k pairwise matrix is 3.5 billion pairs; this
     is the plan-review's recommended replacement, and it reproduces that
     review's published numbers exactly (r9 1.5% / r8 7.7% / r7 43.0%).
  3. Clusters = groups of >=2 cooperatives in the same r8 cell (~1 km hexagon).
     This is the plan's "densest KDMP clusters" deliverable at the finest
     resolution that does not chain: chaining_check.csv documents that at any
     linking radius >= ~1 km, density-connected components merge right across
     dense Java, so a DBSCAN-style partition is not a meaningful object here.

Coordinate honesty (the load-bearing caveat): 821 cooperatives are excluded
from the clean statistics and reported separately in coord_artifacts.csv -
19 whose coordinates are impossible (reports/08-exact-geometry) and 802 that
share an exact duplicate coordinate with another cooperative (almost certainly
a geocoding fallback to an admin centroid, not physical co-location). At r9,
64% of apparent same-cell co-location is these artifacts.

Performance uses the two-hop village link (cooperative name -> land asset ->
village_stats), 79.1% coverage - see scripts/build_analysis_mart.py.

Reads only committed CSVs; no network; deterministic.

Usage: python reports/10-coop-clustering/run.py
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _lib.common import RAW, ROOT, out_dir, write_csv  # noqa: E402

OUT = out_dir(__file__)

# H3 resolution -> average hexagon edge length in km. Two cooperatives sharing
# a cell can be up to ~2x the edge apart (opposite corners of the hexagon).
RES_EDGE_KM = {7: 1.226, 8: 0.461, 9: 0.174}
CO_RES = [7, 8, 9]      # co-location resolutions
CLUSTER_RES = 8         # the ~1 km "same place" cell used for clusters
MIN_CLUSTER = 2         # two coops in one cell is already "on top of each other"

NN_BANDS = [0, 500, 1000, 2000, 5000, np.inf]
NN_LABELS = ["<500m", "500m-1km", "1-2km", "2-5km", ">5km"]

EARTH_R = 6371000.0  # m


class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def unit_sphere(lat, lon):
    """3D unit vectors from lat/lon so a cKDTree can answer geodesic NN."""
    lat = np.radians(lat.to_numpy(dtype=float))
    lon = np.radians(lon.to_numpy(dtype=float))
    clat = np.cos(lat)
    return np.column_stack([clat * np.cos(lon), clat * np.sin(lon), np.sin(lat)])


def chord_to_meters(d):
    """Chord distance on the unit sphere -> great-circle distance in metres."""
    return 2 * np.arcsin(np.clip(d / 2, 0, 1)) * EARTH_R


def admin_key(df):
    """Upper/trimmed p|d|s|v key - the mart's village-link join key."""
    return (
        df.province.astype(str).str.strip().str.upper() + "|"
        + df.district.astype(str).str.strip().str.upper() + "|"
        + df.subdistrict.astype(str).str.strip().str.upper() + "|"
        + df.village.astype(str).str.strip().str.upper()
    )


def main():
    import h3

    loc = pd.read_csv(RAW / "kopdes_locations.csv")
    print(f"loaded {len(loc):,} cooperatives\n")

    # --- 0. coordinate artifacts: impossible (08) or exact-duplicate --------
    sus = pd.read_csv(ROOT / "reports" / "08-exact-geometry" / "suspect_coordinates.csv")
    sus_ids = set(sus.cooperative_id)
    coord_counts = loc.groupby(["latitude", "longitude"]).size()
    dup_ids = set(loc.loc[
        loc.set_index(["latitude", "longitude"]).index.isin(coord_counts[coord_counts > 1].index),
        "cooperative_id",
    ])
    loc["is_artifact"] = loc.cooperative_id.isin(sus_ids) | loc.cooperative_id.isin(dup_ids)

    art = loc[loc.is_artifact].copy()
    art["type"] = np.where(art.cooperative_id.isin(sus_ids), "suspect_coordinate", "exact_duplicate_coordinate")
    art = art.merge(
        coord_counts.rename("n_at_coord").reset_index(), on=["latitude", "longitude"], how="left"
    )
    art = art[
        ["cooperative_id", "name", "province", "district", "subdistrict",
         "latitude", "longitude", "type", "n_at_coord"]
    ].sort_values(["type", "n_at_coord", "cooperative_id"], ascending=[True, False, True])
    write_csv(art, OUT / "coord_artifacts.csv",
              f"{len(art):,} coordinates that are not real co-location")

    # --- h3 cells -----------------------------------------------------------
    t0 = time.time()
    for r in CO_RES:
        loc[f"h3_r{r}"] = [h3.latlng_to_cell(a, b, r) for a, b in zip(loc.latitude, loc.longitude)]
    print(f"h3 cells computed in {time.time()-t0:.1f}s\n")

    clean = loc[~loc.is_artifact]
    print(f"{len(loc)-len(clean):,} coordinate artifacts set aside; {len(clean):,} clean cooperatives\n")

    # --- 1. co-location: how many share a cell with at least one other -------
    rows = []
    for r in CO_RES:
        for mask, excl in ((loc, "all"), (clean, "clean")):
            vc = mask[f"h3_r{r}"].value_counts()
            shared = vc[vc > 1]
            rows.append({
                "res": r,
                "approx_cell_edge_km": RES_EDGE_KM[r],
                "exclusion": excl,
                "coops": len(mask),
                "n_cells_occupied": len(vc),
                "cells_with_2plus": len(shared),
                "coops_sharing_with_other": int(shared.sum()),
                "pct_of_coops": round(100 * int(shared.sum()) / len(mask), 2),
                "max_in_one_cell": int(vc.max()),
            })
    co = pd.DataFrame(rows)
    write_csv(co, OUT / "co_location.csv")
    for _, row in co[co.exclusion == "clean"].iterrows():
        print(f"  r{row.res}: {row.coops_sharing_with_other:,} coops "
              f"({row.pct_of_coops:.1f}%) share a cell with >=1 other; max {row.max_in_one_cell} in one cell")
    print()

    # --- 2. exact nearest-neighbour distances (clean set only) ---------------
    print("computing exact nearest-neighbour distances...")
    t0 = time.time()
    xyz = unit_sphere(clean.latitude, clean.longitude)
    d, _ = cKDTree(xyz).query(xyz, k=2)  # d[:,0] is self; d[:,1] nearest other
    clean["m_to_nearest_other"] = chord_to_meters(d[:, 1])
    print(f"  cKDTree in {time.time()-t0:.1f}s for {len(clean):,} points\n")

    clean["nn_band"] = pd.cut(clean.m_to_nearest_other, NN_BANDS, labels=NN_LABELS)
    band = clean.groupby("nn_band", observed=True).size().reset_index(name="cooperatives")
    band["pct_of_clean"] = (100 * band.cooperatives / len(clean)).round(2)
    write_csv(band, OUT / "nn_bands.csv")

    within = pd.DataFrame({
        "distance_m": [500, 1000, 2000, 5000],
        "coops_with_another_within": [int((clean.m_to_nearest_other <= m).sum()) for m in (500, 1000, 2000, 5000)],
    })
    within["pct_of_clean"] = (100 * within.coops_with_another_within / len(clean)).round(2)
    write_csv(within, OUT / "nn_within.csv")
    print("share of cooperatives with another cooperative within:")
    print(within.to_string(index=False))
    print()

    # --- 3. clusters: co-location groups in the same r8 cell -----------------
    cell_counts = clean.h3_r8.value_counts()
    shared_cells = cell_counts[cell_counts >= MIN_CLUSTER].index
    clean["cluster_id"] = clean.h3_r8.where(clean.h3_r8.isin(shared_cells))
    clean["cluster_size"] = clean.h3_r8.map(cell_counts).where(clean.cluster_id.notna())

    densest = (
        clean[clean.cluster_id.notna()]
        .groupby("cluster_id", as_index=False)
        .agg(size=("cooperative_id", "size"),
             province=("province", "first"),
             district=("district", "first"))
        .sort_values("size", ascending=False)
        .head(20)
    )
    densest["centroid_lat"], densest["centroid_lon"] = zip(
        *[h3.cell_to_latlng(c) for c in densest.cluster_id]
    )
    names = (
        clean[clean.cluster_id.notna()]
        .groupby("cluster_id")["name"]
        .apply(lambda s: " | ".join(s))
        .rename("member_cooperatives")
    )
    densest = densest.merge(names, on="cluster_id", how="left")
    write_csv(densest, OUT / "densest_cells.csv", "top 20 r8 cells by cooperative count")

    summ = (
        clean[clean.cluster_id.notna()]
        .groupby("cluster_id", as_index=False)
        .agg(size=("cooperative_id", "size"),
             province=("province", lambda s: s.mode().iat[0]),
             n_districts=("district", "nunique"),
             centroid_lat=("latitude", "mean"),
             centroid_lon=("longitude", "mean"),
             median_m_to_nearest_other=("m_to_nearest_other", "median"))
        .sort_values("size", ascending=False)
    )
    write_csv(summ, OUT / "clusters.csv", f"{len(summ):,} same-cell clusters (r8, size>={MIN_CLUSTER})")

    dist_bins = pd.cut(summ["size"], [1, 2, 5, 10, 20, 50, 100, np.inf],
                       labels=["2", "3-5", "6-10", "11-20", "21-50", "51-100", "101+"])
    dist = (
        summ.groupby(dist_bins, observed=True)
        .agg(n_clusters=("size", "size"), coops=("size", "sum"))
        .reset_index()
        .rename(columns={"size": "cluster_size_band"})
    )
    write_csv(dist, OUT / "cluster_size_distribution.csv")

    # --- 4. performance: two-hop village link -------------------------------
    la = pd.read_csv(RAW / "kopdes_land_assets.csv")
    vs = pd.read_csv(RAW / "kopdes_stats_village.csv").drop_duplicates("village_id")
    la["_key"] = admin_key(la)
    vs["_key"] = admin_key(vs)
    vs = vs.drop_duplicates("_key")                      # village_id dedup should guarantee this
    la = la.sort_values("asset_id").drop_duplicates("cooperative")   # first asset per cooperative
    perf = la[["cooperative", "_key"]].merge(
        vs[["_key", "village_id", "transaction_value", "transaction_volume",
            "savings_total_amount", "accounts_count", "npwp_count", "nib_count"]],
        on="_key", how="left",
    )
    perf["_name"] = perf.cooperative.str.strip().str.upper()
    perf = perf.drop_duplicates("_name")
    clean["_name"] = clean.name.str.strip().str.upper()
    clean = clean.merge(
        perf.drop(columns=["cooperative", "_key"])[["_name", "village_id", "transaction_value",
                                                    "transaction_volume", "savings_total_amount",
                                                    "accounts_count", "npwp_count", "nib_count"]],
        on="_name", how="left",
    ).drop(columns=["_name"])
    n_linked = int(clean.village_id.notna().sum())
    print(f"village link reached {n_linked:,} of {len(clean):,} cooperatives "
          f"({100*n_linked/len(clean):.1f}%)\n")

    # cluster summary gains performance columns
    summ = summ.merge(
        clean[clean.cluster_id.notna()]
        .groupby("cluster_id", as_index=False)
        .agg(n_linked=("village_id", "count"),
             sum_transaction_value=("transaction_value", "sum"),
             n_reporting=("transaction_value", lambda s: int((s > 0).sum()))),
        on="cluster_id", how="left",
    )
    summ["sum_transaction_value"] = summ.sum_transaction_value.fillna(0)
    write_csv(summ, OUT / "clusters.csv", f"{len(summ):,} same-cell clusters (r8, size>={MIN_CLUSTER})")

    # clustered vs isolated, over the village-linked set
    linked = clean[clean.village_id.notna()].copy()
    linked["group"] = np.where(linked.cluster_id.notna(), "clustered", "isolated")
    rows = []
    total_value = linked.transaction_value.sum()
    for g, sub in linked.groupby("group", observed=True):
        rep = sub[sub.transaction_value > 0]
        rows.append({
            "group": g,
            "n_linked": len(sub),
            "pct_reporting_transaction": round(100 * len(rep) / len(sub), 2),
            "mean_transaction_value_per_coop": round(sub.transaction_value.mean(), 0),
            "median_transaction_value_reporting": round(rep.transaction_value.median(), 0) if len(rep) else None,
            "share_of_linked_value": round(100 * sub.transaction_value.sum() / total_value, 2),
            "pct_with_savings": round(100 * (sub.savings_total_amount > 0).mean(), 2),
            "median_savings_amount": round(sub.savings_total_amount.median(), 0),
            "median_accounts_count": round(sub.accounts_count.median(), 0),
        })
    comp = pd.DataFrame(rows)
    comp = pd.concat([comp, pd.DataFrame([{
        "group": "all", "n_linked": len(linked),
        "pct_reporting_transaction": round(100 * (linked.transaction_value > 0).mean(), 2),
        "mean_transaction_value_per_coop": round(linked.transaction_value.mean(), 0),
        "median_transaction_value_reporting": round(linked.loc[linked.transaction_value > 0, "transaction_value"].median(), 0),
        "share_of_linked_value": 100.0,
        "pct_with_savings": round(100 * (linked.savings_total_amount > 0).mean(), 2),
        "median_savings_amount": round(linked.savings_total_amount.median(), 0),
        "median_accounts_count": round(linked.accounts_count.median(), 0),
    }])], ignore_index=True)
    write_csv(comp, OUT / "cluster_vs_isolated.csv")
    print(comp.to_string(index=False))
    print()

    # does more clustering correlate with lower per-cooperative output?
    cl = linked[linked.cluster_id.notna()]
    rho = cl.cluster_size.corr(cl.transaction_value, method="spearman")
    rho_rep = cl[cl.transaction_value > 0].cluster_size.corr(
        cl[cl.transaction_value > 0].transaction_value, method="spearman")
    write_csv(pd.DataFrame([
        {"subset": "all linked clustered", "n": len(cl), "spearman_cluster_size_vs_value": round(rho, 4)},
        {"subset": "reporting only", "n": int((cl.transaction_value > 0).sum()),
         "spearman_cluster_size_vs_value": round(rho_rep, 4)},
    ]), OUT / "cluster_size_vs_value.csv")
    print(f"spearman(cluster_size, transaction_value): all={rho:.3f}, reporting-only={rho_rep:.3f}\n")

    # --- 5. chaining check: why a DBSCAN partition is not used ---------------
    def components(K):
        occ = sorted(clean.h3_r8.unique())
        idx = {c: i for i, c in enumerate(occ)}
        uf = UnionFind(len(occ))
        for c in occ:
            for nb in h3.grid_disk(c, K):
                if nb in idx:
                    uf.union(idx[c], idx[nb])
        comp = {c: uf.find(idx[c]) for c in occ}
        sz = clean.h3_r8.map(comp).groupby(clean.h3_r8.map(comp)).size()
        big = sz[sz >= 3]
        return len(big), int(big.sum()), int(big.max())

    chain = []
    for K, km in ((1, 0.9), (2, 1.4), (4, 1.8)):
        n_comp, n_coops, maxsz = components(K)
        chain.append({"r8_k_rings": K, "approx_link_km": km,
                      "components_with_3plus": n_comp, "coops_in_components": n_coops,
                      "pct_of_clean": round(100 * n_coops / len(clean), 2),
                      "max_component_size": maxsz})
    write_csv(pd.DataFrame(chain), OUT / "chaining_check.csv")
    print("density-connected components (clean set) - the chaining problem:")
    print(pd.DataFrame(chain).to_string(index=False))
    print()

    # --- per-cooperative deliverable (map-ready) -----------------------------
    out = clean[
        ["cooperative_id", "name", "province", "district", "subdistrict",
         "latitude", "longitude", "m_to_nearest_other", "nn_band",
         "cluster_id", "cluster_size", "village_id",
         "transaction_value", "savings_total_amount", "accounts_count"]
    ].copy()
    out["has_reported_transaction"] = np.where(out.transaction_value.notna(), out.transaction_value > 0, np.nan)
    write_csv(out, OUT / "nn_distances.csv", "per-cooperative; feeds the screengrid views")


if __name__ == "__main__":
    main()
