# Edmonton Parks NDVI Analysis

This project analyzes vegetation patterns across Edmonton parks using Sentinel-2 imagery and NDVI.

## Workflow
1. Download and clean park boundary data  
2. Retrieve Sentinel-2 imagery from Microsoft Planetary Computer  
3. Calculate NDVI using red and near-infrared bands  
4. Classify NDVI into vegetation levels  
5. Perform zonal statistics to summarize vegetation per park  


## Technologies
- Python
- GeoPandas
- Rasterio / rioxarray
- Planetary Computer STAC API
- Rasterstats

## Output
- NDVI raster  
- Classified vegetation raster  
- Park-level vegetation summary  

## Note
Raw data and raster outputs are not included due to file size. The workflow can be reproduced using the provided script.
