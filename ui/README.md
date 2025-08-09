# PS-10 Change Detection UI

Apple-grade local interface for visualizing change detection results.

## Features

- **Multi-Mode Comparison**: Swipe, Side-by-Side, Flicker, Mask Overlay
- **Interactive Inspector**: Click polygons for detailed metrics  
- **Real-time Stats**: Changed area, polygon count, largest changes
- **Export Tools**: Copy paths, generate submission names
- **Offline Operation**: No server required, works with local files

## Quick Start

### 1. Copy Results for Demo

First, copy a processed run to the UI's public directory:

```bash
# From project root
cp -r project/output/runs/RUN_20241201_120000/pair_001 ui/public/outputs/pair_001

# Or create the demo structure manually
mkdir -p ui/public/outputs/pair_001
```

### 2. Install Dependencies

```bash
cd ui
npm install
```

### 3. Start Development Server

```bash
npm run dev
```

The UI will be available at http://localhost:3000

## File Structure

The UI expects results in this structure:

```
ui/public/outputs/
├── pair_001/                    # Pair directory
│   ├── manifest.json           # Pair metadata and statistics
│   ├── Change_Mask_*.tif       # Binary change mask (not used by UI)
│   ├── Change_Mask_*.shp       # Shapefile (not used by UI)
│   └── Change_Mask_*.geojson   # GeoJSON for visualization
├── pair_002/
└── index.json                  # Optional: run index
```

### Required Files

Each pair directory must contain:

1. **manifest.json** - Contains statistics and metadata
2. **\*.geojson** - Change polygons for map visualization

### manifest.json Format

```json
{
  "pair_id": "pair_001",
  "outputs": {
    "change_mask": "Change_Mask_34.0531_74.3909.tif",
    "shapefile": "Change_Mask_34.0531_74.3909.shp", 
    "geojson": "Change_Mask_34.0531_74.3909.geojson"
  },
  "statistics": {
    "total_pixels": 1000000,
    "change_pixels": 5000,
    "change_area_m2": 125000,
    "change_area_km2": 0.125,
    "total_polygons": 15,
    "largest_area_m2": 25000,
    "mean_area_m2": 8333
  }
}
```

## UI Components

### Left Panel
- **Data Selection**: Run and pair dropdowns
- **Comparison Mode**: Diff mode controls with sliders
- **Statistics**: Real-time metrics and change intensity
- **Inspector**: Polygon details on click
- **Export Tools**: Path copying, downloads, submission names

### Map View
- **MapLibre GL**: Lightweight map rendering
- **Change Polygons**: Vector overlay with styling
- **Mode Controls**: Swipe handle, flicker indicator
- **Stats Overlay**: Quick metrics display

## Comparison Modes

### 1. Mask Overlay (Default)
- Shows change polygons as colored overlay
- Adjustable opacity for base image, mask, and outlines
- Best for general overview

### 2. Swipe
- Draggable vertical divider
- Before image on left, after on right
- Interactive position control

### 3. Side by Side  
- Split viewport with synchronized pan/zoom
- Before on left, after on right
- Good for detailed comparison

### 4. Flicker
- Animated toggle between before/after
- Adjustable speed (0.5-3 seconds)
- Effective for spotting changes

## Styling

The UI uses Apple-inspired design tokens:

- **Typography**: SF Pro Text/Display with system fallbacks
- **Colors**: Neutral grays with blue accents
- **Effects**: Frosted glass panels with backdrop blur
- **Animations**: Smooth 200ms cubic-bezier transitions
- **Shadows**: Layered depth with proper elevation

## Development

### Available Scripts

```bash
npm run dev      # Start development server
npm run build    # Build for production  
npm run preview  # Preview production build
npm run lint     # Run ESLint
```

### Adding New Features

1. **New Comparison Mode**: Add to `DiffMode` type and implement in `MapView`
2. **Additional Stats**: Extend `manifest.json` format and update `LeftPanel`
3. **Export Options**: Add new functions to `api/files.ts`

### Customization

- **Colors**: Modify CSS custom properties in `styles.css`
- **Layout**: Adjust panel widths and spacing
- **Map Style**: Customize MapLibre style object

## Troubleshooting

### No Data Appears
1. Check that files exist in `ui/public/outputs/`
2. Verify `manifest.json` format is correct
3. Ensure GeoJSON files are valid
4. Check browser console for errors

### Map Not Loading
1. Verify GeoJSON coordinates are valid
2. Check that polygons have proper geometry
3. Ensure coordinate system is WGS84 (EPSG:4326)

### Performance Issues
1. Reduce polygon complexity in postprocessing
2. Limit number of features displayed
3. Use simplified geometries for overview

## Browser Support

- **Chrome/Edge**: Full support
- **Firefox**: Full support  
- **Safari**: Full support (requires HTTPS for some features)

## Production Deployment

### Build for Production

```bash
npm run build
```

### Serve Static Files

The built files in `dist/` can be served by any static file server:

```bash
# Using Python
python -m http.server 3000 -d dist

# Using Node.js serve
npx serve dist

# Using nginx (copy dist/ contents to web root)
```

### HTTPS Requirements

Some features (clipboard access) require HTTPS in production. Use a reverse proxy or deploy to a platform that provides HTTPS.

## Integration with Pipeline

The UI automatically works with pipeline outputs when files are organized correctly:

```bash
# After running pipeline
./scripts/run_all.sh

# Copy results for UI
cp -r project/output/runs/RUN_*/pair_* ui/public/outputs/

# Start UI
cd ui && npm run dev
```

For automated integration, consider adding a script to copy results automatically after pipeline completion.