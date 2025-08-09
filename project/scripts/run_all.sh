#!/bin/bash
"""
Run processing pipeline for all pairs in pairs.csv.

Usage: ./run_all.sh
"""

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Running PS-10 Change Detection Pipeline"
echo "Project directory: $PROJECT_DIR"

cd "$PROJECT_DIR"

# Check if pairs.csv exists and has content
if [ ! -f input/pairs.csv ]; then
    echo "Error: input/pairs.csv not found"
    echo "Please create pairs.csv using the template in scripts/pairs_template.csv"
    exit 1
fi

# Count pairs (excluding header)
PAIR_COUNT=$(tail -n +2 input/pairs.csv | wc -l)
if [ "$PAIR_COUNT" -eq 0 ]; then
    echo "Error: No pairs found in input/pairs.csv"
    echo "Please add pairs to process"
    exit 1
fi

echo "Found $PAIR_COUNT pairs to process"

# Set run ID with timestamp
export RUN_ID="RUN_$(date +%Y%m%d_%H%M%S)"
echo "Run ID: $RUN_ID"

# Create logs directory
mkdir -p stage/logs

echo "Starting pipeline..."
START_TIME=$(date +%s)

# Run preprocessing
echo ""
echo "=== Step 1/3: Preprocessing ==="
docker compose run --rm preprocess

if [ $? -ne 0 ]; then
    echo "Error: Preprocessing failed"
    exit 1
fi

# Run detection
echo ""
echo "=== Step 2/3: Detection ==="
docker compose run --rm detect

if [ $? -ne 0 ]; then
    echo "Error: Detection failed"
    exit 1
fi

# Run postprocessing
echo ""
echo "=== Step 3/3: Postprocessing ==="
docker compose run --rm postprocess

if [ $? -ne 0 ]; then
    echo "Error: Postprocessing failed"
    exit 1
fi

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo "=== Pipeline Completed Successfully ==="
echo "Total time: ${DURATION}s"
echo "Results saved to: output/runs/$RUN_ID"

# Show summary table
if [ -f "output/runs/$RUN_ID/run_summary.json" ]; then
    echo ""
    echo "Summary:"
    python3 -c "
import json
import os

run_dir = 'output/runs/$RUN_ID'
summary_file = os.path.join(run_dir, 'run_summary.json')

if os.path.exists(summary_file):
    with open(summary_file) as f:
        summary = json.load(f)
    
    print(f'Run ID: {summary[\"run_id\"]}')
    print(f'Pairs processed: {summary[\"total_pairs_processed\"]}')
    print()
    print('Per-pair results:')
    print('Pair ID'.ljust(15) + 'Polygons'.rjust(10) + 'Area (km²)'.rjust(12) + 'Largest (ha)'.rjust(15))
    print('-' * 52)
    
    for pair_id, stats in summary['pairs'].items():
        polygons = stats['total_polygons']
        area_km2 = stats['change_area_km2']
        largest_ha = stats.get('largest_area_m2', 0) / 10000
        print(f'{pair_id}'.ljust(15) + f'{polygons:,}'.rjust(10) + f'{area_km2:.3f}'.rjust(12) + f'{largest_ha:.1f}'.rjust(15))
else:
    print('Summary file not found')
"
fi

echo ""
echo "Next steps:"
echo "1. Review results in output/runs/$RUN_ID"
echo "2. Launch UI: cd ui && npm run dev"
echo "3. Create submission: ./scripts/make_submission_zip.sh $RUN_ID"