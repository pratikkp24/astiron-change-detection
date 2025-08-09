"""
Metrics calculation utilities for change detection evaluation.
"""

import numpy as np
import rasterio
from typing import Tuple, Dict, Any, Optional
import logging


def calculate_jaccard_index(pred_path: str, gt_path: str) -> float:
    """
    Calculate Jaccard Index (IoU) between predicted and ground truth masks.
    
    Args:
        pred_path: Path to predicted binary mask
        gt_path: Path to ground truth binary mask
        
    Returns:
        Jaccard index (0.0 to 1.0)
    """
    with rasterio.open(pred_path) as pred_src, \
         rasterio.open(gt_path) as gt_src:
        
        # Read masks
        pred_mask = pred_src.read(1).astype(bool)
        gt_mask = gt_src.read(1).astype(bool)
        
        # Ensure same dimensions
        if pred_mask.shape != gt_mask.shape:
            raise ValueError(f"Mask dimensions don't match: {pred_mask.shape} vs {gt_mask.shape}")
        
        # Calculate intersection and union
        intersection = np.logical_and(pred_mask, gt_mask).sum()
        union = np.logical_or(pred_mask, gt_mask).sum()
        
        if union == 0:
            return 1.0 if intersection == 0 else 0.0
        
        return float(intersection / union)


def calculate_f1_score(pred_path: str, gt_path: str) -> Tuple[float, float, float]:
    """
    Calculate F1 score, precision, and recall.
    
    Args:
        pred_path: Path to predicted binary mask
        gt_path: Path to ground truth binary mask
        
    Returns:
        Tuple of (f1_score, precision, recall)
    """
    with rasterio.open(pred_path) as pred_src, \
         rasterio.open(gt_path) as gt_src:
        
        pred_mask = pred_src.read(1).astype(bool)
        gt_mask = gt_src.read(1).astype(bool)
        
        # Calculate confusion matrix components
        tp = np.logical_and(pred_mask, gt_mask).sum()  # True positives
        fp = np.logical_and(pred_mask, ~gt_mask).sum()  # False positives
        fn = np.logical_and(~pred_mask, gt_mask).sum()  # False negatives
        
        # Calculate metrics
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        return float(f1), float(precision), float(recall)


def calculate_confusion_matrix(pred_path: str, gt_path: str) -> Dict[str, int]:
    """
    Calculate confusion matrix components.
    
    Args:
        pred_path: Path to predicted binary mask
        gt_path: Path to ground truth binary mask
        
    Returns:
        Dictionary with TP, TN, FP, FN counts
    """
    with rasterio.open(pred_path) as pred_src, \
         rasterio.open(gt_path) as gt_src:
        
        pred_mask = pred_src.read(1).astype(bool)
        gt_mask = gt_src.read(1).astype(bool)
        
        tp = np.logical_and(pred_mask, gt_mask).sum()
        tn = np.logical_and(~pred_mask, ~gt_mask).sum()
        fp = np.logical_and(pred_mask, ~gt_mask).sum()
        fn = np.logical_and(~pred_mask, gt_mask).sum()
        
        return {
            'true_positives': int(tp),
            'true_negatives': int(tn),
            'false_positives': int(fp),
            'false_negatives': int(fn)
        }


def calculate_accuracy(pred_path: str, gt_path: str) -> float:
    """Calculate overall accuracy."""
    cm = calculate_confusion_matrix(pred_path, gt_path)
    total = sum(cm.values())
    correct = cm['true_positives'] + cm['true_negatives']
    
    return float(correct / total) if total > 0 else 0.0


def calculate_area_metrics(pred_path: str, gt_path: str, 
                          pixel_size_m2: Optional[float] = None) -> Dict[str, float]:
    """
    Calculate area-based metrics.
    
    Args:
        pred_path: Path to predicted binary mask
        gt_path: Path to ground truth binary mask
        pixel_size_m2: Pixel area in square meters (calculated if None)
        
    Returns:
        Dictionary with area metrics
    """
    with rasterio.open(pred_path) as pred_src, \
         rasterio.open(gt_path) as gt_src:
        
        pred_mask = pred_src.read(1).astype(bool)
        gt_mask = gt_src.read(1).astype(bool)
        
        if pixel_size_m2 is None:
            # Calculate pixel size from transform
            transform = pred_src.transform
            pixel_size_m2 = abs(transform[0] * transform[4])
        
        pred_area_px = pred_mask.sum()
        gt_area_px = gt_mask.sum()
        intersection_px = np.logical_and(pred_mask, gt_mask).sum()
        
        pred_area_m2 = pred_area_px * pixel_size_m2
        gt_area_m2 = gt_area_px * pixel_size_m2
        intersection_m2 = intersection_px * pixel_size_m2
        
        # Area-based metrics
        area_precision = intersection_m2 / pred_area_m2 if pred_area_m2 > 0 else 0.0
        area_recall = intersection_m2 / gt_area_m2 if gt_area_m2 > 0 else 0.0
        area_error = abs(pred_area_m2 - gt_area_m2) / gt_area_m2 if gt_area_m2 > 0 else 0.0
        
        return {
            'predicted_area_m2': float(pred_area_m2),
            'ground_truth_area_m2': float(gt_area_m2),
            'intersection_area_m2': float(intersection_m2),
            'area_precision': float(area_precision),
            'area_recall': float(area_recall),
            'relative_area_error': float(area_error)
        }


def evaluate_change_detection(pred_path: str, gt_path: str, 
                            pixel_size_m2: Optional[float] = None) -> Dict[str, Any]:
    """
    Comprehensive evaluation of change detection results.
    
    Args:
        pred_path: Path to predicted binary mask
        gt_path: Path to ground truth binary mask
        pixel_size_m2: Pixel area in square meters
        
    Returns:
        Dictionary with all evaluation metrics
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Basic metrics
        jaccard = calculate_jaccard_index(pred_path, gt_path)
        f1, precision, recall = calculate_f1_score(pred_path, gt_path)
        accuracy = calculate_accuracy(pred_path, gt_path)
        
        # Confusion matrix
        cm = calculate_confusion_matrix(pred_path, gt_path)
        
        # Area metrics
        area_metrics = calculate_area_metrics(pred_path, gt_path, pixel_size_m2)
        
        results = {
            'jaccard_index': jaccard,
            'f1_score': f1,
            'precision': precision,
            'recall': recall,
            'accuracy': accuracy,
            'confusion_matrix': cm,
            **area_metrics
        }
        
        logger.info(f"Evaluation complete - Jaccard: {jaccard:.3f}, F1: {f1:.3f}")
        
        return results
        
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        return {}


def print_evaluation_report(metrics: Dict[str, Any]) -> None:
    """Print formatted evaluation report."""
    if not metrics:
        print("No metrics available")
        return
    
    print("\n" + "="*50)
    print("CHANGE DETECTION EVALUATION REPORT")
    print("="*50)
    
    print(f"\nPixel-based Metrics:")
    print(f"  Jaccard Index (IoU): {metrics.get('jaccard_index', 0):.4f}")
    print(f"  F1 Score:           {metrics.get('f1_score', 0):.4f}")
    print(f"  Precision:          {metrics.get('precision', 0):.4f}")
    print(f"  Recall:             {metrics.get('recall', 0):.4f}")
    print(f"  Accuracy:           {metrics.get('accuracy', 0):.4f}")
    
    if 'confusion_matrix' in metrics:
        cm = metrics['confusion_matrix']
        print(f"\nConfusion Matrix:")
        print(f"  True Positives:     {cm.get('true_positives', 0):,}")
        print(f"  True Negatives:     {cm.get('true_negatives', 0):,}")
        print(f"  False Positives:    {cm.get('false_positives', 0):,}")
        print(f"  False Negatives:    {cm.get('false_negatives', 0):,}")
    
    print(f"\nArea-based Metrics:")
    print(f"  Predicted Area:     {metrics.get('predicted_area_m2', 0)/1e6:.2f} km²")
    print(f"  Ground Truth Area:  {metrics.get('ground_truth_area_m2', 0)/1e6:.2f} km²")
    print(f"  Intersection Area:  {metrics.get('intersection_area_m2', 0)/1e6:.2f} km²")
    print(f"  Area Precision:     {metrics.get('area_precision', 0):.4f}")
    print(f"  Area Recall:        {metrics.get('area_recall', 0):.4f}")
    print(f"  Relative Area Error: {metrics.get('relative_area_error', 0):.4f}")
    
    print("="*50)