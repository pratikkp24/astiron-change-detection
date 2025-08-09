#!/bin/bash
"""
Download Sentinel-2 data from Copernicus Data Space Ecosystem (CDSE).

Prerequisites:
1. Register at https://dataspace.copernicus.eu/
2. Get access token from https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token
3. Set CDSE_TOKEN environment variable

Usage: ./get_data_cdse.sh
"""

set -e

# Check if token is set
if [ -z "$CDSE_TOKEN" ]; then
    echo "Error: CDSE_TOKEN environment variable not set"
    echo ""
    echo "To get a token:"
    echo "1. Register at https://dataspace.copernicus.eu/"
    echo "2. Get token from: https://documentation.dataspace.copernicus.eu/APIs/Token.html"
    echo "3. Export CDSE_TOKEN=\"your_token_here\""
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Configuration
BASE_URL="https://catalogue.dataspace.copernicus.eu/odata/v1"
DOWNLOAD_URL="https://zipper.dataspace.copernicus.eu/odata/v1"

# Example coordinates (Kashmir region)
LAT=34.0531
LON=74.3909
BUFFER=0.1  # degrees

# Date range
START_DATE="2024-06-01"
END_DATE="2024-07-01"

echo "Searching for Sentinel-2 data..."
echo "Location: $LAT, $LON (±$BUFFER degrees)"
echo "Date range: $START_DATE to $END_DATE"

# Create search geometry (bounding box)
MIN_LON=$(echo "$LON - $BUFFER" | bc)
MAX_LON=$(echo "$LON + $BUFFER" | bc)
MIN_LAT=$(echo "$LAT - $BUFFER" | bc)
MAX_LAT=$(echo "$LAT + $BUFFER" | bc)

GEOMETRY="POLYGON(($MIN_LON $MIN_LAT,$MAX_LON $MIN_LAT,$MAX_LON $MAX_LAT,$MIN_LON $MAX_LAT,$MIN_LON $MIN_LAT))"

# Search query
SEARCH_QUERY="Collection/Name eq 'SENTINEL-2' and OData.CSC.Intersects(area=geography'SRID=4326;$GEOMETRY') and ContentDate/Start ge ${START_DATE}T00:00:00.000Z and ContentDate/Start le ${END_DATE}T23:59:59.999Z and Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' and att/OData.CSC.DoubleAttribute/Value le 20)"

echo ""
echo "Searching products..."

# Search for products
SEARCH_RESPONSE=$(curl -s -H "Authorization: Bearer $CDSE_TOKEN" \
    "$BASE_URL/Products?\$filter=$SEARCH_QUERY&\$orderby=ContentDate/Start&\$top=10")

# Parse response and extract product IDs
PRODUCT_IDS=$(echo "$SEARCH_RESPONSE" | python3 -c "
import json
import sys

try:
    data = json.load(sys.stdin)
    products = data.get('value', [])
    
    if not products:
        print('No products found')
        sys.exit(1)
    
    print(f'Found {len(products)} products:')
    for i, product in enumerate(products):
        name = product['Name']
        date = product['ContentDate']['Start'][:10]
        cloud_cover = next((attr['Value'] for attr in product.get('Attributes', []) 
                           if attr['Name'] == 'cloudCover'), 'N/A')
        print(f'  {i+1}. {name} ({date}, {cloud_cover}% clouds)')
        
        if i < 2:  # Only download first 2 products
            print(product['Id'])
    
except Exception as e:
    print(f'Error parsing response: {e}')
    sys.exit(1)
")

if echo "$PRODUCT_IDS" | grep -q "No products found"; then
    echo "No Sentinel-2 products found for the specified criteria"
    exit 1
fi

echo "$PRODUCT_IDS"

# Extract actual product IDs (last 2 lines)
PRODUCT_ID_LIST=$(echo "$PRODUCT_IDS" | tail -2)

if [ -z "$PRODUCT_ID_LIST" ]; then
    echo "No product IDs extracted"
    exit 1
fi

# Download products
mkdir -p input/a input/b

COUNTER=0
for PRODUCT_ID in $PRODUCT_ID_LIST; do
    COUNTER=$((COUNTER + 1))
    
    if [ $COUNTER -eq 1 ]; then
        OUTPUT_DIR="input/a"
        LABEL="before"
    else
        OUTPUT_DIR="input/b"
        LABEL="after"
    fi
    
    echo ""
    echo "Downloading product $COUNTER ($LABEL): $PRODUCT_ID"
    
    # Get download URL
    DOWNLOAD_RESPONSE=$(curl -s -H "Authorization: Bearer $CDSE_TOKEN" \
        "$DOWNLOAD_URL/Products($PRODUCT_ID)/\$value")
    
    # Download with aria2c for resume capability
    OUTPUT_FILE="$OUTPUT_DIR/S2_${LABEL}_$(date +%Y%m%d).zip"
    
    if command -v aria2c >/dev/null 2>&1; then
        aria2c -c -x 4 -s 4 \
            --header="Authorization: Bearer $CDSE_TOKEN" \
            -o "$OUTPUT_FILE" \
            "$DOWNLOAD_URL/Products($PRODUCT_ID)/\$value"
    else
        curl -L -C - \
            -H "Authorization: Bearer $CDSE_TOKEN" \
            -o "$OUTPUT_FILE" \
            "$DOWNLOAD_URL/Products($PRODUCT_ID)/\$value"
    fi
    
    if [ $? -eq 0 ]; then
        echo "Downloaded: $OUTPUT_FILE"
        
        # Extract and convert to GeoTIFF
        echo "Extracting and converting to GeoTIFF..."
        
        EXTRACT_DIR="$OUTPUT_DIR/extracted"
        mkdir -p "$EXTRACT_DIR"
        
        unzip -q "$OUTPUT_FILE" -d "$EXTRACT_DIR"
        
        # Find the SAFE directory
        SAFE_DIR=$(find "$EXTRACT_DIR" -name "*.SAFE" -type d | head -n 1)
        
        if [ -n "$SAFE_DIR" ]; then
            # Find 10m resolution bands (B02, B03, B04, B08)
            IMG_DIR="$SAFE_DIR/GRANULE/*/IMG_DATA/R10m"
            
            if [ -d $IMG_DIR ]; then
                # Stack RGB bands
                B02_FILE=$(find $IMG_DIR -name "*B02_10m.jp2" | head -n 1)
                B03_FILE=$(find $IMG_DIR -name "*B03_10m.jp2" | head -n 1)
                B04_FILE=$(find $IMG_DIR -name "*B04_10m.jp2" | head -n 1)
                B08_FILE=$(find $IMG_DIR -name "*B08_10m.jp2" | head -n 1)
                
                if [ -n "$B02_FILE" ] && [ -n "$B03_FILE" ] && [ -n "$B04_FILE" ]; then
                    OUTPUT_TIF="$OUTPUT_DIR/S2_${LABEL}_$(date +%Y%m%d).tif"
                    
                    # Stack bands using GDAL
                    gdal_merge.py -separate -o "$OUTPUT_TIF" \
                        "$B04_FILE" "$B03_FILE" "$B02_FILE" "$B08_FILE"
                    
                    echo "Created: $OUTPUT_TIF"
                else
                    echo "Warning: Could not find required bands in $IMG_DIR"
                fi
            else
                echo "Warning: Could not find 10m resolution data in $SAFE_DIR"
            fi
        else
            echo "Warning: Could not find SAFE directory in extracted files"
        fi
        
        # Cleanup
        rm -rf "$EXTRACT_DIR"
        
    else
        echo "Failed to download product $PRODUCT_ID"
    fi
done

echo ""
echo "Download complete!"
echo "Check input/a/ and input/b/ directories for downloaded data"
echo ""
echo "Next steps:"
echo "1. Update input/pairs.csv with the downloaded file paths"
echo "2. Run the pipeline: ./scripts/run_all.sh"