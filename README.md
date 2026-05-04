# Edmonton Parks NDVI Analysis

This project analyzes vegetation patterns across Edmonton parks using Sentinel-2 imagery and NDVI.

## Workflow
1. Download and clean park boundary data  
2. Retrieve Sentinel-2 imagery from Microsoft Planetary Computer  
3. Calculate NDVI using red and near-infrared bands  
4. Classify NDVI into vegetation levels  
5. Perform zonal statistics to summarize vegetation per park  

<img width="1537" height="364" alt="ndvi_pipeline drawio" src="https://github.com/user-attachments/assets/82e6da4a-f365-4fd1-8060-1695a6725842" />


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
