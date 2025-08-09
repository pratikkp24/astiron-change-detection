"""
Vectorization utilities for converting raster masks to vector polygons.
"""

import numpy as np
import rasterio
import rasterio.features
import geopandas as gpd
from shapely.geometry import shape, Polygon
from shapely.ops import unary_union
import logging
from typing import List, Dict, Any, Optional, Tuple
import os


def raster_to_polygons(raster_path: str, 
                      min_area_m2: float = 100.0,
                      simplify_tolerance_m: float = 0.5) -> gpd.GeoDataFrame:
    """
    Convert binary raster to polygon GeoDataFrame.
    
    Args:
        raster_path: Path to binary raster (1=change, 0=no change)
        min_area_m2: Minimum polygon area in square meters
        simplify_tolerance_m: Simplification tolerance in meters
        
    Returns:
        GeoDataFrame with change polygons
    """
    logger = logging.getLogger(__name__)
    
    with rasterio.open(raster_path) as src:
        # Read binary mask
        mask = src.read(1)
        transform = src.transform
        crs = src.crs
        
        # Extract polygons from raster
        shapes = rasterio.features.shapes(
            mask.astype(np.uint8), 
            mask=(mask == 1), 
            transform=transform
        )
        
        # Convert to shapely polygons
        polygons = []
        for geom, value in shapes:
            if value == 1:  # Only change pixels
                poly = shape(geom)
                if poly.is_valid:
                    polygons.append(poly)
        
        logger.info(f"Extracted {len(polygons)} raw polygons")
        
        if not polygons:
            # Return empty GeoDataFrame with correct schema
            return gpd.GeoDataFrame(
                columns=['geometry', 'area_m2', 'perimeter_m', 'change_id'],
                crs=crs
            )
        
        # Create GeoDataFrame
        gdf = gpd.GeoDataFrame(geometry=polygons, crs=crs)
        
        # Calculate areas and filter
        if crs and crs.is_geographic:
            # Convert to appropriate projected CRS for area calculation
            utm_crs = _get_utm_crs_from_bounds(gdf.total_bounds)
            gdf_proj = gdf.to_crs(utm_crs)
            areas_m2 = gdf_proj.geometry.area
            perimeters_m = gdf_proj.geometry.length
        else:
            # Assume already in projected coordinates
            areas_m2 = gdf.geometry.area
            perimeters_m = gdf.geometry.length
        
        # Add attributes
        gdf['area_m2'] = areas_m2
        gdf['perimeter_m'] = perimeters_m
        gdf['change_id'] = range(1, len(gdf) + 1)
        
        # Filter by minimum area
        gdf_filtered = gdf[gdf['area_m2'] >= min_area_m2].copy()
        logger.info(f"Filtered to {len(gdf_filtered)} polygons (min area: {min_area_m2} m²)")
        
        # Simplify geometries
        if simplify_tolerance_m > 0 and len(gdf_filtered) > 0:
            if crs and crs.is_geographic:
                # Simplify in projected coordinates
                gdf_proj = gdf_filtered.to_crs(utm_crs)
                gdf_proj['geometry'] = gdf_proj.geometry.simplify(simplify_tolerance_m)
                gdf_filtered = gdf_proj.to_crs(crs)
            else:
                gdf_filtered['geometry'] = gdf_filtered.geometry.simplify(simplify_tolerance_m)
            
            logger.info(f"Simplified polygons with tolerance {simplify_tolerance_m} m")
        
        # Reset change_id after filtering
        gdf_filtered = gdf_filtered.reset_index(drop=True)
        gdf_filtered['change_id'] = range(1, len(gdf_filtered) + 1)
        
        return gdf_filtered


def save_shapefile(gdf: gpd.GeoDataFrame, output_path: str) -> None:
    """Save GeoDataFrame as shapefile."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    if len(gdf) == 0:
        # Create empty shapefile with correct schema
        empty_gdf = gpd.GeoDataFrame(
            columns=['geometry', 'area_m2', 'perimeter_m', 'change_id'],
            crs=gdf.crs
        )
        empty_gdf.to_file(output_path)
    else:
        gdf.to_file(output_path)


def save_geojson(gdf: gpd.GeoDataFrame, output_path: str) -> None:
    """Save GeoDataFrame as GeoJSON."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    if len(gdf) == 0:
        # Create empty GeoJSON with correct schema
        empty_gdf = gpd.GeoDataFrame(
            columns=['geometry', 'area_m2', 'perimeter_m', 'change_id'],
            crs=gdf.crs
        )
        empty_gdf.to_file(output_path, driver='GeoJSON')
    else:
        gdf.to_file(output_path, driver='GeoJSON')


def clean_polygons(gdf: gpd.GeoDataFrame, 
                  buffer_distance: float = 0.0) -> gpd.GeoDataFrame:
    """
    Clean polygon geometries.
    
    Args:
        gdf: Input GeoDataFrame
        buffer_distance: Buffer distance for cleaning (0 = no buffer)
        
    Returns:
        Cleaned GeoDataFrame
    """
    if len(gdf) == 0:
        return gdf
    
    cleaned_gdf = gdf.copy()
    
    # Fix invalid geometries
    invalid_mask = ~cleaned_gdf.geometry.is_valid
    if invalid_mask.any():
        logging.info(f"Fixing {invalid_mask.sum()} invalid geometries")
        cleaned_gdf.loc[invalid_mask, 'geometry'] = (
            cleaned_gdf.loc[invalid_mask, 'geometry'].buffer(0)
        )
    
    # Apply buffer if specified (can help clean small artifacts)
    if buffer_distance > 0:
        cleaned_gdf['geometry'] = (
            cleaned_gdf.geometry
            .buffer(buffer_distance)
            .buffer(-buffer_distance)
        )
    
    # Remove empty geometries
    empty_mask = cleaned_gdf.geometry.is_empty
    if empty_mask.any():
        logging.info(f"Removing {empty_mask.sum()} empty geometries")
        cleaned_gdf = cleaned_gdf[~empty_mask]
    
    return cleaned_gdf.reset_index(drop=True)


def merge_nearby_polygons(gdf: gpd.GeoDataFrame, 
                         distance_threshold: float = 10.0) -> gpd.GeoDataFrame:
    """
    Merge polygons that are within distance threshold.
    
    Args:
        gdf: Input GeoDataFrame
        distance_threshold: Distance threshold in map units
        
    Returns:
        GeoDataFrame with merged polygons
    """
    if len(gdf) <= 1:
        return gdf
    
    # Create spatial index for efficiency
    spatial_index = gdf.sindex
    
    # Find nearby polygons
    merged_groups = []
    processed = set()
    
    for idx, geom in enumerate(gdf.geometry):
        if idx in processed:
            continue
        
        # Find nearby polygons
        possible_matches_index = list(spatial_index.intersection(geom.bounds))
        possible_matches = gdf.iloc[possible_matches_index]
        
        # Check actual distance
        nearby_indices = []
        for match_idx in possible_matches_index:
            if match_idx != idx and match_idx not in processed:
                distance = geom.distance(gdf.geometry.iloc[match_idx])
                if distance <= distance_threshold:
                    nearby_indices.append(match_idx)
        
        if nearby_indices:
            # Merge with nearby polygons
            group_indices = [idx] + nearby_indices
            group_geoms = [gdf.geometry.iloc[i] for i in group_indices]
            merged_geom = unary_union(group_geoms)
            
            # Calculate new attributes
            total_area = sum(gdf.area_m2.iloc[group_indices])
            
            merged_groups.append({
                'geometry': merged_geom,
                'area_m2': total_area,
                'perimeter_m': merged_geom.length if hasattr(merged_geom, 'length') else 0,
                'change_id': len(merged_groups) + 1
            })
            
            processed.update(group_indices)
        else:
            # Keep original polygon
            merged_groups.append({
                'geometry': geom,
                'area_m2': gdf.area_m2.iloc[idx],
                'perimeter_m': gdf.perimeter_m.iloc[idx],
                'change_id': len(merged_groups) + 1
            })
            processed.add(idx)
    
    # Create new GeoDataFrame
    merged_gdf = gpd.GeoDataFrame(merged_groups, crs=gdf.crs)
    
    logging.info(f"Merged {len(gdf)} polygons into {len(merged_gdf)} polygons")
    
    return merged_gdf


def _get_utm_crs_from_bounds(bounds: Tuple[float, float, float, float]) -> str:
    """Get appropriate UTM CRS from geographic bounds."""
    minx, miny, maxx, maxy = bounds
    center_lon = (minx + maxx) / 2
    center_lat = (miny + maxy) / 2
    
    utm_zone = int((center_lon + 180) / 6) + 1
    hemisphere = 'north' if center_lat >= 0 else 'south'
    
    return f'+proj=utm +zone={utm_zone} +{hemisphere} +datum=WGS84'


def calculate_polygon_stats(gdf: gpd.GeoDataFrame) -> Dict[str, Any]:
    """Calculate summary statistics for polygon collection."""
    if len(gdf) == 0:
        return {
            'total_polygons': 0,
            'total_area_m2': 0.0,
            'total_area_km2': 0.0,
            'mean_area_m2': 0.0,
            'median_area_m2': 0.0,
            'largest_area_m2': 0.0,
            'smallest_area_m2': 0.0
        }
    
    areas = gdf['area_m2']
    
    return {
        'total_polygons': len(gdf),
        'total_area_m2': float(areas.sum()),
        'total_area_km2': float(areas.sum() / 1_000_000),
        'mean_area_m2': float(areas.mean()),
        'median_area_m2': float(areas.median()),
        'largest_area_m2': float(areas.max()),
        'smallest_area_m2': float(areas.min())
    }