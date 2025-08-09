#!/bin/bash
"""
Validate pipeline outputs for correctness.

Usage: ./validate_outputs.sh [RUN_ID]
"""

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Get run ID
if [ $# -eq 1 ]; then
    RUN_ID="$1"
else
    # Find most recent run
    RUN_ID=$(ls -1 output/runs/ | grep "^RUN_" | sort -r | head -n 1)
    if [ -z "$RUN_ID" ]; then
        echo "Error: No runs found in output/runs/"
        echo "Usage: $0 [RUN_ID]"
        exit 1
    fi
    echo "Validating most recent run: $RUN_ID"
fi

RUN_DIR="output/runs/$RUN_ID"

if [ ! -d "$RUN_DIR" ]; then
    echo "Error: Run directory not found: $RUN_DIR"
    exit 1
fi

echo "Validating outputs for run: $RUN_ID"
echo ""

TOTAL_PAIRS=0
VALID_PAIRS=0
ERRORS=()

# Validate each pair
for PAIR_DIR in "$RUN_DIR"/*; do
    if [ -d "$PAIR_DIR" ]; then
        PAIR_ID=$(basename "$PAIR_DIR")
        
        # Skip non-pair directories
        if [[ "$PAIR_ID" == "run_summary.json" ]]; then
            continue
        fi
        
        echo "Validating pair: $PAIR_ID"
        TOTAL_PAIRS=$((TOTAL_PAIRS + 1))
        PAIR_VALID=true
        
        # Check required files exist
        TIF_FILE=$(find "$PAIR_DIR" -name "*.tif" | head -n 1)
        SHP_FILE=$(find "$PAIR_DIR" -name "*.shp" | head -n 1)
        
        if [ -z "$TIF_FILE" ]; then
            ERRORS+=("$PAIR_ID: Missing GeoTIFF file")
            PAIR_VALID=false
        fi
        
        if [ -z "$SHP_FILE" ]; then
            ERRORS+=("$PAIR_ID: Missing Shapefile")
            PAIR_VALID=false
        fi
        
        # Validate GeoTIFF if exists
        if [ -n "$TIF_FILE" ]; then
            # Check if it's a valid raster
            if ! gdalinfo "$TIF_FILE" >/dev/null 2>&1; then
                ERRORS+=("$PAIR_ID: Invalid GeoTIFF format")
                PAIR_VALID=false
            else
                # Check if values are binary (0 or 1)
                UNIQUE_VALUES=$(python3 -c "
import rasterio
import numpy as np
try:
    with rasterio.open('$TIF_FILE') as src:
        data = src.read(1)
        unique_vals = np.unique(data)
        print(' '.join(map(str, unique_vals)))
except Exception as e:
    print('ERROR')
" 2>/dev/null)
                
                if [ "$UNIQUE_VALUES" = "ERROR" ]; then
                    ERRORS+=("$PAIR_ID: Cannot read GeoTIFF data")
                    PAIR_VALID=false
                elif ! echo "$UNIQUE_VALUES" | grep -E '^[01 ]+$' >/dev/null; then
                    ERRORS+=("$PAIR_ID: GeoTIFF contains non-binary values: $UNIQUE_VALUES")
                    PAIR_VALID=false
                fi
                
                # Check CRS exists
                CRS_INFO=$(gdalinfo "$TIF_FILE" | grep "Coordinate System is" || echo "")
                if [ -z "$CRS_INFO" ]; then
                    ERRORS+=("$PAIR_ID: GeoTIFF missing coordinate system")
                    PAIR_VALID=false
                fi
            fi
        fi
        
        # Validate Shapefile if exists
        if [ -n "$SHP_FILE" ]; then
            # Check if it's a valid shapefile
            if ! ogrinfo "$SHP_FILE" >/dev/null 2>&1; then
                ERRORS+=("$PAIR_ID: Invalid Shapefile format")
                PAIR_VALID=false
            else
                # Check if shapefile has features when mask has changes
                if [ -n "$TIF_FILE" ] && [ "$UNIQUE_VALUES" != "0" ] && [ "$UNIQUE_VALUES" != "ERROR" ]; then
                    FEATURE_COUNT=$(ogrinfo -so "$SHP_FILE" $(basename "$SHP_FILE" .shp) | grep "Feature Count" | awk '{print $3}' || echo "0")
                    if [ "$FEATURE_COUNT" = "0" ]; then
                        ERRORS+=("$PAIR_ID: Shapefile is empty but mask has changes")
                        PAIR_VALID=false
                    fi
                fi
            fi
        fi
        
        # Check manifest exists
        if [ ! -f "$PAIR_DIR/manifest.json" ]; then
            ERRORS+=("$PAIR_ID: Missing manifest.json")
            PAIR_VALID=false
        fi
        
        if [ "$PAIR_VALID" = true ]; then
            VALID_PAIRS=$((VALID_PAIRS + 1))
            echo "  ✓ Valid"
        else
            echo "  ✗ Invalid"
        fi
        
        echo ""
    fi
done

# Print summary
echo "=== Validation Summary ==="
echo "Total pairs: $TOTAL_PAIRS"
echo "Valid pairs: $VALID_PAIRS"
echo "Invalid pairs: $((TOTAL_PAIRS - VALID_PAIRS))"

if [ ${#ERRORS[@]} -gt 0 ]; then
    echo ""
    echo "Errors found:"
    for ERROR in "${ERRORS[@]}"; do
        echo "  - $ERROR"
    done
    echo ""
    echo "❌ Validation FAILED"
    exit 1
else
    echo ""
    echo "✅ All outputs are valid!"
fi