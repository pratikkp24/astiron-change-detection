"""
Input/Output utilities for PS-10 Change Detection pipeline.
"""

import os
import json
import csv
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import yaml
import rasterio
import numpy as np
from rasterio.windows import Window


def setup_logging(log_dir: str, name: str = "ps10") -> logging.Logger:
    """Setup logging with file and console handlers."""
    os.makedirs(log_dir, exist_ok=True)
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # File handler
    log_file = os.path.join(log_dir, f"{name}.log")
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def load_config(config_path: str) -> Dict[str, Any]:
    """Load YAML configuration file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def load_pairs_csv(csv_path: str) -> List[Dict[str, str]]:
    """Load pairs CSV file and return list of pair dictionaries."""
    pairs = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pairs.append(row)
    return pairs


def save_manifest(manifest: Dict[str, Any], output_path: str) -> None:
    """Save processing manifest as JSON."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(manifest, f, indent=2)


def load_manifest(manifest_path: str) -> Dict[str, Any]:
    """Load processing manifest from JSON."""
    with open(manifest_path, 'r') as f:
        return json.load(f)


def read_raster_info(raster_path: str) -> Dict[str, Any]:
    """Read basic raster information without loading data."""
    with rasterio.open(raster_path) as src:
        return {
            'path': raster_path,
            'width': src.width,
            'height': src.height,
            'count': src.count,
            'dtype': str(src.dtype),
            'crs': str(src.crs) if src.crs else None,
            'transform': list(src.transform),
            'bounds': list(src.bounds),
            'nodata': src.nodata
        }


def read_raster_window(raster_path: str, window: Window) -> Tuple[np.ndarray, Dict]:
    """Read a window from raster file."""
    with rasterio.open(raster_path) as src:
        data = src.read(window=window)
        profile = src.profile.copy()
        
        # Update profile for window
        profile.update({
            'height': window.height,
            'width': window.width,
            'transform': rasterio.windows.transform(window, src.transform)
        })
        
        return data, profile


def write_raster(data: np.ndarray, profile: Dict, output_path: str) -> None:
    """Write raster data to file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with rasterio.open(output_path, 'w', **profile) as dst:
        if data.ndim == 2:
            dst.write(data, 1)
        else:
            dst.write(data)


def ensure_dir(path: str) -> None:
    """Ensure directory exists."""
    os.makedirs(path, exist_ok=True)


def get_memory_usage() -> float:
    """Get current memory usage in MB."""
    try:
        import psutil
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        return 0.0


def log_performance(logger: logging.Logger, operation: str, 
                   start_time: float, memory_before: float) -> None:
    """Log performance metrics for an operation."""
    import time
    
    end_time = time.time()
    memory_after = get_memory_usage()
    
    logger.info(f"{operation} completed in {end_time - start_time:.2f}s, "
               f"memory: {memory_before:.1f} -> {memory_after:.1f} MB "
               f"(+{memory_after - memory_before:.1f} MB)")