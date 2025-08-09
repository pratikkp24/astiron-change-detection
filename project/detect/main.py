#!/usr/bin/env python3
"""
Detection module for PS-10 Change Detection pipeline.

This module handles:
- Classical change detection algorithms
- ML-based change detection (optional)
- Tile-based processing for large images
- Result stitching
"""

import os
import sys
import time
import logging
from pathlib import Path

# Add common modules to path
sys.path.append('/app/common')

from io import setup_logging, load_config, load_manifest, save_manifest, get_memory_usage, log_performance
from tiles import TileManager, load_tile_manifest
import rasterio
import numpy as np
from tqdm import tqdm

# Import detection algorithms
from classical import classical_change_detection, get_algorithm_description
from ml_infer import ml_change_detection, is_ml_available


def detect_change_tile(tile_a_path: str, tile_b_path: str, 
                      config: dict, logger: logging.Logger) -> tuple:
    """
    Detect changes in a single tile.
    
    Args:
        tile_a_path: Path to first tile
        tile_b_path: Path to second tile
        config: Configuration dictionary
        logger: Logger instance
        
    Returns:
        Tuple of (binary_mask, metadata)
    """
    # Read tile data
    with rasterio.open(tile_a_path) as src_a, \
         rasterio.open(tile_b_path) as src_b:
        
        data_a = src_a.read()
        data_b = src_b.read()
        profile = src_a.profile.copy()
    
    # Choose detection method
    detection_mode = config['detect']['mode']
    
    if detection_mode == 'ml' and is_ml_available(config):
        binary_mask, metadata = ml_change_detection(data_a, data_b, config)
    else:
        if detection_mode == 'ml':
            logger.warning("ML model not available, falling back to classical detection")
        binary_mask, metadata = classical_change_detection(data_a, data_b, config)
    
    return binary_mask, metadata, profile


def process_pair_tiles(pair_id: str, config: dict, logger: logging.Logger) -> dict:
    """
    Process all tiles for a pair and stitch results.
    
    Args:
        pair_id: Pair identifier
        config: Configuration dictionary
        logger: Logger instance
        
    Returns:
        Processing result dictionary
    """
    start_time = time.time()
    memory_before = get_memory_usage()
    
    logger.info(f"Processing tiles for pair: {pair_id}")
    
    # Load tile manifest
    manifest_path = f'/app/stage/tiles/{pair_id}/manifest.json'
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Tile manifest not found: {manifest_path}")
    
    manifest = load_tile_manifest(manifest_path)
    tiles = manifest['tiles']
    
    logger.info(f"Processing {len(tiles)} tiles")
    
    # Create output directory for tile results
    tile_results_dir = f'/app/stage/tiles/{pair_id}/results'
    os.makedirs(tile_results_dir, exist_ok=True)
    
    # Process each tile
    tile_results = []
    successful_tiles = 0
    
    for tile in tqdm(tiles, desc=f"Processing {pair_id}"):
        tile_id = tile['tile_id']
        
        try:
            # Detect changes in tile
            binary_mask, metadata, profile = detect_change_tile(
                tile['path_a'], tile['path_b'], config, logger
            )
            
            # Save tile result
            result_path = os.path.join(tile_results_dir, f'result_{tile_id:04d}.tif')
            
            # Update profile for binary output
            profile.update({
                'dtype': 'uint8',
                'count': 1,
                'compress': 'lzw'
            })
            
            with rasterio.open(result_path, 'w', **profile) as dst:
                dst.write(binary_mask, 1)
            
            # Store tile result info
            tile_result = {
                'tile_id': tile_id,
                'result_path': result_path,
                'bounds': tile['bounds'],
                'metadata': metadata,
                'status': 'success'
            }
            
            tile_results.append(tile_result)
            successful_tiles += 1
            
        except Exception as e:
            logger.error(f"Failed to process tile {tile_id}: {e}")
            tile_results.append({
                'tile_id': tile_id,
                'status': 'failed',
                'error': str(e),
                'bounds': tile['bounds']
            })
    
    logger.info(f"Processed {successful_tiles}/{len(tiles)} tiles successfully")
    
    if successful_tiles == 0:
        raise RuntimeError("No tiles processed successfully")
    
    # Stitch successful tiles
    logger.info("Stitching tile results")
    
    successful_results = [r for r in tile_results if r['status'] == 'success']
    
    # Create stitched output path
    stitched_path = f'/app/stage/{pair_id}_change_mask.tif'
    
    # Use tile manager to stitch results
    tile_manager = TileManager()
    reference_raster = manifest['raster_a']  # Use first image as reference
    
    tile_manager.stitch_tiles(successful_results, stitched_path, reference_raster)
    
    # Collect overall metadata
    all_metadata = [r['metadata'] for r in successful_results]
    
    # Calculate overall statistics
    total_change_pixels = sum(m['change_pixels'] for m in all_metadata)
    total_pixels = sum(m['total_pixels'] for m in all_metadata)
    overall_change_percentage = (total_change_pixels / total_pixels) * 100 if total_pixels > 0 else 0
    
    # Get algorithm description for hashing
    if config['detect']['mode'] == 'classical':
        algorithm_desc = get_algorithm_description(config)
    else:
        algorithm_desc = f"ml_{config['detect']['ml']['onnx_model']}"
    
    result = {
        'pair_id': pair_id,
        'status': 'success',
        'stitched_mask_path': stitched_path,
        'total_tiles': len(tiles),
        'successful_tiles': successful_tiles,
        'failed_tiles': len(tiles) - successful_tiles,
        'total_pixels': total_pixels,
        'change_pixels': total_change_pixels,
        'change_percentage': overall_change_percentage,
        'algorithm_description': algorithm_desc,
        'detection_mode': config['detect']['mode'],
        'tile_results': tile_results
    }
    
    log_performance(logger, f"Detection {pair_id}", start_time, memory_before)
    
    return result


def main():
    """Main detection function."""
    # Setup logging
    logger = setup_logging('/app/stage/logs', 'detect')
    logger.info("Starting detection module")
    
    try:
        # Load configuration
        config = load_config('/app/configs/config.yaml')
        
        # Load preprocessing results
        preprocess_results_path = '/app/stage/preprocess_results.json'
        if not os.path.exists(preprocess_results_path):
            raise FileNotFoundError("Preprocessing results not found")
        
        preprocess_results = load_manifest(preprocess_results_path)
        successful_pairs = [r for r in preprocess_results['results'] if r['status'] == 'success']
        
        if not successful_pairs:
            logger.error("No successfully preprocessed pairs found")
            sys.exit(1)
        
        logger.info(f"Found {len(successful_pairs)} pairs to process")
        
        # Process each pair
        results = []
        for pair_result in successful_pairs:
            pair_id = pair_result['pair_id']
            
            try:
                result = process_pair_tiles(pair_id, config, logger)
                results.append(result)
                logger.info(f"Successfully processed {pair_id}")
            except Exception as e:
                logger.error(f"Failed to process {pair_id}: {e}")
                results.append({
                    'pair_id': pair_id,
                    'status': 'failed',
                    'error': str(e)
                })
        
        # Save overall results
        overall_result = {
            'module': 'detect',
            'timestamp': time.time(),
            'total_pairs': len(successful_pairs),
            'successful_pairs': len([r for r in results if r['status'] == 'success']),
            'failed_pairs': len([r for r in results if r['status'] == 'failed']),
            'detection_mode': config['detect']['mode'],
            'results': results
        }
        
        save_manifest(overall_result, '/app/stage/detect_results.json')
        
        logger.info(f"Detection complete: {overall_result['successful_pairs']}/{overall_result['total_pairs']} pairs successful")
        
    except Exception as e:
        logger.error(f"Detection failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()