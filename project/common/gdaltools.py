"""
GDAL utilities for raster processing.
"""

import os
import subprocess
import tempfile
from typing import List, Optional, Tuple
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import logging


def gdal_warp(src_path: str, dst_path: str, 
              target_crs: Optional[str] = None,
              target_resolution: Optional[Tuple[float, float]] = None,
              resampling: str = 'bilinear',
              cutline: Optional[str] = None) -> bool:
    """
    Warp raster using GDAL command line tools.
    
    Args:
        src_path: Source raster path
        dst_path: Destination raster path
        target_crs: Target CRS (e.g., 'EPSG:4326')
        target_resolution: Target resolution (x_res, y_res)
        resampling: Resampling method
        cutline: Cutline shapefile path
        
    Returns:
        True if successful
    """
    cmd = ['gdalwarp']
    
    if target_crs:
        cmd.extend(['-t_srs', target_crs])
    
    if target_resolution:
        cmd.extend(['-tr', str(target_resolution[0]), str(target_resolution[1])])
    
    cmd.extend(['-r', resampling])
    
    if cutline:
        cmd.extend(['-cutline', cutline, '-crop_to_cutline'])
    
    cmd.extend(['-overwrite', src_path, dst_path])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"GDAL warp failed: {e.stderr}")
        return False


def gdal_translate(src_path: str, dst_path: str,
                  bands: Optional[List[int]] = None,
                  output_type: Optional[str] = None,
                  creation_options: Optional[List[str]] = None) -> bool:
    """
    Translate raster format using GDAL.
    
    Args:
        src_path: Source raster path
        dst_path: Destination raster path
        bands: List of band numbers to extract
        output_type: Output data type (e.g., 'Byte', 'Float32')
        creation_options: GDAL creation options
        
    Returns:
        True if successful
    """
    cmd = ['gdal_translate']
    
    if bands:
        for band in bands:
            cmd.extend(['-b', str(band)])
    
    if output_type:
        cmd.extend(['-ot', output_type])
    
    if creation_options:
        for option in creation_options:
            cmd.extend(['-co', option])
    
    cmd.extend([src_path, dst_path])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"GDAL translate failed: {e.stderr}")
        return False


def gdal_merge(input_files: List[str], output_file: str,
               creation_options: Optional[List[str]] = None) -> bool:
    """
    Merge multiple rasters using gdal_merge.py.
    
    Args:
        input_files: List of input raster files
        output_file: Output merged raster
        creation_options: GDAL creation options
        
    Returns:
        True if successful
    """
    cmd = ['gdal_merge.py', '-o', output_file]
    
    if creation_options:
        for option in creation_options:
            cmd.extend(['-co', option])
    
    cmd.extend(input_files)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"GDAL merge failed: {e.stderr}")
        return False


def convert_jp2_to_tiff(jp2_path: str, tiff_path: str, 
                       bands: Optional[List[int]] = None) -> bool:
    """
    Convert JP2 to GeoTIFF format.
    
    Args:
        jp2_path: Input JP2 file path
        tiff_path: Output TIFF file path
        bands: Specific bands to extract
        
    Returns:
        True if successful
    """
    creation_options = [
        'COMPRESS=LZW',
        'TILED=YES',
        'BLOCKXSIZE=512',
        'BLOCKYSIZE=512'
    ]
    
    return gdal_translate(jp2_path, tiff_path, bands=bands, 
                         creation_options=creation_options)


def stack_bands(band_files: List[str], output_file: str) -> bool:
    """
    Stack multiple single-band rasters into multi-band raster.
    
    Args:
        band_files: List of single-band raster files
        output_file: Output multi-band raster
        
    Returns:
        True if successful
    """
    if not band_files:
        return False
    
    # Use rasterio for band stacking
    try:
        # Read first file to get profile
        with rasterio.open(band_files[0]) as src:
            profile = src.profile.copy()
            profile.update(count=len(band_files))
        
        # Stack bands
        with rasterio.open(output_file, 'w', **profile) as dst:
            for i, band_file in enumerate(band_files, 1):
                with rasterio.open(band_file) as src:
                    dst.write(src.read(1), i)
        
        return True
    except Exception as e:
        logging.error(f"Band stacking failed: {e}")
        return False


def get_raster_stats(raster_path: str) -> dict:
    """Get basic statistics for raster bands."""
    stats = {}
    
    try:
        with rasterio.open(raster_path) as src:
            for i in range(1, src.count + 1):
                band_data = src.read(i, masked=True)
                stats[f'band_{i}'] = {
                    'min': float(band_data.min()),
                    'max': float(band_data.max()),
                    'mean': float(band_data.mean()),
                    'std': float(band_data.std()),
                    'count': int(band_data.count()),
                    'nodata_count': int(band_data.mask.sum())
                }
    except Exception as e:
        logging.error(f"Failed to compute raster stats: {e}")
    
    return stats


def create_overviews(raster_path: str, levels: List[int] = [2, 4, 8, 16]) -> bool:
    """Create pyramid overviews for raster."""
    cmd = ['gdaladdo', '-r', 'average', raster_path] + [str(level) for level in levels]
    
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Overview creation failed: {e.stderr}")
        return False