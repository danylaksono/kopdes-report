#!/usr/bin/env python3
"""
Download Kontur Population for Indonesia (400m H3 hexagons).

Output: data/population/kontur_population_ID.gpkg

Source: Kontur / HDX — CC-BY license
    https://data.humdata.org/dataset/kontur-population-indonesia

Columns:
    h3         — H3 index (resolution 10, ~400m edge)
    population — total population in the hexagon
    geom       — polygon geometry (EPSG:3857)

Usage:
    python scripts/download_population.py
"""

import gzip
import shutil
import sys
import time
from pathlib import Path

import requests
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "population"
URL = (
    "https://geodata-eu-central-1-kontur-public.s3.amazonaws.com"
    "/kontur_datasets/kontur_population_ID_20231101.gpkg.gz"
)
OUT_PATH = DATA_DIR / "kontur_population_ID.gpkg"


def file_size_mb(path: Path) -> str:
    if not path.exists():
        return "N/A"
    sz = path.stat().st_size
    return f"{sz / 1_048_576:.1f} MB"


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if OUT_PATH.exists():
        print(f"[skip] Already downloaded: {OUT_PATH}  ({file_size_mb(OUT_PATH)})")
        return

    gz_path = DATA_DIR / "kontur_population_ID.gpkg.gz"

    # Download
    print(f"Downloading Kontur Population (Indonesia, 400m H3)...")
    print(f"  {URL}")
    resp = requests.get(URL, stream=True, timeout=30)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))

    with open(gz_path, "wb") as f, tqdm(
        desc="  Download",
        total=total,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            size = f.write(chunk)
            bar.update(size)

    print(f"  Downloaded: {file_size_mb(gz_path)}")

    # Decompress
    print("  Decompressing...")
    t0 = time.time()
    with gzip.open(gz_path, "rb") as f_in:
        with open(OUT_PATH, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    elapsed = time.time() - t0

    # Remove compressed file
    gz_path.unlink()

    print(f"  Decompressed in {elapsed:.0f}s -> {OUT_PATH}  ({file_size_mb(OUT_PATH)})")

    # Quick sanity check
    try:
        import geopandas as gpd
        gdf = gpd.read_file(OUT_PATH, rows=5)
        cols = list(gdf.columns)
        print(f"  Columns: {cols}")
        print(f"  Sample: {gdf.head(2).to_string()}")
    except Exception as e:
        print(f"  (Could not preview: {e})")


if __name__ == "__main__":
    main()
