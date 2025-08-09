#!/usr/bin/env python3
"""
Preprocessing module for PS-10 Change Detection pipeline.

This module handles:
- Image alignment and co-registration
- Radiometric normalization
- Tiling for large rasters
- Cloud masking (optional)
"""

import os
import sys
import time
import logging
from pathlib import Path

# Add common modules to path
sys.path.append('/app/common')

from io import setup_logging, load_config, load_pairs_csv, save_manifest, get_memory_usage, log_performance
from geo import reproject_raster, coregister_images, normalize_radiometric, get_pixel_size_meters
from tiles import TileManager, save_tile_manifest
import rasterio
from rasterio.crs import CRS
import numpy as np


def preprocess_pair(pair_info: dict, config: dict, output_dir: str, logger: logging.Logger) -> dict:
    """
    Preprocess a single image pair.
    
    Args:
        pair_info: Dictionary with pair information from CSV
        config: Configuration dictionary
        output_dir: Output directory for processed files
        logger: Logger instance
        
    Returns:
        Dictionary with processing results
    """
    start_time = time.time()
    memory_before = get_memory_usage()
    
    pair_id = pair_info['pair_id']
    logger.info(f"Processing pair: {pair_id}")
    
    # Input paths
    first_path = os.path.join('/app/input', pair_info['first_path'])
    second_path = os.path.join('/app/input', pair_info['second_path'])
    
    # Validate input files
    if not os.path.exists(first_path):
        raise FileNotFoundError(f"First image not found: {first_path}")
    if not os.path.exists(second_path):
        raise FileNotFoundError(f"Second image not found: {second_path}")
    
    # Create pair output directory
    pair_output_dir = os.path.join(output_dir, pair_id)
    os.makedirs(pair_output_dir, exist_ok=True)
    
    # Read image information
    with rasterio.open(first_path) as src1, rasterio.open(second_path) as src2:
        info1 = {
            'width': src1.width, 'height': src1.height,
            'crs': src1.crs, 'transform': src1.transform,
            'bounds': src1.bounds, 'count': src1.count
        }
        info2 = {
            'width': src2.width, 'height': src2.height,
            'crs': src2.crs, 'transform': src2.transform,
            'bounds': src2.bounds, 'count': src2.count
        }
    
    logger.info(f"Image 1: {info1['width']}x{info1['height']}, CRS: {info1['crs']}")
    logger.info(f"Image 2: {info2['width']}x{info2['height']}, CRS: {info2['crs']}")
    
    # Determine target grid
    target_grid = config['preprocess']['target_grid']
    if target_grid == 'first':
        target_info = info1
        source_path, target_path = second_path, first_path
        source_info, target_info = info2, info1
    else:  # 'second'
        target_info = info2
        source_path, target_path = first_path, second_path
        source_info, target_info = info1, info2
    
    # Output paths for aligned images
    aligned_first_path = os.path.join(pair_output_dir, 'aligned_first.tif')
    aligned_second_path = os.path.join(pair_output_dir, 'aligned_second.tif')
    
    # Reproject source to target grid if needed
    if target_grid == 'first':
        # Copy first image as-is
        import shutil
        shutil.copy2(first_path, aligned_first_path)
        
        # Reproject second to first's grid
        logger.info("Reprojecting second image to first image's grid")
        reproject_raster(
            second_path, aligned_second_path,
            str(target_info['crs']),
            target_info['transform'],
            target_info['width'],
            target_info['height']
        )
    else:
        # Copy second image as-is
        import shutil
        shutil.copy2(second_path, aligned_second_path)
        
        # Reproject first to second's grid
        logger.info("Reprojecting first image to second image's grid")
        reproject_raster(
            first_path, aligned_first_path,
            str(target_info['crs']),
            target_info['transform'],
            target_info['width'],
            target_info['height']
        )
    
    # Co-registration if enabled
    if config['preprocess']['enable_coreg']:
        logger.info("Performing co-registration")
        
        with rasterio.open(aligned_first_path) as src1, \
             rasterio.open(aligned_second_path) as src2:
            
            # Read data for co-registration (use first 3 bands or all if fewer)
            data1 = src1.read(list(range(1, min(4, src1.count + 1))))
            data2 = src2.read(list(range(1, min(4, src2.count + 1))))
            
            # Perform co-registration
            aligned_data2, shift = coregister_images(data1, data2)
            
            logger.info(f"Co-registration shift: {shift}")
            
            # Write co-registered second image
            if abs(shift[0]) > 0.3 or abs(shift[1]) > 0.3:
                profile = src2.profile.copy()
                with rasterio.open(aligned_second_path, 'w', **profile) as dst:
                    # Apply shift to all bands
                    for i in range(1, src2.count + 1):
                        band_data = src2.read(i)
                        if i <= aligned_data2.shape[0]:
                            dst.write(aligned_data2[i-1], i)
                        else:
                            # For bands beyond the co-registration data, apply same shift
                            from scipy import ndimage
                            shifted_band = ndimage.shift(band_data, shift, mode='constant', cval=0)
                            dst.write(shifted_band, i)
    
    # Radiometric normalization
    norm_method = config['preprocess']['radiometric_norm']
    if norm_method != 'none':
        logger.info(f"Applying radiometric normalization: {norm_method}")
        
        # Read aligned images
        with rasterio.open(aligned_first_path) as src1, \
             rasterio.open(aligned_second_path) as src2:
            
            data1 = src1.read()
            data2 = src2.read()
            profile1 = src1.profile.copy()
            profile2 = src2.profile.copy()
            
            # Normalize
            if norm_method == 'histmatch':
                # Use first image as reference
                norm_data1 = normalize_radiometric(data1, 'none')
                norm_data2 = normalize_radiometric(data2, 'histmatch', data1)
            else:
                norm_data1 = normalize_radiometric(data1, norm_method)
                norm_data2 = normalize_radiometric(data2, norm_method)
            
            # Update data type for normalized data
            profile1.update(dtype='float32')
            profile2.update(dtype='float32')
            
            # Write normalized images
            with rasterio.open(aligned_first_path, 'w', **profile1) as dst1:
                dst1.write(norm_data1.astype(np.float32))
            
            with rasterio.open(aligned_second_path, 'w', **profile2) as dst2:
                dst2.write(norm_data2.astype(np.float32))
    
    # Create tiling manifest
    logger.info("Creating tiling manifest")
    tile_manager = TileManager(
        tile_size=config['runtime']['tile_size'],
        overlap=config['runtime']['tile_overlap']
    )
    
    manifest = tile_manager.create_tile_manifest(
        aligned_first_path, aligned_second_path,
        '/app/stage/tiles', pair_id
    )
    
    # Extract tiles
    logger.info("Extracting tiles")
    tile_manager.extract_tiles(manifest)
    
    # Save manifest
    manifest_path = os.path.join('/app/stage/tiles', pair_id, 'manifest.json')
    save_tile_manifest(manifest, manifest_path)
    
    # Calculate pixel size for area calculations
    with rasterio.open(aligned_first_path) as src:
        pixel_size_x, pixel_size_y = get_pixel_size_meters(src.transform, src.crs)
        pixel_area_m2 = pixel_size_x * pixel_size_y
    
    # Create processing result
    result = {
        'pair_id': pair_id,
        'status': 'success',
        'aligned_first_path': aligned_first_path,
        'aligned_second_path': aligned_second_path,
        'manifest_path': manifest_path,
        'num_tiles': manifest['num_tiles'],
        'pixel_size_x_m': pixel_size_x,
        'pixel_size_y_m': pixel_size_y,
        'pixel_area_m2': pixel_area_m2,
        'width': target_info['width'],
        'height': target_info['height'],
        'crs': str(target_info['crs'])
    }
    
    log_performance(logger, f"Preprocessing {pair_id}", start_time, memory_before)
    
    return result


def main():
    """Main preprocessing function."""
    # Setup logging
    logger = setup_logging('/app/stage/logs', 'preprocess')
    logger.info("Starting preprocessing module")
    
    try:
        # Load configuration
        config = load_config('/app/configs/config.yaml')
        
        # Load pairs
        pairs = load_pairs_csv('/app/input/pairs.csv')
        if not pairs:
            logger.warning("No pairs found in pairs.csv")
            return
        
        logger.info(f"Found {len(pairs)} pairs to process")
        
        # Process each pair
        results = []
        for pair_info in pairs:
            try:
                result = preprocess_pair(pair_info, config, '/app/stage', logger)
                results.append(result)
                logger.info(f"Successfully processed {pair_info['pair_id']}")
            except Exception as e:
                logger.error(f"Failed to process {pair_info['pair_id']}: {e}")
                results.append({
                    'pair_id': pair_info['pair_id'],
                    'status': 'failed',
                    'error': str(e)
                })
        
        # Save overall results
        overall_result = {
            'module': 'preprocess',
            'timestamp': time.time(),
            'total_pairs': len(pairs),
            'successful_pairs': len([r for r in results if r['status'] == 'success']),
            'failed_pairs': len([r for r in results if r['status'] == 'failed']),
            'results': results
        }
        
        save_manifest(overall_result, '/app/stage/preprocess_results.json')
        
        logger.info(f"Preprocessing complete: {overall_result['successful_pairs']}/{overall_result['total_pairs']} pairs successful")
        
    except Exception as e:
        logger.error(f"Preprocessing failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()