# QGIS to CadnaA Spatial Processor Tool

### Table of Contents
1. Description
2. Installation
3. Usage
4. Credits

## Description
QGIS python script script for generating CadnaA 3D modelling inputs using free UK government LIDAR data for DTM/DSM and OS VectorMap Local geodatabse or seperate shapefiles for roads, rail and buildings.

Exports shapefiles ready for CadnaA input (contours, road, rail and buildings) and assigns a height value to 2D building shapefile.

Individual shapefiles: https://osdatahub.os.uk/downloads/open/VectorMapDistrict
VectorMap Local Data: https://www.ordnancesurvey.co.uk/products/os-vectormap-local#get
National LIDAR Programme Data: https://www.data.gov.uk/dataset/f0db0249-f17b-4036-9e65-309148c97ce4/national-lidar-programme
Requirements: QGIS with GRASS

Assumes all data has the same co-ordinate system.

## Installation
To install this program
- install python 3 
- download the cadnaa_spatial_processing.py script
- open QGIS, go to 'Processing Toolbox tab' and 'Add Script to Toolbox'

## Usage
Input requirements:
- DTM raster layer (.TIF)
- DSM raster layer (.TIF)
- VectorMap Geodatabase (.gdb) [optional]*
- buildings (.shp) [optional]*
- roads (.shp) [optional]
- rail (.shp) [optional]

*inputs must include a buildings layer (either from VectorMap Geodatabase or as a standalone shapefile)

Running the script:
- once the .py file has been added to the processing toolbox, open the 'Create CadnaA Inputs' tool
- populate the fields with the above data
- choose your contour interval (usually match this with resolution of DTM/DSM
- specify your output folder

Outputs:
The script will output 4 x shapefiles:
- buildings.shp - 2D shapefile with columns that CadnaA can use to give height (HA) - height is based on the mean height of DSM minus DTM, you can change this to max if required
- contours.shp - 3D shapefile based on DTM layer and specified contour interval
- roads.shp - 2D shapefile with CadnaA columns to make relative
- rail.shp - 2D shapefile with CadnaA columns to make relative

## Credits
Me :ok_hand:


