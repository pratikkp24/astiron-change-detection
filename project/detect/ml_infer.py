"""
ML inference module for change detection (Stage-2 preparation).
"""

import numpy as np
import onnxruntime as ort
import logging
from typing import Tuple, Dict, Any, Optional
import os


class ONNXChangeDetector:
    """ONNX-based change detection model."""
    
    def __init__(self, model_path: str):
        """
        Initialize ONNX model.
        
        Args:
            model_path: Path to ONNX model file
        """
        self.logger = logging.getLogger(__name__)
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"ONNX model not found: {model_path}")
        
        # Create ONNX Runtime session
        self.session = ort.InferenceSession(model_path)
        
        # Get model input/output info
        self.input_name = self.session.get_inputs()[0].name
        self.input_shape = self.session.get_inputs()[0].shape
        self.output_name = self.session.get_outputs()[0].name
        
        self.logger.info(f"Loaded ONNX model: {model_path}")
        self.logger.info(f"Input shape: {self.input_shape}")
    
    def preprocess_images(self, image_before: np.ndarray, 
                         image_after: np.ndarray,
                         input_bands: str = 'RGB') -> np.ndarray:
        """
        Preprocess images for model input.
        
        Args:
            image_before: Before image
            image_after: After image
            input_bands: Which bands to use ('RGB', 'ALL')
            
        Returns:
            Preprocessed input tensor
        """
        # Select bands
        if input_bands == 'RGB' and image_before.shape[0] >= 3:
            before_bands = image_before[:3]  # R, G, B
            after_bands = image_after[:3]
        else:
            before_bands = image_before
            after_bands = image_after
        
        # Stack before and after images
        stacked = np.concatenate([before_bands, after_bands], axis=0)
        
        # Add batch dimension: (1, channels, height, width)
        input_tensor = np.expand_dims(stacked, axis=0).astype(np.float32)
        
        # Normalize to [0, 1] if needed
        if input_tensor.max() > 1.0:
            input_tensor = input_tensor / 255.0
        
        return input_tensor
    
    def predict(self, image_before: np.ndarray, image_after: np.ndarray,
                input_bands: str = 'RGB') -> np.ndarray:
        """
        Predict change probability map.
        
        Args:
            image_before: Before image
            image_after: After image
            input_bands: Which bands to use
            
        Returns:
            Change probability map (0-1)
        """
        # Preprocess
        input_tensor = self.preprocess_images(image_before, image_after, input_bands)
        
        # Run inference
        outputs = self.session.run([self.output_name], {self.input_name: input_tensor})
        prob_map = outputs[0][0, 0]  # Remove batch and channel dimensions
        
        return prob_map


def ml_change_detection(image_before: np.ndarray, image_after: np.ndarray,
                       config: Dict[str, Any]) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Perform ML-based change detection on image pair.
    
    Args:
        image_before: Before image
        image_after: After image
        config: Configuration dictionary
        
    Returns:
        Tuple of (binary_mask, metadata)
    """
    logger = logging.getLogger(__name__)
    
    # Extract configuration
    ml_config = config['detect']['ml']
    model_path = ml_config['onnx_model']
    prob_threshold = ml_config['prob_threshold']
    input_bands = ml_config['input_bands']
    
    logger.info(f"ML detection using model: {model_path}")
    
    try:
        # Initialize model
        detector = ONNXChangeDetector(model_path)
        
        # Predict change probability
        prob_map = detector.predict(image_before, image_after, input_bands)
        
        # Threshold to binary mask
        binary_mask = (prob_map > prob_threshold).astype(np.uint8)
        
        # Calculate statistics
        total_pixels = binary_mask.size
        change_pixels = np.sum(binary_mask)
        change_percentage = (change_pixels / total_pixels) * 100
        mean_prob = float(np.mean(prob_map))
        max_prob = float(np.max(prob_map))
        
        metadata = {
            'algorithm': 'ml',
            'model_path': model_path,
            'input_bands': input_bands,
            'prob_threshold': prob_threshold,
            'total_pixels': int(total_pixels),
            'change_pixels': int(change_pixels),
            'change_percentage': float(change_percentage),
            'mean_probability': mean_prob,
            'max_probability': max_prob
        }
        
        logger.info(f"ML detection complete: {change_pixels:,} pixels ({change_percentage:.2f}%)")
        logger.info(f"Mean probability: {mean_prob:.3f}, Max: {max_prob:.3f}")
        
        return binary_mask, metadata
        
    except Exception as e:
        logger.error(f"ML detection failed: {e}")
        # Fallback to classical method
        logger.info("Falling back to classical detection")
        from classical import classical_change_detection
        return classical_change_detection(image_before, image_after, config)


def is_ml_available(config: Dict[str, Any]) -> bool:
    """Check if ML model is available."""
    ml_config = config['detect']['ml']
    model_path = ml_config['onnx_model']
    return os.path.exists(model_path)