# KDMP Analytics Plan — Critical Investigation Through Data

**Context**: The KDMP (_Koperasi Desa Merah Putih_) program aims to establish ~83,000 village cooperatives nationwide, each funded with significant state budget. Public criticism has centered on three recurring themes: **(1)** points are established in remote, inaccessible locations where they cannot serve communities effectively; **(2)** many KDMP sit in close proximity to existing minimarkets (Alfamart, Indomaret) and other cooperatives, raising questions of redundancy and cannibalization; and **(3)** budget absorption appears misaligned with actual operational output — money is spent but transaction volumes, member activity, and facility completion remain low.

This document outlines a data-driven investigation into these claims, structured as concrete analytical modules. Each module specifies the question it answers, the data it requires, the methodology, and the expected deliverable.

---

## Data Inventory (what we already have)

| Dataset                                    | Rows                                | Key Fields                                                                                                                                                         |
| ------------------------------------------ | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `kopdes_locations.csv`                     | ~83k                                | `cooperative_id`, `name`, `province`, `district`, `subdistrict`, `lat`, `lon`                                                                                      |
| `kopdes_land_assets.csv`                   | ~66k                                | `asset_id`, `cooperative` (name), `status` (Terverifikasi/Sedang Diverifikasi/Tidak Ada Lahan), `surveyor` (TNI/Agrinas/KOPERASI), `lat`, `lon`                    |
| `kopdes_national_summary.csv`              | 1                                   | 20+ national aggregates: total cooperatives, legal entity counts, NPWP/NIB compliance, land verification counts, IDR 179.5T total transaction volume, 1.8M members |
| `kopdes_stats_province.csv`                | 38                                  | Per-province: cooperatives count, NPWP/NIB/RAT counts, transaction volume/value, savings (pokok + wajib), health score (all "unhealthy", index 51-57)              |
| `kopdes_stats_district.csv`                | ~514                                | Same stat columns at district level                                                                                                                                |
| `kopdes_stats_subdistrict.csv`             | ~7.2k                               | Same stat columns at subdistrict level                                                                                                                             |
| `kopdes_stats_village.csv`                 | ~83k                                | Same stat columns at village level                                                                                                                                 |
| `kopdes_province_rat_and_construction.csv` | 38                                  | RAT completion (all 0), construction progress buckets (0-20%, 21-50%, 51-75%, 76-99%, 100%)                                                                        |
| `kopdes_province_top_products.csv`         | ~38 x N                             | `product`, `volume`, `value` per province                                                                                                                          |
| Geo boundaries                             | Provinsi, Kab/Kota, Kecamatan, Desa | BIG-derived polygons, simplified, linked via name matching                                                                                                         |
| `data/osm/indonesia_roads.gpkg`            | ~4.5M segments                      | Nationwide road network: `osm_id`, `highway`, `name`, `oneway`, `maxspeed`, `surface`, `ref`, `lanes`, `bridge`, `tunnel`                                          |
| `data/osm/indonesia_minimarkets.gpkg`      | ~10.6k POIs                         | Minimarket/supermarket POIs: `osm_id`, `name`, `brand`, `brand_label`, `shop`, `addr:*` — 16 brand categories                                                      |
| `data/population/kontur_population_ID.gpkg` | ~1.8M cells                         | Kontur 400m H3 hexagons: `h3` (res 10), `population` — fusion of GHSL, Facebook HRSL, Microsoft Buildings, OSM                                                    |

---

## Module A — Accessibility & Remote Location Analysis

> _"KDMP dibangun di lokasi terpencil, tidak bisa diakses masyarakat."_

### A1. Distance-to-Nearest-Settlement

**Question**: How far is each KDMP from the nearest population center?

**Method**:

- Index KDMP points and population grid (WorldPop ~100m or Kontur ~400m H3) into H3 resolution 9 (~2 km edge).
- Compute haversine distance from each KDMP to the centroid of the nearest populated cell.
- Classify KDMP into accessibility bands: <1 km (walkable), 1-5 km (motorbike), 5-15 km (vehicle), >15 km (remote).

**Deliverable**: Histogram and map of KDMP by distance band, per province. Table of "most remote KDMP" (>15 km from any population).

### A2. Population Catchment Analysis

**Question**: What % of Indonesia's population lives within reasonable reach of a KDMP?

**Method**:

- Generate H3 k-ring catchments (k=1 -> ~5 km radius; k=2 -> ~10 km; k=3 -> ~15 km) around each KDMP at resolution 8 or 9.
- Join with population raster aggregated to H3 cells.
- Compute: (a) total population covered by at least one KDMP; (b) population in "coverage deserts" (zero KDMP within 15 km); (c) per-province coverage rates.

**Deliverable**: National population coverage map; province ranking by % uncovered population; list of top-100 most underserved subdistricts.

### A3. Terrain & Geographic Barrier Analysis

**Question**: How many KDMP are placed in locations with prohibitive terrain (steep slopes, water barriers, no road access)?

**Method**:

- Overlay KDMP points with SRTM/DEM elevation and slope rasters.
- Compute distance from each KDMP to nearest OSM road segment.
- Flag KDMP on small islands with no bridge/ferry connection to the main island of that province.
- Classify: accessible by road (<500 m), trail access (500 m-2 km), no road access (>2 km).

**Deliverable**: Road-accessibility classification per KDMP; map of KDMP on isolated islands; slope-risk flagged cooperatives.

### A4. Correlate Remoteness with Performance

**Question**: Do remote KDMP actually underperform, or is the criticism overstated?

**Method**:

- Join distance-to-population metric (from A1) with village-level transaction data from `kopdes_stats_village.csv`.
- Compare mean transaction volume/value, savings amounts, and member counts across accessibility bands.
- Statistical test (Kruskal-Wallis or ANOVA) for significant difference between bands.

**Deliverable**: Scatter plot of remoteness vs. transaction volume; box plots by accessibility band; province-adjusted comparisons.

---

## Module B — Proximity & Cannibalization Analysis

> _"KDMP dibangun terlalu dekat dengan minimarket dan koperasi lain — tumpang tindih, boros anggaran."_

### B1. KDMP-to-KDMP Proximity

**Question**: How many KDMP are clustered so close to each other that they compete for the same population?

**Method**:

- Pairwise distance matrix for all ~83k points (use spatial index: `s2geometry` or `scipy.spatial.cKDTree` with Haversine).
- Count KDMP within 500 m, 1 km, 2 km, 5 km of each other.
- Identify clusters: run DBSCAN (eps=2 km, min_samples=3) to find KDMP-dense areas.
- Join cluster membership with village-level stats: do clustered KDMP have lower per-unit transaction volumes?

**Deliverable**: Cluster map showing over-concentration; table of top-20 densest KDMP clusters; per-unit transaction comparison (clustered vs. isolated).

### B2. Overlap with Existing Cooperatives

**Question**: How many KDMP were established in villages that already had an active KUD or other cooperative?

**Method**:

- Requires external data: registry of existing (non-KDMP) cooperatives from Kemenkop or BPS PODES.
- Spatial join at desa level: flag desa that already had >=1 cooperative pre-KDMP.
- Compare performance: KDMP in "cooperative-dense" desa vs. KDMP in previously unserved desa.

**Deliverable**: Desa-level duplication map; performance differential between "new coverage" and "duplicate coverage" KDMP.

### B3. Proximity to Modern Retail (Minimarket Competition)

**Question**: How close is each KDMP to the nearest Alfamart, Indomaret, or other modern retail outlet?

**Method**:

- Requires external data: minimarket locations (Alfamart/Indomaret POI dataset — available via OSM or commercial sources).
- Compute nearest-neighbor distance from KDMP to minimarket.
- Classify: <500 m (direct competition), 500 m-1 km (overlapping catchment), >1 km (distinct catchment).
- Cross-reference with product data: do KDMP near minimarkets sell different products (fertilizer, LPG) vs. minimarket-overlapping products (sembako)?

**Deliverable**: KDMP-minimarket proximity map; product mix analysis by proximity band; case studies of high-overlap areas.

---

## Module C — Budget Efficiency & Absorption Analysis

> _"Anggaran besar tapi transaksi rendah, pembangunan mangkrak, RAT tidak jalan."_

### C1. Construction Progress vs. Operational Output

**Question**: Do provinces with higher construction completion rates also show higher transaction activity — or is there a disconnect?

**Method**:

- From `kopdes_province_rat_and_construction.csv`: compute % of KDMP at each construction tier per province.
- From `kopdes_stats_province.csv`: transaction volume, transaction value, savings amounts.
- Correlation analysis: construction progress vs. transaction activity, member counts, savings.
- Scatter plot with province labels; identify outliers (high construction, low activity -> possible "infrastructure without operations").

**Deliverable**: Construction-to-activity correlation matrix; flagged provinces where buildings exist but transactions don't.

### C2. Land Verification Bottleneck Analysis

**Question**: What is the status of land asset verification, and does it correlate with operational performance?

**Method**:

- From `kopdes_land_assets.csv`: aggregate by province and status (`Terverifikasi`, `Sedang Diverifikasi`, `Tidak Ada Lahan`, `Lahan Diajukan`).
- Cross with transaction stats: do provinces with higher verification rates have better transaction metrics?
- Analyze surveyor type (TNI vs. Agrinas vs. KOPERASI) against verification speed and success rate.
- Identify provinces where large % of land is "Tidak Ada Lahan" — possible indicator of budget allocated to cooperatives without physical presence.

**Deliverable**: Land status Sankey diagram per province; surveyor efficiency comparison; "ghost KDMP" identification.

### C3. RAT (Annual Member Meeting) Compliance

**Question**: All 38 provinces show `total_rat = 0` and `total_done_rat = 0`. Is this a data collection failure or are RAT genuinely not happening?

**Method**:

- Verify the zero values against the raw API responses (check extraction scripts).
- If genuine: RAT is a legal requirement under the Cooperatives Law (UU No. 25/1992). Zero compliance nationwide is a major governance finding.
- Cross-reference: if RAT is zero everywhere, examine whether the `health_score` model already penalizes this or ignores it.
- If the data is missing/not collected: flag this as a critical data infrastructure gap.

**Deliverable**: RAT compliance report; legal/regulatory context framing; recommendation to Kemenkop on data collection.

### C4. Per-Unit Economic Efficiency

**Question**: What is the "bang for buck" — transaction value per cooperative, per province?

**Method**:

- Normalize all financial metrics per cooperative: `transaction_value / cooperatives`, `savings_total / cooperatives`, `simpanan_pokok_members / cooperatives`.
- Rank provinces by efficiency.
- Identify provinces that have many cooperatives but very low per-unit activity.
- If budget allocation data can be sourced (e.g., DIPA/APBN per cooperative), compute ROI: `transaction_value / budget_allocation`.

**Deliverable**: Province efficiency ranking table; per-unit metric dashboards; budget ROI estimates (with external data).

---

## Module D — Performance & Health Diagnostics

> _"Semua provinsi dapat status 'tidak sehat' — apa yang sebenarnya terjadi?"_

### D1. Health Score Decomposition

**Question**: All 38 provinces score "unhealthy" with indices tightly clustered between 51-57. What drives this uniformity, and what are the actual discriminating factors?

**Method**:

- Since we don't have the raw health score components, infer them: correlate health index against all available stats (NPWP %, NIB %, RAT count, transaction volume, savings, member counts).
- Run PCA or factor analysis to identify which dimensions actually vary and which are universally low.
- Hypothesis: the health model may be dominated by RAT compliance (all zero), making all provinces uniformly unhealthy regardless of other performance.

**Deliverable**: Health score driver analysis; recommendation on whether the health model is fit for purpose.

### D2. Product Mix & Economic Role Analysis

**Question**: What are KDMP actually selling, and does the product mix align with their stated mission (sembako, agriculture inputs, financial services)?

**Method**:

- From `kopdes_province_top_products.csv`: categorize products (sembako, fertilizer/seeds, LPG/energy, other).
- Compute product diversity per province (Shannon index or simple category count).
- Identify provinces where product mix is dominated by a single category (low resilience).
- Cross with transaction volume: do diversified KDMP perform better?

**Deliverable**: Product category composition charts per province; diversification-vs-performance analysis.

### D3. NPWP & NIB Compliance Gap

**Question**: ~3,600 cooperatives lack NPWP (~4.3%) and ~22,600 lack NIB (~27%). Is there a geographic or performance pattern to non-compliance?

**Method**:

- Map NPWP and NIB compliance rates at province, district, and subdistrict levels.
- Test whether non-compliant KDMP have lower transaction activity (are they "zombie" cooperatives?).
- Identify worst-offender districts.

**Deliverable**: NPWP/NIB compliance maps; correlation with transaction activity; zombie cooperative risk index.

---

## Module E — Data Quality & Integrity

> Foundational: before any analytics, we must establish trust in the data.

### E1. Coordinate Validation

**Question**: What % of KDMP and land asset points are geolocated incorrectly (in the ocean, outside Indonesia, in the wrong province)?

**Method**:

- Point-in-polygon test: are KDMP `(lat, lon)` within the province polygon they claim?
- Check for points inside the ocean using a land mask (GADM or Natural Earth coastline).
- Check for duplicate coordinates (multiple cooperatives at the exact same lat/lon).
- Flag points that moved >50 km during name-matching geo-linking.

**Deliverable**: Data quality report: % ocean points, % wrong-province points, % duplicates; list of flagged cooperatives for manual review.

### E2. Name Matching Audit

**Question**: The geo pipeline links stats to boundaries via fuzzy name matching. What's the error rate?

**Method**:

- Review all `_unmatched.csv` files from the geo pipeline.
- Sample matched rows and manually verify against authoritative BPS name lists.
- Identify systematic mismatches (e.g., abbreviated names, spelling variants, SIMKOPDES using unofficial names).

**Deliverable**: Match quality report; list of provinces/districts with poorest match rates; recommendations for improving the join key.

### E3. Temporal Consistency

**Question**: Can we establish a time series? Is the data snapshot reproducible?

**Method**:

- Document the extraction date for the current snapshot (2026-08-05).
- Run the extract scripts periodically and diff the results.
- Track: cooperatives added/removed, coordinate changes, status transitions.

**Deliverable**: Change-detection pipeline design; first delta report comparing two snapshots.

---

## Additional Analytical Modules

### F1. Transaction Volume Anomaly Detection

**Question**: Are there provinces or districts with transaction volumes that are statistically implausible (either suspiciously high or suspiciously low)?

**Method**: Fit a per-province expected transaction model based on cooperative count, population, and product diversity. Flag outliers (>2.5 sigma). Investigate top outliers for data entry errors or genuine anomalies.

### F2. Savings Behavior Analysis

**Question**: The data includes `simpanan_pokok` (mandatory) and `simpanan_wajib` (compulsory monthly) metrics. Are members actually saving, or are these accounts dormant?

**Method**: Compute savings-per-member ratios. Compare `simpanan_pokok` vs. `simpanan_wajib` ratios — if wajib >> pokok, it suggests active ongoing saving. If both are near zero, the cooperative may be inactive.

### F3. Island Group Comparative Analysis

**Question**: Java vs. Sumatra vs. Kalimantan vs. Sulawesi vs. Papua vs. Nusa Tenggara vs. Maluku — how does KDMP performance differ across Indonesia's major island groups?

**Method**: Map provinces to island groups. Compare all metrics (transaction volume, savings, construction progress, land verification, health scores) across groups. Control for cooperative count and population.

### F4. Top Product Cross-Province Overlap

**Question**: Do neighboring provinces sell the same products, or is there meaningful local specialization?

**Method**: Compute Jaccard similarity of top-10 products between all province pairs. Cluster provinces by product similarity. Identify provinces with unique product profiles.

---

## External Data Wishlist

To fully execute the modules above, we need these external datasets:

| Dataset                                  | Needed For | Source                         | Priority | Status    |
| ---------------------------------------- | ---------- | ------------------------------ | -------- | --------- |
| Population grid (100m-1km)               | A1, A2     | WorldPop, Kontur, GHSL         | Critical | ✅ Kontur 400m H3 acquired (1.8M cells, 164 MB) |
| OSM road network (Indonesia extract)     | A3         | Geofabrik, PPP-OSM-ID          | Critical | ✅ Acquired (4.5M segments, 1.6 GB GPKG) |
| SRTM/DEM elevation                       | A3         | USGS EarthExplorer, DEMNAS-BIG | High     |           |
| Minimarket POI (Alfamart, Indomaret)     | B3         | OSM, commercial                | High     | ✅ Acquired (10.6k nodes, 1.7 MB GPKG) |
| Existing cooperative registry (pre-KDMP) | B2         | Kemenkop, BPS PODES            | High     |
| APBN/DIPA budget allocation per KDMP     | C4         | Kemenkeu, Kemenkop             | High     |
| Poverty/Vulnerability maps               | A4, C4     | BPS, SMERU, World Bank         | Medium   |
| 3T area boundaries                       | A4         | Kemendes PDTT                  | Medium   |
| Ferry & boat route network               | A3         | OSM, ASDP, Pelni               | Medium   |
| Land cover/land use                      | A3         | KLHK, ESA WorldCover           | Medium   |
| BPS desa-level population                | A2         | BPS                            | Medium   |

---

## Implementation Roadmap

### Phase 0 — Data Quality (Week 1)

- [ ] Module E1: Coordinate validation -> clean point dataset
- [ ] Module E2: Name matching audit -> verified geo-linked data
- [ ] Set up reproducible extraction + validation pipeline

### Phase 1 — Core Spatial Analytics (Weeks 2-3)

- [ ] Module A1: Distance-to-settlement (now has Kontur population grid ✅)
- [ ] Module B1: KDMP-to-KDMP proximity & clustering
- [ ] Module C1: Construction vs. output correlation
- [ ] Module C2: Land verification analysis
- [ ] Module D2: Product mix analysis

### Phase 2 — Enriched Analytics (Weeks 4-6)

- [ ] Module A2: Population catchment (Kontur H3 acquired ✅)
- [ ] Module A3: Terrain & road accessibility (OSM roads acquired ✅; DEM still needed)
- [ ] Module B3: Minimarket proximity (minimarket POIs acquired ✅)
- [ ] Module C3: RAT compliance investigation
- [ ] Module D1: Health score decomposition

### Phase 3 — Synthesis & Storytelling (Weeks 7-8)

- [ ] Module C4: Per-unit efficiency & budget ROI
- [ ] Module D3: NPWP/NIB compliance mapping
- [ ] Cross-module synthesis: integrated narrative on KDMP effectiveness
- [ ] Interactive dashboard (kepler.gl or custom web map) with all layers
- [ ] Policy brief: findings + actionable recommendations

---

## Recommended Tech Stack

| Layer                | Tools                                                                          |
| -------------------- | ------------------------------------------------------------------------------ |
| **Data processing**  | Python: `pandas`/`polars`, `geopandas`, `shapely`, `h3`, `scipy`               |
| **Spatial analysis** | `s2geometry`, `scipy.spatial.cKDTree`, `DBSCAN` (sklearn), `rasterio`, `osmnx` |
| **Heavy lifting**    | DuckDB + spatial extension (for >100k pairwise operations)                     |
| **Visualization**    | kepler.gl (hexagon maps), Altair/Plotly (charts), Folium/Maplibre (web)        |
| **Reporting**        | Quarto or Jupyter notebooks -> static HTML reports                             |
| **Versioning**       | Git + DVC for large external datasets                                          |

---

## Key Hypotheses to Test

1. **H1**: KDMP in remote locations (>5 km from population) have significantly lower transaction volumes than accessible ones.
2. **H2**: Clustered KDMP (<2 km apart) have lower per-unit transaction volume than isolated ones — consistent with cannibalization.
3. **H3**: Provinces with higher construction completion rates do NOT show proportionally higher transaction activity — suggesting infrastructure-first, operations-second problems.
4. **H4**: All-province "unhealthy" classification is driven primarily by zero RAT compliance, masking variation in other performance dimensions.
5. **H5**: A significant fraction (>5%) of KDMP coordinates do not fall within their claimed province boundary — indicating systematic data quality issues.
6. **H6**: KDMP near minimarkets (<1 km) sell a different product mix than those far from minimarkets — suggesting market segmentation rather than direct competition.
