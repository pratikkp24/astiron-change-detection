#!/bin/bash
"""
Compute MD5 hash for model or algorithm description.

Usage: ./compute_md5.sh
"""

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Check if ML model exists
ML_MODEL_PATH="detect/models/model.onnx"

if [ -f "$ML_MODEL_PATH" ]; then
    echo "# ML Model Hash"
    md5sum "$ML_MODEL_PATH" | cut -d' ' -f1
else
    # Use classical algorithm description
    ALGORITHM_DESC="classical_logratio_otsu_morphology_v1.0"
    
    # Load actual configuration if available
    if [ -f configs/config.yaml ]; then
        ALGORITHM_DESC=$(python3 -c "
import yaml
import sys
sys.path.append('common')
from hashing import get_model_hash

try:
    with open('configs/config.yaml') as f:
        config = yaml.safe_load(f)
    
    # Generate algorithm description
    classical_config = config['detect']['classical']
    desc = f\"classical_{classical_config['index']}_{classical_config['thresh']}_morph_open{classical_config['morph']['open_size']}_close{classical_config['morph']['close_size']}_minarea{classical_config['morph']['min_area_px']}_denoise_{classical_config['denoise']}_v1.0\"
    
    print(get_model_hash(algorithm_description=desc))
except Exception as e:
    # Fallback to default
    print(get_model_hash(algorithm_description='$ALGORITHM_DESC'))
" 2>/dev/null || echo -n "$ALGORITHM_DESC" | md5sum | cut -d' ' -f1)
    fi
    
    echo "# Classical Algorithm Hash"
    echo "$ALGORITHM_DESC"
fi