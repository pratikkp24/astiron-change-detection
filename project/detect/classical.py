"""
Classical change detection algorithms for PS-10 pipeline.
"""

import numpy as np
import cv2
from scipy import ndimage
from skimage import filters, morphology, measure
from skimage.filters import threshold_otsu, threshold_local
import logging
from typing import Tuple, Dict, Any


def compute_change_index(image_before: np.ndarray, image_after: np.ndarray, 
                        method: str = 'logratio') -> np.ndarray:
    """
    Compute change index between two images.
    
    Args:
        image_before: Before image (bands, height, width) or (height, width)
        image_after: After image (same shape as before)
        method: Change index method ('absdiff', 'ratio', 'logratio')
        
    Returns:
        Change index array (height, width)
    """
    # Convert to grayscale if multi-band
    if image_before.ndim == 3:
        # Use mean of first 3 bands (RGB) or all bands if fewer
        num_bands = min(3, image_before.shape[0])
        before_gray = np.mean(image_before[:num_bands], axis=0)
        after_gray = np.mean(image_after[:num_bands], axis=0)
    else:
        before_gray = image_before
        after_gray = image_after
    
    # Ensure float type and positive values
    before_gray = before_gray.astype(np.float32)
    after_gray = after_gray.astype(np.float32)
    
    # Add small epsilon to avoid division by zero
    epsilon = 1e-8
    before_gray = np.maximum(before_gray, epsilon)
    after_gray = np.maximum(after_gray, epsilon)
    
    if method == 'absdiff':
        # Absolute difference
        change_index = np.abs(after_gray - before_gray)
    
    elif method == 'ratio':
        # Simple ratio
        change_index = np.maximum(after_gray / before_gray, before_gray / after_gray)
        change_index = change_index - 1.0  # Subtract 1 so no-change = 0
    
    elif method == 'logratio':
        # Log ratio (more robust to illumination changes)
        change_index = np.abs(np.log(after_gray + epsilon) - np.log(before_gray + epsilon))
    
    else:
        raise ValueError(f"Unknown change index method: {method}")
    
    return change_index


def denoise_image(image: np.ndarray, method: str = 'bilateral', 
                 **kwargs) -> np.ndarray:
    """
    Apply denoising to change index image.
    
    Args:
        image: Input image
        method: Denoising method ('none', 'gaussian', 'bilateral')
        **kwargs: Additional parameters for denoising
        
    Returns:
        Denoised image
    """
    if method == 'none':
        return image
    
    # Normalize to 0-255 for OpenCV functions
    image_norm = cv2.normalize(image, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
    
    if method == 'gaussian':
        kernel_size = kwargs.get('kernel_size', 5)
        sigma = kwargs.get('sigma', 1.0)
        denoised = cv2.GaussianBlur(image_norm, (kernel_size, kernel_size), sigma)
    
    elif method == 'bilateral':
        d = kwargs.get('d', 9)
        sigma_color = kwargs.get('sigma_color', 75)
        sigma_space = kwargs.get('sigma_space', 75)
        denoised = cv2.bilateralFilter(image_norm, d, sigma_color, sigma_space)
    
    else:
        raise ValueError(f"Unknown denoising method: {method}")
    
    # Convert back to original range
    return denoised.astype(np.float32) / 255.0 * image.max()


def threshold_change_index(change_index: np.ndarray, method: str = 'otsu',
                          **kwargs) -> np.ndarray:
    """
    Apply thresholding to change index to create binary mask.
    
    Args:
        change_index: Change index image
        method: Thresholding method ('otsu', 'adaptive', 'manual')
        **kwargs: Additional parameters
        
    Returns:
        Binary mask (1=change, 0=no change)
    """
    if method == 'otsu':
        # Otsu's automatic threshold selection
        threshold = threshold_otsu(change_index)
        binary_mask = change_index > threshold
    
    elif method == 'adaptive':
        # Adaptive thresholding
        block_size = kwargs.get('block_size', 51)
        offset = kwargs.get('offset', 0.01)
        
        # Convert to uint8 for adaptive threshold
        change_norm = cv2.normalize(change_index, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
        
        # Apply adaptive threshold
        binary_norm = cv2.adaptiveThreshold(
            change_norm, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, block_size, offset * 255
        )
        
        binary_mask = binary_norm > 0
    
    elif method == 'manual':
        threshold = kwargs.get('threshold', 0.1)
        binary_mask = change_index > threshold
    
    else:
        raise ValueError(f"Unknown thresholding method: {method}")
    
    return binary_mask.astype(np.uint8)


def apply_morphological_operations(binary_mask: np.ndarray, 
                                 open_size: int = 3, 
                                 close_size: int = 5,
                                 min_area_px: int = 36) -> np.ndarray:
    """
    Apply morphological operations to clean binary mask.
    
    Args:
        binary_mask: Input binary mask
        open_size: Size of opening kernel
        close_size: Size of closing kernel
        min_area_px: Minimum area in pixels for connected components
        
    Returns:
        Cleaned binary mask
    """
    # Create structuring elements
    open_kernel = morphology.disk(open_size)
    close_kernel = morphology.disk(close_size)
    
    # Apply morphological opening (removes small noise)
    if open_size > 0:
        cleaned = morphology.binary_opening(binary_mask, open_kernel)
    else:
        cleaned = binary_mask
    
    # Apply morphological closing (fills small holes)
    if close_size > 0:
        cleaned = morphology.binary_closing(cleaned, close_kernel)
    
    # Remove small connected components
    if min_area_px > 0:
        cleaned = morphology.remove_small_objects(
            cleaned.astype(bool), min_size=min_area_px
        ).astype(np.uint8)
    
    return cleaned


def classical_change_detection(image_before: np.ndarray, image_after: np.ndarray,
                             config: Dict[str, Any]) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Perform classical change detection on image pair.
    
    Args:
        image_before: Before image
        image_after: After image
        config: Configuration dictionary
        
    Returns:
        Tuple of (binary_mask, metadata)
    """
    logger = logging.getLogger(__name__)
    
    # Extract configuration
    classical_config = config['detect']['classical']
    index_method = classical_config['index']
    denoise_method = classical_config['denoise']
    thresh_method = classical_config['thresh']
    morph_config = classical_config['morph']
    
    logger.info(f"Classical detection: {index_method} + {thresh_method} + morphology")
    
    # Step 1: Compute change index
    change_index = compute_change_index(image_before, image_after, index_method)
    
    # Step 2: Denoising
    if denoise_method != 'none':
        change_index = denoise_image(change_index, denoise_method)
    
    # Step 3: Thresholding
    binary_mask = threshold_change_index(change_index, thresh_method)
    
    # Step 4: Morphological operations
    binary_mask = apply_morphological_operations(
        binary_mask,
        open_size=morph_config['open_size'],
        close_size=morph_config['close_size'],
        min_area_px=morph_config['min_area_px']
    )
    
    # Calculate statistics
    total_pixels = binary_mask.size
    change_pixels = np.sum(binary_mask)
    change_percentage = (change_pixels / total_pixels) * 100
    
    metadata = {
        'algorithm': 'classical',
        'index_method': index_method,
        'denoise_method': denoise_method,
        'threshold_method': thresh_method,
        'total_pixels': int(total_pixels),
        'change_pixels': int(change_pixels),
        'change_percentage': float(change_percentage),
        'morphology_config': morph_config
    }
    
    logger.info(f"Change detection complete: {change_pixels:,} pixels ({change_percentage:.2f}%)")
    
    return binary_mask, metadata


def get_algorithm_description(config: Dict[str, Any]) -> str:
    """Get string description of classical algorithm for hashing."""
    classical_config = config['detect']['classical']
    
    description = (
        f"classical_{classical_config['index']}_"
        f"{classical_config['thresh']}_"
        f"morph_open{classical_config['morph']['open_size']}_"
        f"close{classical_config['morph']['close_size']}_"
        f"minarea{classical_config['morph']['min_area_px']}_"
        f"denoise_{classical_config['denoise']}_v1.0"
    )
    
    return description