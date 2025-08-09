# ResourceSat-2 LISS-IV Data Download from Bhoonidhi Portal

The Bhoonidhi portal (https://bhoonidhi.nrsc.gov.in/) provides access to Indian satellite data including ResourceSat-2 LISS-IV. Since there's no public API, data must be downloaded manually.

## Prerequisites

1. **Register Account**: Create account at https://bhoonidhi.nrsc.gov.in/
2. **Account Approval**: Wait for account approval (may take 1-2 business days)
3. **Login Credentials**: Keep your username and password ready

## Download Steps

### 1. Login to Portal
- Go to https://bhoonidhi.nrsc.gov.in/
- Click "Login" and enter your credentials
- Navigate to "Data Search" or "Catalogue"

### 2. Search Parameters
Configure search with these parameters:

**Satellite**: ResourceSat-2
**Sensor**: LISS-IV
**Resolution**: 5.8m
**Product Level**: L1G (Geo-corrected) or L2A (Atmospherically corrected)

**Geographic Area**: 
- Use coordinates from your target region
- Example coordinates for different terrains:
  - **Kashmir (Snow)**: 34.0531°N, 74.3909°E
  - **Delhi (Urban)**: 28.6139°N, 77.2090°E
  - **Rajasthan (Desert)**: 27.0238°N, 74.2179°E
  - **Kerala (Forest)**: 10.8505°N, 76.2711°E
  - **Punjab (Plain)**: 31.1471°N, 75.3412°E
  - **Himachal (Hill)**: 32.1024°N, 77.1734°E

**Date Range**:
- Select two different dates (at least 3-6 months apart)
- Avoid monsoon season for better image quality
- Check cloud cover percentage (<20% recommended)

### 3. Search and Select
1. Click "Search" to find available scenes
2. Review results and check:
   - Cloud cover percentage
   - Image quality indicators
   - Date separation
3. Select **two scenes** from different dates covering the same area

### 4. Download Process
1. Add selected scenes to cart
2. Proceed to checkout
3. **Payment**: Most data requires payment (check current rates)
4. **Processing Time**: Downloads may take several hours to process
5. **Download Links**: You'll receive email notifications with download links

### 5. File Organization
Once downloaded, organize files as follows:

```
project/input/
├── a/                          # "Before" images
│   └── LISS4_2024_06_01.tif   # First date
├── b/                          # "After" images  
│   └── LISS4_2024_11_01.tif   # Second date
└── pairs.csv                   # Update with file paths
```

### 6. Update pairs.csv
Add your downloaded data to `input/pairs.csv`:

```csv
pair_id,ref_lat,ref_lon,sensor,first_path,second_path,crs_target,notes
pair_liss4_001,28.6139,77.2090,LISS4,a/LISS4_2024_06_01.tif,b/LISS4_2024_11_01.tif,,Delhi urban area
```

## File Format Notes

- **Format**: Usually provided as GeoTIFF (.tif) or HDF
- **Bands**: LISS-IV has 3 bands (Green, Red, NIR)
- **Resolution**: 5.8m pixel size
- **Projection**: Usually UTM or Geographic (WGS84)

## Tips for Better Results

1. **Cloud Cover**: Choose scenes with <10% cloud cover
2. **Season Consistency**: Avoid mixing different seasons
3. **Time Gap**: 3-6 months between dates works well for change detection
4. **Area Coverage**: Ensure both scenes cover exactly the same geographic area
5. **Quality Check**: Verify image quality before processing

## Troubleshooting

**Account Issues**:
- Contact NRSC support if account approval is delayed
- Ensure all registration details are accurate

**Search Problems**:
- Try broader date ranges if no results found
- Check if coordinates are within India's coverage area
- Verify satellite/sensor combination is correct

**Download Issues**:
- Large files may require download managers
- Check email spam folder for download notifications
- Contact support if download links expire

## Alternative Sources

If Bhoonidhi is not accessible, consider:

1. **USGS EarthExplorer**: May have some Indian satellite data
2. **ESA Copernicus**: Sentinel-2 data (10m resolution) as alternative
3. **Commercial Providers**: Planet, Maxar, etc. (requires subscription)

## Next Steps

After downloading:
1. Verify file integrity and format
2. Update `pairs.csv` with correct paths
3. Run preprocessing to check alignment
4. Proceed with change detection pipeline

For technical support with the pipeline, see the main README.md file.