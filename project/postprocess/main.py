#!/usr/bin/env python3
"""
Postprocessing module for PS-10 Change Detection pipeline.

This module handles:
- Binary mask cleaning and hole filling
- Vectorization to polygons
- Polygon simplification and filtering
- Final output generation (GeoTIFF + Shapefile + GeoJSON)
"""

import os
import sys
import time
import logging
from pathlib import Path

# Add common modules to path
sys.path.append('/app/common')

from io import setup_logging, load_config, load_manifest, save_manifest, get_memory_usage, log_performance
from vectorize import raster_to_polygons, save_shapefile, save_geojson, clean_polygons, calculate_polygon_stats
import rasterio
import numpy as np
from scipy import ndimage
from skimage import morphology
import cv2


def clean_binary_mask(mask_path: str, config: dict, logger: logging.Logger) -> str:
    """
    Clean binary mask by filling holes and ensuring strict binary values.
    
    Args:
        mask_path: Path to input binary mask
        config: Configuration dictionary
        logger: Logger instance
        
    Returns:
        Path to cleaned mask
    """
    logger.info("Cleaning binary mask")
    
    fill_holes_px = config['postprocess']['fill_holes_px']
    
    with rasterio.open(mask_path) as src:
        mask = src.read(1)
        profile = src.profile.copy()
    
    # Ensure binary values (0 or 1)
    mask_binary = (mask > 0).astype(np.uint8)
    
    # Fill small holes
    if fill_holes_px > 0:
        # Create structuring element for hole filling
        kernel = morphology.disk(fill_holes_px)
        
        # Fill holes using morphological closing
        mask_filled = morphology.binary_closing(mask_binary, kernel)
        mask_binary = mask_filled.astype(np.uint8)
        
        logger.info(f"Filled holes smaller than {fill_holes_px} pixels")
    
    # Alternative hole filling using flood fill from edges
    # This ensures only interior holes are filled, not edge connections
    mask_filled = mask_binary.copy()
    
    # Flood fill from all edges to identify exterior regions
    h, w = mask_filled.shape
    exterior_mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
    
    # Start flood fill from all edge pixels that are 0
    for i in range(h):
        if mask_filled[i, 0] == 0:
            cv2.floodFill(mask_filled, exterior_mask, (0, i), 255)
        if mask_filled[i, w-1] == 0:
            cv2.floodFill(mask_filled, exterior_mask, (w-1, i), 255)
    
    for j in range(w):
        if mask_filled[0, j] == 0:
            cv2.floodFill(mask_filled, exterior_mask, (j, 0), 255)
        if mask_filled[h-1, j] == 0:
            cv2.floodFill(mask_filled, exterior_mask, (j, h-1), 255)
    
    # Now all exterior 0s are marked as 255, interior 0s (holes) remain 0
    # Fill interior holes
    interior_holes = (mask_filled == 0) & (mask_binary == 0)
    mask_binary[interior_holes] = 1
    
    # Reset flood-filled exterior regions back to 0
    mask_binary[mask_filled == 255] = 0
    
    # Save cleaned mask
    cleaned_path = mask_path.replace('.tif', '_cleaned.tif')
    
    profile.update({
        'dtype': 'uint8',
        'count': 1,
        'compress': 'lzw'
    })
    
    with rasterio.open(cleaned_path, 'w', **profile) as dst:
        dst.write(mask_binary, 1)
    
    # Calculate cleaning statistics
    original_pixels = np.sum(mask > 0)
    cleaned_pixels = np.sum(mask_binary)
    
    logger.info(f"Mask cleaning: {original_pixels:,} -> {cleaned_pixels:,} pixels "
               f"({cleaned_pixels - original_pixels:+,} change)")
    
    return cleaned_path


def postprocess_pair(pair_result: dict, config: dict, run_id: str, 
                    logger: logging.Logger) -> dict:
    """
    Postprocess a single pair result.
    
    Args:
        pair_result: Detection result for the pair
        config: Configuration dictionary
        run_id: Run identifier
        logger: Logger instance
        
    Returns:
        Postprocessing result dictionary
    """
    start_time = time.time()
    memory_before = get_memory_usage()
    
    pair_id = pair_result['pair_id']
    logger.info(f"Postprocessing pair: {pair_id}")
    
    # Get input mask path
    mask_path = pair_result['stitched_mask_path']
    if not os.path.exists(mask_path):
        raise FileNotFoundError(f"Stitched mask not found: {mask_path}")
    
    # Clean binary mask
    cleaned_mask_path = clean_binary_mask(mask_path, config, logger)
    
    # Create output directory
    output_dir = f'/app/output/runs/{run_id}/{pair_id}'
    os.makedirs(output_dir, exist_ok=True)
    
    # Get reference coordinates for output naming
    # This should come from the original pairs.csv
    ref_lat = "XX.XXXX"  # Default placeholder
    ref_lon = "XX.XXXX"  # Default placeholder
    
    # Try to extract from preprocessing results if available
    preprocess_results_path = '/app/stage/preprocess_results.json'
    if os.path.exists(preprocess_results_path):
        preprocess_results = load_manifest(preprocess_results_path)
        for prep_result in preprocess_results['results']:
            if prep_result['pair_id'] == pair_id:
                # Would need to get this from original pairs.csv
                # For now, use pair_id as fallback
                break
    
    # Generate output filenames
    base_name = f"Change_Mask_{ref_lat}_{ref_lon}"
    final_mask_path = os.path.join(output_dir, f"{base_name}.tif")
    shapefile_path = os.path.join(output_dir, f"{base_name}.shp")
    geojson_path = os.path.join(output_dir, f"{base_name}.geojson")
    
    # Copy cleaned mask to final location
    import shutil
    shutil.copy2(cleaned_mask_path, final_mask_path)
    
    # Vectorize to polygons
    logger.info("Vectorizing mask to polygons")
    
    min_area_m2 = config['postprocess']['min_polygon_area_m2']
    simplify_tol_m = config['postprocess']['simplify_tol_m']
    
    gdf = raster_to_polygons(
        cleaned_mask_path,
        min_area_m2=min_area_m2,
        simplify_tolerance_m=simplify_tol_m
    )
    
    # Clean polygons
    if len(gdf) > 0:
        gdf = clean_polygons(gdf, buffer_distance=0.1)  # Small buffer for cleaning
    
    # Save vector outputs
    save_shapefile(gdf, shapefile_path)
    save_geojson(gdf, geojson_path)
    
    # Calculate statistics
    polygon_stats = calculate_polygon_stats(gdf)
    
    # Read final mask for pixel statistics
    with rasterio.open(final_mask_path) as src:
        final_mask = src.read(1)
        pixel_size_x = abs(src.transform[0])
        pixel_size_y = abs(src.transform[4])
        pixel_area_m2 = pixel_size_x * pixel_size_y
    
    total_pixels = final_mask.size
    change_pixels = np.sum(final_mask)
    change_area_m2 = change_pixels * pixel_area_m2
    
    # Create manifest for this pair
    pair_manifest = {
        'pair_id': pair_id,
        'run_id': run_id,
        'timestamp': time.time(),
        'outputs': {
            'change_mask': os.path.basename(final_mask_path),
            'shapefile': os.path.basename(shapefile_path),
            'geojson': os.path.basename(geojson_path)
        },
        'statistics': {
            'total_pixels': int(total_pixels),
            'change_pixels': int(change_pixels),
            'change_area_m2': float(change_area_m2),
            'change_area_km2': float(change_area_m2 / 1_000_000),
            'pixel_area_m2': float(pixel_area_m2),
            **polygon_stats
        },
        'processing': {
            'min_polygon_area_m2': min_area_m2,
            'simplify_tolerance_m': simplify_tol_m,
            'algorithm': pair_result.get('algorithm_description', 'unknown')
        }
    }
    
    # Save pair manifest
    manifest_path = os.path.join(output_dir, 'manifest.json')
    save_manifest(pair_manifest, manifest_path)
    
    result = {
        'pair_id': pair_id,
        'status': 'success',
        'output_dir': output_dir,
        'final_mask_path': final_mask_path,
        'shapefile_path': shapefile_path,
        'geojson_path': geojson_path,
        'manifest_path': manifest_path,
        'statistics': pair_manifest['statistics']
    }
    
    log_performance(logger, f"Postprocessing {pair_id}", start_time, memory_before)
    
    logger.info(f"Generated {polygon_stats['total_polygons']} polygons, "
               f"total area: {change_area_m2/1e6:.2f} km²")
    
    return result


def main():
    """Main postprocessing function."""
    # Setup logging
    logger = setup_logging('/app/stage/logs', 'postprocess')
    logger.info("Starting postprocessing module")
    
    try:
        # Load configuration
        config = load_config('/app/configs/config.yaml')
        
        # Get run ID from environment
        run_id = os.environ.get('RUN_ID', f'RUN_{int(time.time())}')
        logger.info(f"Run ID: {run_id}")
        
        # Load detection results
        detect_results_path = '/app/stage/detect_results.json'
        if not os.path.exists(detect_results_path):
            raise FileNotFoundError("Detection results not found")
        
        detect_results = load_manifest(detect_results_path)
        successful_pairs = [r for r in detect_results['results'] if r['status'] == 'success']
        
        if not successful_pairs:
            logger.error("No successfully detected pairs found")
            sys.exit(1)
        
        logger.info(f"Found {len(successful_pairs)} pairs to postprocess")
        
        # Process each pair
        results = []
        for pair_result in successful_pairs:
            try:
                result = postprocess_pair(pair_result, config, run_id, logger)
                results.append(result)
                logger.info(f"Successfully postprocessed {pair_result['pair_id']}")
            except Exception as e:
                logger.error(f"Failed to postprocess {pair_result['pair_id']}: {e}")
                results.append({
                    'pair_id': pair_result['pair_id'],
                    'status': 'failed',
                    'error': str(e)
                })
        
        # Save overall results
        overall_result = {
            'module': 'postprocess',
            'run_id': run_id,
            'timestamp': time.time(),
            'total_pairs': len(successful_pairs),
            'successful_pairs': len([r for r in results if r['status'] == 'success']),
            'failed_pairs': len([r for r in results if r['status'] == 'failed']),
            'results': results
        }
        
        save_manifest(overall_result, '/app/stage/postprocess_results.json')
        
        # Create run summary
        run_summary = {
            'run_id': run_id,
            'timestamp': time.time(),
            'total_pairs_processed': overall_result['successful_pairs'],
            'output_location': f'/app/output/runs/{run_id}',
            'pairs': {r['pair_id']: r['statistics'] for r in results if r['status'] == 'success'}
        }
        
        save_manifest(run_summary, f'/app/output/runs/{run_id}/run_summary.json')
        
        logger.info(f"Postprocessing complete: {overall_result['successful_pairs']}/{overall_result['total_pairs']} pairs successful")
        logger.info(f"Results saved to: /app/output/runs/{run_id}")
        
    except Exception as e:
        logger.error(f"Postprocessing failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()