#!/bin/bash
"""
Run processing pipeline for a single pair.

Usage: ./run_pair.sh <pair_id>
"""

set -e

if [ $# -ne 1 ]; then
    echo "Usage: $0 <pair_id>"
    echo "Example: $0 pair_001"
    exit 1
fi

PAIR_ID="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Processing pair: $PAIR_ID"
echo "Project directory: $PROJECT_DIR"

cd "$PROJECT_DIR"

# Set run ID with timestamp
export RUN_ID="RUN_$(date +%Y%m%d_%H%M%S)"
echo "Run ID: $RUN_ID"

# Check if pair exists in pairs.csv
if ! grep -q "^$PAIR_ID," input/pairs.csv; then
    echo "Error: Pair '$PAIR_ID' not found in input/pairs.csv"
    exit 1
fi

# Create temporary pairs.csv with only the specified pair
TEMP_PAIRS_CSV="input/pairs_temp_$PAIR_ID.csv"
head -n 1 input/pairs.csv > "$TEMP_PAIRS_CSV"
grep "^$PAIR_ID," input/pairs.csv >> "$TEMP_PAIRS_CSV"

# Backup original pairs.csv and use temporary one
mv input/pairs.csv input/pairs.csv.backup
mv "$TEMP_PAIRS_CSV" input/pairs.csv

# Cleanup function
cleanup() {
    echo "Cleaning up..."
    if [ -f input/pairs.csv.backup ]; then
        mv input/pairs.csv.backup input/pairs.csv
    fi
}
trap cleanup EXIT

echo "Starting pipeline for $PAIR_ID..."

# Run preprocessing
echo "Step 1/3: Preprocessing..."
docker compose run --rm preprocess

if [ $? -ne 0 ]; then
    echo "Error: Preprocessing failed"
    exit 1
fi

# Run detection
echo "Step 2/3: Detection..."
docker compose run --rm detect

if [ $? -ne 0 ]; then
    echo "Error: Detection failed"
    exit 1
fi

# Run postprocessing
echo "Step 3/3: Postprocessing..."
docker compose run --rm postprocess

if [ $? -ne 0 ]; then
    echo "Error: Postprocessing failed"
    exit 1
fi

echo "Pipeline completed successfully for $PAIR_ID"
echo "Results saved to: output/runs/$RUN_ID/$PAIR_ID"

# Show summary
if [ -f "output/runs/$RUN_ID/$PAIR_ID/manifest.json" ]; then
    echo ""
    echo "Summary:"
    python3 -c "
import json
with open('output/runs/$RUN_ID/$PAIR_ID/manifest.json') as f:
    data = json.load(f)
stats = data['statistics']
print(f\"  Total polygons: {stats['total_polygons']:,}\")
print(f\"  Changed area: {stats['change_area_km2']:.3f} km²\")
print(f\"  Largest polygon: {stats.get('largest_area_m2', 0)/10000:.1f} hectares\")
"
fi