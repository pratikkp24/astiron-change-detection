"""
Geospatial utilities for PS-10 Change Detection pipeline.
"""

import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.crs import CRS
from rasterio.transform import from_bounds
import pyproj
from scipy import ndimage
from skimage import registration
from typing import Tuple, Optional, Dict, Any
import logging


def get_pixel_size_meters(transform, crs) -> Tuple[float, float]:
    """Calculate pixel size in meters."""
    if crs is None:
        return abs(transform[0]), abs(transform[4])
    
    # Convert to projected CRS if geographic
    if crs.is_geographic:
        # Use UTM zone for the center of the image
        bounds = rasterio.transform.array_bounds(1, 1, transform)
        center_lon = (bounds[0] + bounds[2]) / 2
        center_lat = (bounds[1] + bounds[3]) / 2
        
        utm_zone = int((center_lon + 180) / 6) + 1
        hemisphere = 'north' if center_lat >= 0 else 'south'
        utm_crs = CRS.from_string(f'+proj=utm +zone={utm_zone} +{hemisphere} +datum=WGS84')
        
        # Transform a small square to UTM and measure
        transformer = pyproj.Transformer.from_crs(crs, utm_crs, always_xy=True)
        x1, y1 = transformer.transform(bounds[0], bounds[1])
        x2, y2 = transformer.transform(bounds[0] + abs(transform[0]), bounds[1])
        x3, y3 = transformer.transform(bounds[0], bounds[1] + abs(transform[4]))
        
        pixel_size_x = abs(x2 - x1)
        pixel_size_y = abs(y3 - y1)
    else:
        pixel_size_x = abs(transform[0])
        pixel_size_y = abs(transform[4])
    
    return pixel_size_x, pixel_size_y


def reproject_raster(src_path: str, dst_path: str, dst_crs: str, 
                    dst_transform: Optional[Any] = None, 
                    dst_width: Optional[int] = None, 
                    dst_height: Optional[int] = None,
                    resampling: Resampling = Resampling.bilinear) -> Dict[str, Any]:
    """Reproject raster to target CRS and resolution."""
    
    with rasterio.open(src_path) as src:
        if dst_transform is None or dst_width is None or dst_height is None:
            # Calculate default transform and dimensions
            dst_transform, dst_width, dst_height = calculate_default_transform(
                src.crs, dst_crs, src.width, src.height, *src.bounds
            )
        
        # Update profile
        profile = src.profile.copy()
        profile.update({
            'crs': dst_crs,
            'transform': dst_transform,
            'width': dst_width,
            'height': dst_height
        })
        
        # Create output raster
        with rasterio.open(dst_path, 'w', **profile) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=dst_transform,
                    dst_crs=dst_crs,
                    resampling=resampling
                )
    
    return {
        'crs': str(dst_crs),
        'transform': list(dst_transform),
        'width': dst_width,
        'height': dst_height
    }


def coregister_images(reference: np.ndarray, target: np.ndarray, 
                     max_shift: int = 10) -> Tuple[np.ndarray, Tuple[float, float]]:
    """
    Co-register target image to reference using phase correlation.
    
    Args:
        reference: Reference image (2D array)
        target: Target image to be aligned (2D array)
        max_shift: Maximum allowed shift in pixels
        
    Returns:
        Tuple of (aligned_target, (shift_y, shift_x))
    """
    # Convert to grayscale if multi-band
    if reference.ndim > 2:
        ref_gray = np.mean(reference, axis=0)
    else:
        ref_gray = reference
        
    if target.ndim > 2:
        tgt_gray = np.mean(target, axis=0)
    else:
        tgt_gray = target
    
    # Compute phase correlation
    shift, error, diffphase = registration.phase_cross_correlation(
        ref_gray, tgt_gray, upsample_factor=10
    )
    
    shift_y, shift_x = shift
    
    # Check if shift is significant
    if abs(shift_x) < 0.3 and abs(shift_y) < 0.3:
        return target, (0.0, 0.0)
    
    # Limit maximum shift
    shift_x = np.clip(shift_x, -max_shift, max_shift)
    shift_y = np.clip(shift_y, -max_shift, max_shift)
    
    # Apply shift
    if target.ndim > 2:
        aligned = np.zeros_like(target)
        for i in range(target.shape[0]):
            aligned[i] = ndimage.shift(target[i], (shift_y, shift_x), 
                                     mode='constant', cval=0)
    else:
        aligned = ndimage.shift(target, (shift_y, shift_x), 
                               mode='constant', cval=0)
    
    return aligned, (shift_y, shift_x)


def normalize_radiometric(image: np.ndarray, method: str = 'zscore', 
                         reference: Optional[np.ndarray] = None) -> np.ndarray:
    """
    Apply radiometric normalization to image.
    
    Args:
        image: Input image array
        method: Normalization method ('zscore', 'histmatch', 'minmax', 'none')
        reference: Reference image for histogram matching
        
    Returns:
        Normalized image
    """
    if method == 'none':
        return image
    
    normalized = image.copy().astype(np.float32)
    
    if method == 'zscore':
        # Z-score normalization per band
        if image.ndim > 2:
            for i in range(image.shape[0]):
                band = normalized[i]
                mask = band > 0  # Ignore zero/nodata values
                if np.any(mask):
                    mean_val = np.mean(band[mask])
                    std_val = np.std(band[mask])
                    if std_val > 0:
                        normalized[i] = (band - mean_val) / std_val
        else:
            mask = normalized > 0
            if np.any(mask):
                mean_val = np.mean(normalized[mask])
                std_val = np.std(normalized[mask])
                if std_val > 0:
                    normalized = (normalized - mean_val) / std_val
    
    elif method == 'minmax':
        # Min-max normalization to [0, 1]
        if image.ndim > 2:
            for i in range(image.shape[0]):
                band = normalized[i]
                mask = band > 0
                if np.any(mask):
                    min_val = np.min(band[mask])
                    max_val = np.max(band[mask])
                    if max_val > min_val:
                        normalized[i] = (band - min_val) / (max_val - min_val)
        else:
            mask = normalized > 0
            if np.any(mask):
                min_val = np.min(normalized[mask])
                max_val = np.max(normalized[mask])
                if max_val > min_val:
                    normalized = (normalized - min_val) / (max_val - min_val)
    
    elif method == 'histmatch' and reference is not None:
        # Histogram matching (simplified)
        from skimage import exposure
        if image.ndim > 2 and reference.ndim > 2:
            for i in range(min(image.shape[0], reference.shape[0])):
                normalized[i] = exposure.match_histograms(
                    normalized[i], reference[i]
                )
        else:
            normalized = exposure.match_histograms(normalized, reference)
    
    return normalized


def calculate_area_m2(polygon_pixels: int, pixel_size_x: float, 
                     pixel_size_y: float) -> float:
    """Calculate area in square meters from pixel count."""
    return polygon_pixels * pixel_size_x * pixel_size_y


def get_utm_crs(lon: float, lat: float) -> CRS:
    """Get appropriate UTM CRS for given coordinates."""
    utm_zone = int((lon + 180) / 6) + 1
    hemisphere = 'north' if lat >= 0 else 'south'
    return CRS.from_string(f'+proj=utm +zone={utm_zone} +{hemisphere} +datum=WGS84')


def bounds_to_transform(bounds: Tuple[float, float, float, float], 
                       width: int, height: int) -> Any:
    """Create transform from bounds and dimensions."""
    return from_bounds(*bounds, width, height)