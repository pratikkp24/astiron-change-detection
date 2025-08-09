"""
Test tiling and stitching functionality.
"""

import pytest
import numpy as np
import tempfile
import os
from pathlib import Path
import sys

# Add common modules to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'project', 'common'))

from tiles import TileManager
import rasterio
from rasterio.transform import from_bounds


def create_test_raster(width=1000, height=1000, output_path=None):
    """Create a test raster for tiling tests."""
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.tif')
    
    # Create synthetic data
    data = np.random.randint(0, 255, (3, height, width), dtype=np.uint8)
    
    # Create transform (simple geographic)
    bounds = (-1, -1, 1, 1)  # Simple bounds
    transform = from_bounds(*bounds, width, height)
    
    profile = {
        'driver': 'GTiff',
        'dtype': 'uint8',
        'count': 3,
        'width': width,
        'height': height,
        'crs': 'EPSG:4326',
        'transform': transform,
        'compress': 'lzw'
    }
    
    with rasterio.open(output_path, 'w', **profile) as dst:
        dst.write(data)
    
    return output_path


def test_tile_generation():
    """Test tile window generation."""
    tile_manager = TileManager(tile_size=256, overlap=32)
    
    # Test with 1000x1000 image
    tiles = tile_manager.generate_tiles(1000, 1000)
    
    # Should generate 5x5 = 25 tiles (with overlap)
    # Step size = 256 - 32 = 224
    # Tiles at: 0, 224, 448, 672, 896 (5 tiles per dimension)
    assert len(tiles) == 25
    
    # Check first tile
    first_tile = tiles[0]
    assert first_tile['window']['col_off'] == 0
    assert first_tile['window']['row_off'] == 0
    assert first_tile['window']['width'] == 256
    assert first_tile['window']['height'] == 256
    
    # Check last tile (should be smaller due to image boundary)
    last_tile = tiles[-1]
    assert last_tile['window']['col_off'] == 896
    assert last_tile['window']['row_off'] == 896
    assert last_tile['window']['width'] == 104  # 1000 - 896
    assert last_tile['window']['height'] == 104


def test_tile_manifest_creation():
    """Test tile manifest creation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test rasters
        raster_a = create_test_raster(500, 500)
        raster_b = create_test_raster(500, 500)
        
        tile_manager = TileManager(tile_size=128, overlap=16)
        
        # Create manifest
        manifest = tile_manager.create_tile_manifest(
            raster_a, raster_b, temp_dir, 'test_pair'
        )
        
        # Check manifest structure
        assert manifest['pair_id'] == 'test_pair'
        assert manifest['width'] == 500
        assert manifest['height'] == 500
        assert manifest['tile_size'] == 128
        assert manifest['overlap'] == 16
        assert len(manifest['tiles']) > 0
        
        # Check tile paths
        for tile in manifest['tiles']:
            assert 'path_a' in tile
            assert 'path_b' in tile
            assert 'test_pair' in tile['path_a']
        
        # Cleanup
        os.unlink(raster_a)
        os.unlink(raster_b)


def test_tile_extraction():
    """Test tile extraction from rasters."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test rasters
        raster_a = create_test_raster(300, 300)
        raster_b = create_test_raster(300, 300)
        
        tile_manager = TileManager(tile_size=100, overlap=10)
        
        # Create and extract tiles
        manifest = tile_manager.create_tile_manifest(
            raster_a, raster_b, temp_dir, 'test_pair'
        )
        
        tile_manager.extract_tiles(manifest)
        
        # Check that tile files were created
        for tile in manifest['tiles']:
            assert os.path.exists(tile['path_a'])
            assert os.path.exists(tile['path_b'])
            
            # Check tile dimensions
            with rasterio.open(tile['path_a']) as src:
                assert src.width <= 100
                assert src.height <= 100
                assert src.count == 3  # RGB
        
        # Cleanup
        os.unlink(raster_a)
        os.unlink(raster_b)


def test_tile_stitching():
    """Test stitching tiles back together."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test raster with known pattern
        width, height = 200, 200
        data = np.zeros((1, height, width), dtype=np.uint8)
        
        # Create a checkerboard pattern for easy verification
        for i in range(0, height, 50):
            for j in range(0, width, 50):
                if (i // 50 + j // 50) % 2 == 0:
                    data[0, i:i+50, j:j+50] = 255
        
        # Save original
        original_path = os.path.join(temp_dir, 'original.tif')
        profile = {
            'driver': 'GTiff',
            'dtype': 'uint8',
            'count': 1,
            'width': width,
            'height': height,
            'crs': 'EPSG:4326',
            'transform': from_bounds(-1, -1, 1, 1, width, height)
        }
        
        with rasterio.open(original_path, 'w', **profile) as dst:
            dst.write(data)
        
        # Create tiles
        tile_manager = TileManager(tile_size=64, overlap=8)
        
        # Simulate tile results (just copy original data to tiles)
        tiles = tile_manager.generate_tiles(width, height)
        tile_results = []
        
        for i, tile in enumerate(tiles):
            tile_path = os.path.join(temp_dir, f'tile_{i}.tif')
            
            # Extract tile data
            row_start = tile['bounds']['row_start']
            row_end = tile['bounds']['row_end']
            col_start = tile['bounds']['col_start']
            col_end = tile['bounds']['col_end']
            
            tile_data = data[:, row_start:row_end, col_start:col_end]
            
            tile_profile = profile.copy()
            tile_profile.update({
                'width': col_end - col_start,
                'height': row_end - row_start
            })
            
            with rasterio.open(tile_path, 'w', **tile_profile) as dst:
                dst.write(tile_data)
            
            tile_results.append({
                'result_path': tile_path,
                'bounds': tile['bounds']
            })
        
        # Stitch tiles
        stitched_path = os.path.join(temp_dir, 'stitched.tif')
        tile_manager.stitch_tiles(tile_results, stitched_path, original_path)
        
        # Verify stitched result
        with rasterio.open(stitched_path) as stitched:
            stitched_data = stitched.read(1)
            
            # Should be close to original (allowing for blending effects)
            # Check that general pattern is preserved
            assert stitched_data.shape == (height, width)
            
            # Check corners (should be exact since no overlap there)
            assert stitched_data[0, 0] == data[0, 0, 0]
            assert stitched_data[-1, -1] == data[0, -1, -1]


def test_blend_weights():
    """Test blend weight generation."""
    tile_manager = TileManager()
    
    # Test weight generation
    weights = tile_manager._create_blend_weights(100, 100)
    
    assert weights.shape == (100, 100)
    assert weights.dtype == np.float32
    
    # Center should have highest weight
    center_weight = weights[50, 50]
    edge_weight = weights[0, 0]
    
    assert center_weight > edge_weight
    assert center_weight <= 1.0
    assert edge_weight >= 0.1


if __name__ == '__main__':
    # Run tests
    test_tile_generation()
    test_tile_manifest_creation()
    test_tile_extraction()
    test_tile_stitching()
    test_blend_weights()
    
    print("All tile tests passed!")