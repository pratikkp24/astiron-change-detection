#!/bin/bash
"""
Create PS-10 submission zip file.

Usage: ./make_submission_zip.sh [RUN_ID]
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
    echo "Using most recent run: $RUN_ID"
fi

RUN_DIR="output/runs/$RUN_ID"

if [ ! -d "$RUN_DIR" ]; then
    echo "Error: Run directory not found: $RUN_DIR"
    exit 1
fi

# Load configuration for team name
TEAM_NAME="TEAMNAME"
if [ -f configs/config.yaml ]; then
    TEAM_NAME=$(python3 -c "
import yaml
with open('configs/config.yaml') as f:
    config = yaml.safe_load(f)
print(config.get('submission', {}).get('team_name', 'TEAMNAME'))
" 2>/dev/null || echo "TEAMNAME")
fi

# Generate submission filename
DATE_STR=$(date +"%d-%b-%Y")
SUBMISSION_NAME="PS10_${DATE_STR}_${TEAM_NAME}.zip"

echo "Creating submission: $SUBMISSION_NAME"
echo "From run: $RUN_ID"

# Create temporary directory for submission
TEMP_DIR=$(mktemp -d)
SUBMISSION_DIR="$TEMP_DIR/submission"
mkdir -p "$SUBMISSION_DIR"

# Copy all pair outputs
PAIR_COUNT=0
for PAIR_DIR in "$RUN_DIR"/*; do
    if [ -d "$PAIR_DIR" ]; then
        PAIR_ID=$(basename "$PAIR_DIR")
        
        # Skip run summary files
        if [ "$PAIR_ID" = "run_summary.json" ]; then
            continue
        fi
        
        echo "Adding pair: $PAIR_ID"
        
        # Copy required files
        for FILE in "$PAIR_DIR"/*.tif "$PAIR_DIR"/*.shp "$PAIR_DIR"/*.shx "$PAIR_DIR"/*.dbf "$PAIR_DIR"/*.prj; do
            if [ -f "$FILE" ]; then
                cp "$FILE" "$SUBMISSION_DIR/"
            fi
        done
        
        PAIR_COUNT=$((PAIR_COUNT + 1))
    fi
done

if [ $PAIR_COUNT -eq 0 ]; then
    echo "Error: No pairs found in run directory"
    rm -rf "$TEMP_DIR"
    exit 1
fi

echo "Added $PAIR_COUNT pairs to submission"

# Generate model hash
MODEL_HASH_FILE="$SUBMISSION_DIR/model_hash.txt"
./scripts/compute_md5.sh > "$MODEL_HASH_FILE"

echo "Generated model hash"

# Create the zip file
cd "$TEMP_DIR"
zip -r "$SUBMISSION_NAME" submission/

# Move to project directory
mv "$SUBMISSION_NAME" "$PROJECT_DIR/"

# Cleanup
rm -rf "$TEMP_DIR"

echo ""
echo "Submission created successfully:"
echo "  File: $SUBMISSION_NAME"
echo "  Size: $(du -h "$SUBMISSION_NAME" | cut -f1)"
echo "  Pairs: $PAIR_COUNT"

# Show contents
echo ""
echo "Contents:"
unzip -l "$SUBMISSION_NAME" | head -20

if [ $(unzip -l "$SUBMISSION_NAME" | wc -l) -gt 25 ]; then
    echo "  ... (truncated, $(unzip -l "$SUBMISSION_NAME" | tail -1 | awk '{print $2}') total files)"
fi

echo ""
echo "Submission ready for upload: $SUBMISSION_NAME"