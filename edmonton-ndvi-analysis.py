from pathlib import Path
import os
import sys
import json
from datetime import datetime

import geopandas as gpd
import numpy as np
import pandas as pd
import pystac
import planetary_computer
from pystac_client import Client
import rioxarray as rxr
from rioxarray.merge import merge_arrays
from rasterstats import zonal_stats



# CONFIG
RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

parks_clean_path = PROCESSED_DIR / "edmonton_parks_clean.gpkg"
selected_items_path = PROCESSED_DIR / "selected_sentinel_items.json"
ndvi_path = PROCESSED_DIR / "ndvi.tif"
ndvi_class_path = PROCESSED_DIR / "ndvi_3class.tif"
qa_log_path = PROCESSED_DIR / "ndvi_qa_log.txt"
zonal_output_path = PROCESSED_DIR / "parks_ndvi_class_summary.gpkg"



# FIX PROJ ERROR
venv_proj = Path(sys.prefix) / "Lib" / "site-packages" / "rasterio" / "proj_data"
os.environ["PROJ_LIB"] = str(venv_proj)
os.environ["PROJ_DATA"] = str(venv_proj)



# 01 DOWNLOAD + CLEAN PARKS
print("\nDownloading and cleaning parks data")

url = "https://data.edmonton.ca/resource/gdd9-eqv9.geojson?$limit=50000"
parks = gpd.read_file(url)

parks = parks[
    parks.geometry.notna() & ~parks.geometry.is_empty
].copy()

parks["geometry"] = parks.geometry.make_valid()
parks = parks.to_crs(epsg=32612)

valid_classes = [
    "City Park",
    "District Activity Park",
    "Natural Area Park",
    "School and Community Park",
    "Urban Village Park"
]

parks = parks[
    (parks["type"] == "Park") &
    (parks["class"].isin(valid_classes)) &
    (parks["status"] == "Active")
].copy()

parks["area_m2"] = parks.geometry.area
parks["park_name"] = parks["official_name"].fillna(parks["common_name"])

parks = parks[parks["park_name"].notna()].copy()
parks.to_file(parks_clean_path, layer="parks_clean", driver="GPKG")

print(f"Parks cleaned: {len(parks)}")



# 02 SEARCH SENTINEL
print("\nSearching Sentinel-2 data")

parks_wgs84 = parks.to_crs("EPSG:4326")
bbox = parks_wgs84.total_bounds.tolist()

catalog = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")

search = catalog.search(
    collections=["sentinel-2-l2a"],
    bbox=bbox,
    datetime="2024-06-01/2024-08-31",
    query={"eo:cloud_cover": {"lt": 20}},
)

items = list(search.items())

selected_ids = [
    "S2B_MSIL2A_20240707T184919_R113_T11UQV_20240707T233825",
    "S2B_MSIL2A_20240707T184919_R113_T12UUE_20240707T233254"
]

selected_items = [item for item in items if item.id in selected_ids]

with open(selected_items_path, "w") as f:
    json.dump({
        "type": "FeatureCollection",
        "features": [item.to_dict() for item in selected_items]
    }, f)

print("Selected scenes saved")



# 03 CALCULATE NDVI
print("\nCalculating NDVI")

with open(selected_items_path) as f:
    data = json.load(f)

items = [pystac.Item.from_dict(f) for f in data["features"]]

b04_list, b08_list = [], []

for item in items:
    signed = planetary_computer.sign(item)

    b04 = rxr.open_rasterio(signed.assets["B04"].href, masked=True).squeeze()
    b08 = rxr.open_rasterio(signed.assets["B08"].href, masked=True).squeeze()

    b04 = b04.rio.reproject("EPSG:32612", resolution=10)
    b08 = b08.rio.reproject("EPSG:32612", resolution=10)

    b04_list.append(b04)
    b08_list.append(b08)

b04 = merge_arrays(b04_list)
b08 = merge_arrays(b08_list)

ndvi = (b08 - b04) / (b08 + b04)
ndvi = ndvi.where((b08 + b04) != 0)
ndvi = ndvi.where((ndvi >= -1) & (ndvi <= 1))
ndvi = ndvi.astype("float32")

ndvi.rio.write_crs("EPSG:32612", inplace=True)
ndvi.rio.to_raster(ndvi_path)

print("NDVI saved")



# 04 QA + CLASSIFY
print("\nRunning QA and classification")

ndvi = rxr.open_rasterio(ndvi_path, masked=True).squeeze()

outside_range = int(np.sum((ndvi.values < -1) | (ndvi.values > 1)))
nodata_count = int(np.isnan(ndvi.values).sum())

qa_text = f"""
Run: {datetime.now()}
Min: {float(ndvi.min())}
Max: {float(ndvi.max())}
Mean: {float(ndvi.mean())}
Outside range: {outside_range}
NoData: {nodata_count}
"""

with open(qa_log_path, "a") as f:
    f.write(qa_text)

if outside_range > 0:
    raise ValueError("NDVI invalid")

classified = ndvi.copy()
classified.values[:] = 255

valid = np.isfinite(ndvi.values)

classified.values[(ndvi.values < 0.2) & valid] = 1
classified.values[(ndvi.values >= 0.2) & (ndvi.values < 0.5) & valid] = 2
classified.values[(ndvi.values >= 0.5) & valid] = 3

classified = classified.astype("uint8")
classified.rio.write_nodata(255, inplace=True)
classified.rio.write_crs(ndvi.rio.crs, inplace=True)
classified.rio.to_raster(ndvi_class_path)

print("NDVI classified")



# 05 ZONAL SUMMARY
print("\nRunning zonal statistics")

parks = gpd.read_file(parks_clean_path)
classified = rxr.open_rasterio(ndvi_class_path, masked=True).squeeze()

parks = parks.to_crs(classified.rio.crs)

stats = zonal_stats(
    parks,
    ndvi_class_path,
    categorical=True,
    nodata=255
)

df = pd.DataFrame(stats).fillna(0)

for c in [1, 2, 3]:
    if c not in df.columns:
        df[c] = 0

parks["low"] = df[1]
parks["medium"] = df[2]
parks["high"] = df[3]

parks["total"] = parks["low"] + parks["medium"] + parks["high"]

parks["low_ratio"] = parks["low"] / parks["total"]
parks["medium_ratio"] = parks["medium"] / parks["total"]
parks["high_ratio"] = parks["high"] / parks["total"]

parks["dominant"] = parks[["low_ratio", "medium_ratio", "high_ratio"]].idxmax(axis=1)

parks = parks[parks["total"] > 0]

parks.to_file(zonal_output_path, layer="parks_ndvi", driver="GPKG")

print("Pipeline complete")