# PS-10 Change Detection using Satellite Imagery

A fully offline, dockerized pipeline for detecting changes in satellite imagery with an Apple-grade UI for visual QA.

> **Note**: This repository has been verified for access and linting capabilities.

## 🎯 Overview

This repository implements **PS-10 Stage-1**: Change Detection using Earth Observation (EO) imagery. It processes pairs of satellite images (Sentinel-2, ResourceSat-2 LISS-IV) to detect and vectorize changes between two dates.

### Key Features
- **Fully Offline Runtime**: No network dependencies during processing
- **Multi-Sensor Support**: Sentinel-2 (10m) and ResourceSat-2 LISS-IV (5.8m)
- **Tile-Safe Processing**: Handles large scenes (11k-18k pixels) via intelligent tiling
- **Apple-Grade UI**: Polished local interface with swipe, side-by-side, and overlay modes
- **PS-10 Compliant**: Generates submission-ready outputs with proper naming and MD5 hashing

### Outputs per Image Pair
- **GeoTIFF**: Binary change mask (1=change, 0=no change), georeferenced
- **Shapefile**: Vector polygons of detected changes (cleaned & simplified)
- **Submission Package**: PS10_[DD-MMM-YYYY]_[TEAM].zip with model hash

## 🚀 Quick Start

### 1. Build Pipeline
```bash
cd project
docker compose build
```

### 2. Prepare Data
Place your image pairs in `project/input/` and update `pairs.csv`:
```bash
cp scripts/pairs_template.csv input/pairs.csv
# Edit pairs.csv with your image paths
```

### 3. Run Processing
```bash
# Process all pairs
./scripts/run_all.sh

# Or process single pair
./scripts/run_pair.sh <pair_id>
```

### 4. Launch UI
```bash
cd ui
# Copy a sample run for demo
cp -r ../project/output/runs/RUN_*/pair_001 public/outputs/pair_001
npm install && npm run dev
```

### 5. Create Submission
```bash
./scripts/make_submission_zip.sh
./scripts/compute_md5.sh
```

## 📁 Repository Structure

```
ps10-change-detection/
├── project/                 # Main processing pipeline
│   ├── docker-compose.yml   # Orchestration
│   ├── configs/            # Configuration files
│   ├── input/              # Input images and manifests
│   ├── common/             # Shared utilities
│   ├── preprocess/         # Image alignment & tiling
│   ├── detect/             # Change detection algorithms
│   ├── postprocess/        # Vectorization & cleanup
│   ├── scripts/            # Automation scripts
│   └── output/             # Results per run
├── ui/                     # Apple-grade local interface
│   ├── src/                # React/TypeScript components
│   └── public/             # Static assets
├── tests/                  # Unit and integration tests
└── docs/                   # Additional documentation
```

## 🛠 Data Acquisition

### Sentinel-2 (Copernicus Data Space)
```bash
# Set your access token
export CDSE_TOKEN="your_token_here"
./scripts/get_data_cdse.sh
```

### ResourceSat-2 LISS-IV (Bhoonidhi Portal)
See `scripts/get_data_bhoonidhi.md` for manual download instructions.

## 🎨 UI Features

- **Multi-Mode Comparison**: Swipe, Side-by-Side, Flicker, Mask Overlay
- **Interactive Inspector**: Click polygons for detailed metrics
- **Real-time Stats**: Changed area, polygon count, largest changes
- **Export Tools**: Copy paths, generate submission names
- **Offline Operation**: No server required, works with local files

## 📊 Algorithms

### Stage-1 (Current)
- **Classical Detection**: Log-ratio + Otsu thresholding + morphological operations
- **Preprocessing**: Co-registration, normalization, cloud masking
- **Postprocessing**: Hole filling, polygon simplification, area filtering

### Stage-2 (Planned)
- **ML Classification**: Multi-class change detection (buildings, roads, etc.)
- **Multi-Modal**: EO + SAR fusion (Sentinel-1 + Sentinel-2)

## 🧪 Testing

```bash
# Run unit tests
python -m pytest tests/

# Validate outputs
./scripts/validate_outputs.sh

# Compute metrics (if ground truth available)
python metrics/jaccard.py --pred output.tif --gt ground_truth.tif
```

## 📋 Requirements

- **Docker & Docker Compose**
- **Node.js 18+** (for UI)
- **Python 3.10+** (for local testing)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

## 🆘 Support

For issues or questions:
- Check the troubleshooting guide in `docs/`
- Review test cases in `tests/`
- Open an issue with detailed logs
