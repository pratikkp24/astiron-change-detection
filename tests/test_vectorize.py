"""
Test vectorization functionality.
"""

import pytest
import numpy as np
import tempfile
import os
import sys

# Add common modules to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'project', 'common'))

from vectorize import raster_to_polygons, calculate_polygon_stats
import rasterio
from rasterio.transform import from_bounds
import geopandas as gpd


def create_test_mask(width=100, height=100, output_path=None):
    """Create a test binary mask with known shapes."""
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.tif')
    
    # Create binary mask with some shapes
    mask = np.zeros((height, width), dtype=np.uint8)
    
    # Add a large rectangle
    mask[20:40, 20:60] = 1
    
    # Add a small square
    mask[60:70, 60:70] = 1
    
    # Add a tiny shape (should be filtered out)
    mask[80:82, 80:82] = 1
    
    # Create transform (1m pixel size for easy area calculation)
    bounds = (0, 0, width, height)
    transform = from_bounds(*bounds, width, height)
    
    profile = {
        'driver': 'GTiff',
        'dtype': 'uint8',
        'count': 1,
        'width': width,
        'height': height,
        'crs': 'EPSG:32633',  # UTM zone 33N (projected, meters)
        'transform': transform
    }
    
    with rasterio.open(output_path, 'w', **profile) as dst:
        dst.write(mask, 1)
    
    return output_path


def test_raster_to_polygons():
    """Test conversion from raster to polygons."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test mask
        mask_path = create_test_mask()
        
        # Convert to polygons
        gdf = raster_to_polygons(mask_path, min_area_m2=10, simplify_tolerance_m=0.1)
        
        # Should have 2 polygons (large rectangle and small square)
        # Tiny shape should be filtered out
        assert len(gdf) == 2
        
        # Check that areas are calculated
        assert 'area_m2' in gdf.columns
        assert 'perimeter_m' in gdf.columns
        assert 'change_id' in gdf.columns
        
        # Check area values (approximately)
        areas = sorted(gdf['area_m2'].values)
        
        # Small square: 10x10 = 100 m²
        assert abs(areas[0] - 100) < 10
        
        # Large rectangle: 20x40 = 800 m²
        assert abs(areas[1] - 800) < 50
        
        # Cleanup
        os.unlink(mask_path)


def test_empty_mask():
    """Test handling of empty mask."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create empty mask
        mask = np.zeros((100, 100), dtype=np.uint8)
        
        mask_path = tempfile.mktemp(suffix='.tif')
        profile = {
            'driver': 'GTiff',
            'dtype': 'uint8',
            'count': 1,
            'width': 100,
            'height': 100,
            'crs': 'EPSG:4326',
            'transform': from_bounds(0, 0, 1, 1, 100, 100)
        }
        
        with rasterio.open(mask_path, 'w', **profile) as dst:
            dst.write(mask, 1)
        
        # Convert to polygons
        gdf = raster_to_polygons(mask_path)
        
        # Should return empty GeoDataFrame with correct schema
        assert len(gdf) == 0
        assert 'area_m2' in gdf.columns
        assert 'perimeter_m' in gdf.columns
        assert 'change_id' in gdf.columns
        
        # Cleanup
        os.unlink(mask_path)


def test_area_filtering():
    """Test minimum area filtering."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test mask with various sizes
        mask_path = create_test_mask()
        
        # Test with high minimum area (should filter out small shapes)
        gdf_filtered = raster_to_polygons(mask_path, min_area_m2=500)
        
        # Should only have the large rectangle
        assert len(gdf_filtered) == 1
        assert gdf_filtered.iloc[0]['area_m2'] > 500
        
        # Test with low minimum area (should keep all significant shapes)
        gdf_all = raster_to_polygons(mask_path, min_area_m2=1)
        
        # Should have at least 2 shapes (might have 3 if tiny shape is kept)
        assert len(gdf_all) >= 2
        
        # Cleanup
        os.unlink(mask_path)


def test_polygon_stats():
    """Test polygon statistics calculation."""
    # Create mock GeoDataFrame
    from shapely.geometry import Polygon
    
    # Create some test polygons
    polygons = [
        Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]),  # 100 m²
        Polygon([(20, 20), (30, 20), (30, 25), (20, 25)]),  # 50 m²
        Polygon([(40, 40), (45, 40), (45, 45), (40, 45)])   # 25 m²
    ]
    
    gdf = gpd.GeoDataFrame({
        'geometry': polygons,
        'area_m2': [100.0, 50.0, 25.0],
        'perimeter_m': [40.0, 30.0, 20.0],
        'change_id': [1, 2, 3]
    })
    
    stats = calculate_polygon_stats(gdf)
    
    # Check statistics
    assert stats['total_polygons'] == 3
    assert stats['total_area_m2'] == 175.0
    assert stats['total_area_km2'] == 175.0 / 1_000_000
    assert stats['mean_area_m2'] == 175.0 / 3
    assert stats['median_area_m2'] == 50.0
    assert stats['largest_area_m2'] == 100.0
    assert stats['smallest_area_m2'] == 25.0


def test_empty_stats():
    """Test statistics for empty polygon set."""
    empty_gdf = gpd.GeoDataFrame(columns=['geometry', 'area_m2', 'perimeter_m', 'change_id'])
    
    stats = calculate_polygon_stats(empty_gdf)
    
    # All stats should be zero
    assert stats['total_polygons'] == 0
    assert stats['total_area_m2'] == 0.0
    assert stats['total_area_km2'] == 0.0
    assert stats['mean_area_m2'] == 0.0
    assert stats['median_area_m2'] == 0.0
    assert stats['largest_area_m2'] == 0.0
    assert stats['smallest_area_m2'] == 0.0


def test_geographic_to_projected_conversion():
    """Test area calculation with geographic coordinates."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create mask in geographic coordinates
        width, height = 100, 100
        mask = np.ones((height, width), dtype=np.uint8)
        
        # Small geographic area (roughly 1km x 1km near equator)
        bounds = (0, 0, 0.01, 0.01)  # degrees
        transform = from_bounds(*bounds, width, height)
        
        mask_path = tempfile.mktemp(suffix='.tif')
        profile = {
            'driver': 'GTiff',
            'dtype': 'uint8',
            'count': 1,
            'width': width,
            'height': height,
            'crs': 'EPSG:4326',  # Geographic
            'transform': transform
        }
        
        with rasterio.open(mask_path, 'w', **profile) as dst:
            dst.write(mask, 1)
        
        # Convert to polygons
        gdf = raster_to_polygons(mask_path)
        
        # Should have one polygon
        assert len(gdf) == 1
        
        # Area should be reasonable (roughly 1 km²)
        # Note: exact value depends on projection, but should be in right order of magnitude
        area_km2 = gdf.iloc[0]['area_m2'] / 1_000_000
        assert 0.5 < area_km2 < 2.0  # Reasonable range
        
        # Cleanup
        os.unlink(mask_path)


if __name__ == '__main__':
    # Run tests
    test_raster_to_polygons()
    test_empty_mask()
    test_area_filtering()
    test_polygon_stats()
    test_empty_stats()
    test_geographic_to_projected_conversion()
    
    print("All vectorization tests passed!")