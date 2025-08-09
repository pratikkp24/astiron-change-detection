# Data Acquisition Guide for PS-10 Change Detection

This guide covers downloading satellite imagery from both Copernicus Data Space Ecosystem (Sentinel-2) and Bhoonidhi Portal (ResourceSat-2 LISS-IV).

## Target Coordinates

Use these coordinates for different terrain types as specified in PS-10:

| Terrain | Location | Latitude | Longitude | Notes |
|---------|----------|----------|-----------|-------|
| Snow | Kashmir | 34.0531°N | 74.3909°E | High altitude, seasonal snow |
| Urban | Delhi | 28.6139°N | 77.2090°E | Dense urban development |
| Desert | Rajasthan | 27.0238°N | 74.2179°E | Arid landscape |
| Forest | Kerala | 10.8505°N | 76.2711°E | Dense tropical forest |
| Plain | Punjab | 31.1471°N | 75.3412°E | Agricultural plains |
| Hill | Himachal Pradesh | 32.1024°N | 77.1734°E | Mountainous terrain |

## Sentinel-2 Data (Copernicus Data Space)

### Prerequisites
1. Register at https://dataspace.copernicus.eu/
2. Get access token from the authentication endpoint
3. Set environment variable: `export CDSE_TOKEN="your_token_here"`

### Automated Download
```bash
# Set your access token
export CDSE_TOKEN="your_token_here"

# Run download script
./scripts/get_data_cdse.sh
```

### Manual Download
1. Go to https://dataspace.copernicus.eu/browser/
2. Search parameters:
   - **Mission**: Sentinel-2
   - **Product Type**: S2MSI2A (Level-2A, atmospherically corrected)
   - **Cloud Cover**: < 20%
   - **Date Range**: Select two dates 3-6 months apart
3. Download and extract to `input/a/` and `input/b/`

## ResourceSat-2 LISS-IV Data (Bhoonidhi Portal)

### Manual Process Required
ResourceSat-2 data must be downloaded manually from https://bhoonidhi.nrsc.gov.in/

See detailed instructions in: `scripts/get_data_bhoonidhi.md`

### Key Points
- **Registration**: Account approval required (1-2 days)
- **Payment**: Most data requires payment
- **Format**: Usually GeoTIFF
- **Resolution**: 5.8m pixel size
- **Bands**: 3 bands (Green, Red, NIR)

## Data Organization

After downloading, organize files as follows:

```
project/input/
├── a/                          # "Before" images
│   ├── S2_2024_06_01.tif      # Sentinel-2 first date
│   └── LISS4_2024_06_01.tif   # LISS-IV first date
├── b/                          # "After" images
│   ├── S2_2024_11_01.tif      # Sentinel-2 second date
│   └── LISS4_2024_11_01.tif   # LISS-IV second date
└── pairs.csv                   # Manifest file
```

## Update pairs.csv

Add your downloaded pairs to `input/pairs.csv`:

```csv
pair_id,ref_lat,ref_lon,sensor,first_path,second_path,crs_target,notes
s2_kashmir,34.0531,74.3909,S2,a/S2_2024_06_01.tif,b/S2_2024_11_01.tif,,Sentinel-2 Kashmir snow region
liss4_delhi,28.6139,77.2090,LISS4,a/LISS4_2024_06_01.tif,b/LISS4_2024_11_01.tif,,ResourceSat-2 Delhi urban
```

## Quality Criteria

### Image Selection
- **Cloud Cover**: < 20% (preferably < 10%)
- **Time Gap**: 3-6 months between acquisitions
- **Season**: Avoid mixing different seasons
- **Coverage**: Exact geographic overlap between dates

### Technical Requirements
- **Format**: GeoTIFF preferred
- **Projection**: Any standard projection (will be aligned in preprocessing)
- **Bit Depth**: 16-bit or 8-bit
- **Bands**: Minimum RGB, NIR preferred

## Verification Steps

After downloading, verify your data:

```bash
# Check file format and basic info
gdalinfo input/a/your_image.tif

# Verify coordinate system
gdalinfo input/a/your_image.tif | grep "Coordinate System"

# Check image statistics
gdalinfo -stats input/a/your_image.tif
```

## Common Issues and Solutions

### Download Problems
- **Slow Downloads**: Use aria2c or wget with resume capability
- **Authentication**: Ensure token is valid and not expired
- **File Corruption**: Verify file integrity with checksums

### Format Issues
- **JP2 Files**: Convert to GeoTIFF using `gdal_translate`
- **HDF Files**: Extract bands using `gdal_translate`
- **Zip Archives**: Extract and organize band files

### Coordinate Issues
- **Different Projections**: Pipeline handles reprojection automatically
- **Misaligned Images**: Preprocessing includes co-registration
- **Wrong Coordinates**: Double-check lat/lon values in pairs.csv

## Example Commands

### Convert JP2 to GeoTIFF
```bash
gdal_translate -of GTiff input.jp2 output.tif
```

### Stack Multiple Bands
```bash
gdal_merge.py -separate -o stacked.tif band1.tif band2.tif band3.tif
```

### Check Image Overlap
```bash
gdalinfo image1.tif | grep "Upper Left\|Lower Right"
gdalinfo image2.tif | grep "Upper Left\|Lower Right"
```

## Next Steps

Once data is downloaded and organized:

1. **Verify Setup**: Check that all files are accessible
2. **Update Configuration**: Modify `configs/config.yaml` if needed
3. **Test Pipeline**: Run on a small subset first
4. **Full Processing**: Execute `./scripts/run_all.sh`

For pipeline execution, see the main README.md file.