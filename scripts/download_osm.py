#!/usr/bin/env python3
"""
Download OSM data for Indonesia: road network + minimarket POIs.

Two output files go to data/osm/:
  - indonesia_roads.gpkg     — nationwide road network (filtered highways)
  - indonesia_minimarkets.gpkg — Alfamart, Indomaret, Alfamidi, etc.

Usage:
  python scripts/download_osm.py              # both roads + POIs
  python scripts/download_osm.py --roads-only
  python scripts/download_osm.py --poi-only
  python scripts/download_osm.py --no-download # use existing PBF

Data sources:
  - Roads: Geofabrik Indonesia PBF (~1.6 GB) -> extracted with pyrosm -> GeoPackage
  - POIs:  Overpass API (nodes query, ~10k points) -> GeoPackage
"""

import argparse
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Path config
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "osm"
PBF_URL = "https://download.geofabrik.de/asia/indonesia-latest.osm.pbf"
PBF_PATH = DATA_DIR / "indonesia-latest.osm.pbf"
ROADS_GPKG = DATA_DIR / "indonesia_roads.gpkg"
POI_GPKG = DATA_DIR / "indonesia_minimarkets.gpkg"

# Highway values we want in the road network (ordered by importance)
HIGHWAY_TAGS = [
    "motorway", "motorway_link",
    "trunk", "trunk_link",
    "primary", "primary_link",
    "secondary", "secondary_link",
    "tertiary", "tertiary_link",
    "residential", "unclassified",
    "living_street", "road",
    "track",           # rural / unpaved — useful for remote accessibility
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def file_size_mb(path: Path) -> str:
    sz = path.stat().st_size
    return f"{sz / 1_048_576:.1f} MB"


# ---------------------------------------------------------------------------
# Step 1 — Download Indonesia PBF
# ---------------------------------------------------------------------------

def download_pbf():
    """Download Geofabrik Indonesia PBF with progress bar."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if PBF_PATH.exists():
        print(f"[skip] PBF already cached: {PBF_PATH}  ({file_size_mb(PBF_PATH)})")
        return

    print(f"Downloading Indonesia OSM extract from Geofabrik …")
    print(f"  {PBF_URL}")
    try:
        import requests
        from tqdm import tqdm
    except ImportError:
        print("  Please install requests + tqdm: pip install requests tqdm")
        sys.exit(1)

    resp = requests.get(PBF_URL, stream=True, timeout=30)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))

    with open(PBF_PATH, "wb") as f, tqdm(
        desc="  PBF", total=total, unit="B", unit_scale=True, unit_divisor=1024
    ) as bar:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            size = f.write(chunk)
            bar.update(size)

    print(f"  Done → {PBF_PATH}  ({file_size_mb(PBF_PATH)})")


# ---------------------------------------------------------------------------
# Step 2 — Extract roads (pyrosm for convenience, osmium-tool CLI for speed)
# ---------------------------------------------------------------------------
# Step 2 — Extract roads with osmium (streaming to GeoJSONSeq then GPKG)
# ---------------------------------------------------------------------------

ROAD_COLS = [
    "osm_id", "highway", "name", "oneway", "maxspeed",
    "surface", "ref", "lanes", "bridge", "tunnel", "geometry",
]


def extract_roads():
    """Extract highway ways from PBF: osmium stream -> GeoPackage."""
    if ROADS_GPKG.exists():
        print(f"[skip] Roads already extracted: {ROADS_GPKG}  ({file_size_mb(ROADS_GPKG)})")
        return

    try:
        import osmium
        import json
        import geopandas as gpd
    except ImportError:
        print("[error] Install osmium + geopandas: pip install osmium geopandas")
        sys.exit(1)

    print("\n=== Extracting road network ===")
    print("  Streaming highway ways from PBF (~15-20 min, ~2.5 GB temp file) ...")

    geojsonseq = DATA_DIR / "indonesia_roads.geojsonseq"

    class RoadHandler(osmium.SimpleHandler):
        def __init__(self, out_path):
            super().__init__()
            self.f = open(out_path, "w", encoding="utf-8")
            self.count = 0

        def way(self, w):
            tags = {t.k: t.v for t in w.tags}
            hw = tags.get("highway", "")
            if hw not in HIGHWAY_TAGS:
                return
            coords = []
            for ref in w.nodes:
                loc = ref.location
                if loc.valid():
                    coords.append([loc.lon, loc.lat])
            if len(coords) < 2:
                return
            self.f.write(json.dumps({
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coords},
                "properties": {
                    "osm_id": w.id, "highway": hw,
                    "name": tags.get("name", ""),
                    "oneway": tags.get("oneway", ""),
                    "maxspeed": tags.get("maxspeed", ""),
                    "surface": tags.get("surface", ""),
                    "ref": tags.get("ref", ""),
                    "lanes": tags.get("lanes", ""),
                    "bridge": tags.get("bridge", ""),
                    "tunnel": tags.get("tunnel", ""),
                },
            }) + "\n")
            self.count += 1
            if self.count % 50000 == 0:
                print(f"  ... {self.count:,} road segments")

        def close(self):
            self.f.close()

    t0 = time.time()
    handler = RoadHandler(geojsonseq)
    handler.apply_file(str(PBF_PATH), locations=True)
    handler.close()
    print(f"  Extracted {handler.count:,} road segments in {time.time()-t0:.0f}s")

    # Convert to compact GeoPackage
    print(f"  Converting {file_size_mb(geojsonseq)} GeoJSONSeq to GeoPackage (~5-10 min) ...")
    t0 = time.time()
    roads = gpd.read_file(geojsonseq)
    cols = [c for c in ROAD_COLS if c in roads.columns]
    roads = roads[cols]
    ROADS_GPKG.parent.mkdir(parents=True, exist_ok=True)
    roads.to_file(ROADS_GPKG, layer="roads", driver="GPKG")
    print(f"  Roads saved -> {ROADS_GPKG}  ({file_size_mb(ROADS_GPKG)} in {time.time()-t0:.0f}s)")

    # Remove large intermediate file
    geojsonseq.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Step 3 — Extract minimarket POIs via Overpass API
# ---------------------------------------------------------------------------

# Query nodes only — ways/areas are too heavy for nationwide Overpass queries.
# Node coverage for convenience stores in Indonesia is good (~10k nodes).
# We save the raw result so it can be enriched with PBF-extracted ways later.
OVERPASS_POI_QUERY = """
[out:json][timeout:180];
area["ISO3166-1"="ID"]->.ina;
(
  node["shop"="convenience"](area.ina);
  node["shop"="supermarket"](area.ina);
  node["shop"="department_store"](area.ina);
);
out body;
"""


def classify_brand(name: str, brand: str, operator: str) -> str:
    """Tag each POI with a normalized brand label based on name/brand/operator."""
    combined = f"{name} {brand} {operator}"

    if "alfamidi" in combined:
        return "Alfamidi"
    if "alfamart" in combined:
        return "Alfamart"
    if "indomaret" in combined:
        return "Indomaret"
    if "super indo" in combined or "superindo" in combined:
        return "Super Indo"
    if "transmart" in combined or "carrefour" in combined:
        return "Transmart / Carrefour"
    if "family" in combined and "mart" in combined:
        return "FamilyMart"
    if "circle k" in combined:
        return "Circle K"
    if "lawson" in combined:
        return "Lawson"
    if "giant" in combined:
        return "Giant"
    if "hypermart" in combined:
        return "Hypermart"
    if "indogrosir" in combined:
        return "Indogrosir"
    if "aeon" in combined:
        return "AEON"
    if "lotte" in combined:
        return "Lotte Mart"
    if "yogya" in combined:
        return "Yogya / Toserba"
    if "ramayana" in combined:
        return "Ramayana"
    if "matahari" in combined:
        return "Matahari"

    return "other"


def extract_pois_overpass():
    """Query Overpass API for shop POI nodes in Indonesia."""
    try:
        import requests
        import geopandas as gpd
        from shapely.geometry import Point
    except ImportError:
        print("[error] Install requests + geopandas: pip install requests geopandas")
        sys.exit(1)

    print("  Querying Overpass API for shop nodes (this may take 30-60s) ...")
    t0 = time.time()

    resp = requests.post(
        "https://overpass-api.de/api/interpreter",
        data={"data": OVERPASS_POI_QUERY},
        headers={
            "User-Agent": "kopdes-vis/1.0 (https://github.com/danylaksono/kopdes-vis)",
            "Accept": "application/json",
        },
        timeout=200,
    )
    resp.raise_for_status()
    data = resp.json()

    elapsed = time.time() - t0
    elements = data.get("elements", [])
    print(f"  Received {len(elements):,} nodes in {elapsed:.0f}s")

    if not elements:
        print("  No POIs returned — Overpass may be unavailable.")
        return

    # Build GeoDataFrame
    rows = []
    for el in elements:
        tags = el.get("tags", {})
        lat = el.get("lat")
        lon = el.get("lon")
        if lat is None or lon is None:
            continue
        name = (tags.get("name") or "").lower()
        brand = (tags.get("brand") or "").lower()
        operator = (tags.get("operator") or "").lower()

        rows.append({
            "osm_id": el["id"],
            "osm_type": el["type"],
            "name": tags.get("name"),
            "brand": tags.get("brand"),
            "operator": tags.get("operator"),
            "shop": tags.get("shop"),
            "brand_label": classify_brand(name, brand, operator),
            "addr:street": tags.get("addr:street"),
            "addr:city": tags.get("addr:city"),
            "geometry": Point(lon, lat),
        })

    gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")

    # Per-brand stats
    stats = gdf["brand_label"].value_counts()
    for label, count in stats.items():
        print(f"    {label}: {count:,}")

    POI_GPKG.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(POI_GPKG, layer="minimarkets", driver="GPKG")
    print(f"  POIs saved -> {POI_GPKG}  ({file_size_mb(POI_GPKG)})")


def extract_pois():
    """Extract minimarket POIs from Overpass API."""
    if POI_GPKG.exists():
        print(f"[skip] POIs already extracted: {POI_GPKG}  ({file_size_mb(POI_GPKG)})")
        return

    print("\n=== Extracting minimarket POIs ===")
    extract_pois_overpass()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Download OSM roads + minimarket POIs for Indonesia"
    )
    parser.add_argument(
        "--roads-only", action="store_true",
        help="Only extract road network (skip POIs)"
    )
    parser.add_argument(
        "--poi-only", action="store_true",
        help="Only extract minimarket POIs (skip roads)"
    )
    parser.add_argument(
        "--no-download", action="store_true",
        help="Skip PBF download (use existing cached file)"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  OSM Indonesia Data Downloader")
    print("=" * 60)

    do_roads = not args.poi_only
    do_pois = not args.roads_only

    # Step 1: PBF (needed for roads only; POIs come from Overpass)
    if do_roads and not args.no_download:
        download_pbf()

    # Step 2: Roads
    if do_roads:
        extract_roads()

    # Step 3: POIs
    if do_pois:
        extract_pois()

    print("\nDone. Output files:")
    if do_roads and ROADS_GPKG.exists():
        print(f"  Roads:  {ROADS_GPKG}  ({file_size_mb(ROADS_GPKG)})")
    if do_pois and POI_GPKG.exists():
        print(f"  POIs:   {POI_GPKG}  ({file_size_mb(POI_GPKG)})")


if __name__ == "__main__":
    main()
