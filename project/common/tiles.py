"""
Tiling utilities for processing large rasters in chunks.
"""

import os
import json
import numpy as np
import rasterio
from rasterio.windows import Window
from typing import List, Dict, Tuple, Any, Generator
import logging
from .io import ensure_dir


class TileManager:
    """Manages tiling and stitching of large rasters."""
    
    def __init__(self, tile_size: int = 1024, overlap: int = 64):
        self.tile_size = tile_size
        self.overlap = overlap
        self.logger = logging.getLogger(__name__)
    
    def generate_tiles(self, width: int, height: int) -> List[Dict[str, Any]]:
        """Generate tile windows for given raster dimensions."""
        tiles = []
        tile_id = 0
        
        step_size = self.tile_size - self.overlap
        
        for row_start in range(0, height, step_size):
            for col_start in range(0, width, step_size):
                # Calculate tile bounds
                row_end = min(row_start + self.tile_size, height)
                col_end = min(col_start + self.tile_size, width)
                
                # Create window
                window = Window(
                    col_off=col_start,
                    row_off=row_start,
                    width=col_end - col_start,
                    height=row_end - row_start
                )
                
                tiles.append({
                    'tile_id': tile_id,
                    'window': {
                        'col_off': window.col_off,
                        'row_off': window.row_off,
                        'width': window.width,
                        'height': window.height
                    },
                    'bounds': {
                        'row_start': row_start,
                        'row_end': row_end,
                        'col_start': col_start,
                        'col_end': col_end
                    }
                })
                tile_id += 1
        
        return tiles
    
    def create_tile_manifest(self, raster_a_path: str, raster_b_path: str,
                           output_dir: str, pair_id: str) -> Dict[str, Any]:
        """Create tiling manifest for a pair of rasters."""
        
        # Read raster info
        with rasterio.open(raster_a_path) as src_a:
            width, height = src_a.width, src_a.height
            profile_a = src_a.profile.copy()
        
        with rasterio.open(raster_b_path) as src_b:
            profile_b = src_b.profile.copy()
        
        # Generate tiles
        tiles = self.generate_tiles(width, height)
        
        # Create output directories
        tile_dir_a = os.path.join(output_dir, pair_id, 'tiles_a')
        tile_dir_b = os.path.join(output_dir, pair_id, 'tiles_b')
        ensure_dir(tile_dir_a)
        ensure_dir(tile_dir_b)
        
        # Update tile paths
        for tile in tiles:
            tile_id = tile['tile_id']
            tile['path_a'] = os.path.join(tile_dir_a, f'tile_{tile_id:04d}.tif')
            tile['path_b'] = os.path.join(tile_dir_b, f'tile_{tile_id:04d}.tif')
        
        manifest = {
            'pair_id': pair_id,
            'raster_a': raster_a_path,
            'raster_b': raster_b_path,
            'width': width,
            'height': height,
            'tile_size': self.tile_size,
            'overlap': self.overlap,
            'num_tiles': len(tiles),
            'profile_a': {k: v for k, v in profile_a.items() 
                         if k not in ['transform']},  # Exclude non-serializable
            'profile_b': {k: v for k, v in profile_b.items() 
                         if k not in ['transform']},
            'tiles': tiles
        }
        
        return manifest
    
    def extract_tiles(self, manifest: Dict[str, Any]) -> None:
        """Extract tiles from source rasters based on manifest."""
        
        raster_a_path = manifest['raster_a']
        raster_b_path = manifest['raster_b']
        
        with rasterio.open(raster_a_path) as src_a, \
             rasterio.open(raster_b_path) as src_b:
            
            for tile in manifest['tiles']:
                window_dict = tile['window']
                window = Window(
                    col_off=window_dict['col_off'],
                    row_off=window_dict['row_off'],
                    width=window_dict['width'],
                    height=window_dict['height']
                )
                
                # Read tile data
                data_a = src_a.read(window=window)
                data_b = src_b.read(window=window)
                
                # Update profiles for tile
                profile_a = src_a.profile.copy()
                profile_b = src_b.profile.copy()
                
                profile_a.update({
                    'height': window.height,
                    'width': window.width,
                    'transform': rasterio.windows.transform(window, src_a.transform)
                })
                
                profile_b.update({
                    'height': window.height,
                    'width': window.width,
                    'transform': rasterio.windows.transform(window, src_b.transform)
                })
                
                # Write tiles
                with rasterio.open(tile['path_a'], 'w', **profile_a) as dst_a:
                    dst_a.write(data_a)
                
                with rasterio.open(tile['path_b'], 'w', **profile_b) as dst_b:
                    dst_b.write(data_b)
        
        self.logger.info(f"Extracted {len(manifest['tiles'])} tiles for pair {manifest['pair_id']}")
    
    def stitch_tiles(self, tile_results: List[Dict[str, Any]], 
                    output_path: str, reference_raster: str) -> None:
        """Stitch tile results back into full raster."""
        
        # Read reference raster info
        with rasterio.open(reference_raster) as ref:
            width, height = ref.width, ref.height
            profile = ref.profile.copy()
        
        # Initialize output array
        if len(tile_results) == 0:
            raise ValueError("No tile results to stitch")
        
        # Check first tile to determine output data type
        first_tile_path = tile_results[0]['result_path']
        with rasterio.open(first_tile_path) as first_tile:
            output_dtype = first_tile.dtype
            num_bands = first_tile.count
        
        # Update profile
        profile.update({
            'dtype': output_dtype,
            'count': num_bands
        })
        
        # Create output raster
        with rasterio.open(output_path, 'w', **profile) as dst:
            # Initialize with zeros
            if num_bands == 1:
                output_array = np.zeros((height, width), dtype=output_dtype)
            else:
                output_array = np.zeros((num_bands, height, width), dtype=output_dtype)
            
            # Weight array for blending overlaps
            weight_array = np.zeros((height, width), dtype=np.float32)
            
            for tile_result in tile_results:
                tile_path = tile_result['result_path']
                bounds = tile_result['bounds']
                
                row_start = bounds['row_start']
                row_end = bounds['row_end']
                col_start = bounds['col_start']
                col_end = bounds['col_end']
                
                # Read tile result
                with rasterio.open(tile_path) as tile_src:
                    tile_data = tile_src.read()
                
                # Calculate blend weights (higher in center, lower at edges)
                tile_height, tile_width = row_end - row_start, col_end - col_start
                weight_tile = self._create_blend_weights(tile_height, tile_width)
                
                # Add to output with blending
                if num_bands == 1:
                    tile_data = tile_data[0]  # Remove band dimension
                    current_weight = weight_array[row_start:row_end, col_start:col_end]
                    current_data = output_array[row_start:row_end, col_start:col_end]
                    
                    # Weighted average
                    total_weight = current_weight + weight_tile
                    mask = total_weight > 0
                    output_array[row_start:row_end, col_start:col_end][mask] = (
                        (current_data[mask] * current_weight[mask] + 
                         tile_data[mask] * weight_tile[mask]) / total_weight[mask]
                    )
                    weight_array[row_start:row_end, col_start:col_end] = total_weight
                else:
                    # Multi-band case
                    for band in range(num_bands):
                        current_weight = weight_array[row_start:row_end, col_start:col_end]
                        current_data = output_array[band, row_start:row_end, col_start:col_end]
                        
                        total_weight = current_weight + weight_tile
                        mask = total_weight > 0
                        output_array[band, row_start:row_end, col_start:col_end][mask] = (
                            (current_data[mask] * current_weight[mask] + 
                             tile_data[band][mask] * weight_tile[mask]) / total_weight[mask]
                        )
                    
                    weight_array[row_start:row_end, col_start:col_end] = np.maximum(
                        weight_array[row_start:row_end, col_start:col_end], weight_tile
                    )
            
            # Write final result
            if num_bands == 1:
                dst.write(output_array, 1)
            else:
                dst.write(output_array)
        
        self.logger.info(f"Stitched {len(tile_results)} tiles to {output_path}")
    
    def _create_blend_weights(self, height: int, width: int) -> np.ndarray:
        """Create blend weights with higher values in center."""
        y, x = np.ogrid[:height, :width]
        
        # Distance from center
        center_y, center_x = height // 2, width // 2
        dist_y = np.abs(y - center_y) / (height // 2)
        dist_x = np.abs(x - center_x) / (width // 2)
        
        # Combine distances
        dist = np.maximum(dist_y, dist_x)
        
        # Create weight (1 at center, 0.1 at edges)
        weight = 1.0 - 0.9 * dist
        weight = np.clip(weight, 0.1, 1.0)
        
        return weight.astype(np.float32)


def save_tile_manifest(manifest: Dict[str, Any], output_path: str) -> None:
    """Save tile manifest to JSON file."""
    ensure_dir(os.path.dirname(output_path))
    with open(output_path, 'w') as f:
        json.dump(manifest, f, indent=2)


def load_tile_manifest(manifest_path: str) -> Dict[str, Any]:
    """Load tile manifest from JSON file."""
    with open(manifest_path, 'r') as f:
        return json.load(f)