"""
Test metrics calculation functionality.
"""

import pytest
import numpy as np
import tempfile
import os
import sys

# Add common modules to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'project', 'common'))

from metrics import (
    calculate_jaccard_index, 
    calculate_f1_score, 
    calculate_confusion_matrix,
    calculate_accuracy,
    evaluate_change_detection
)
import rasterio
from rasterio.transform import from_bounds


def create_binary_mask(data, output_path=None):
    """Create a binary mask raster from numpy array."""
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.tif')
    
    height, width = data.shape
    
    profile = {
        'driver': 'GTiff',
        'dtype': 'uint8',
        'count': 1,
        'width': width,
        'height': height,
        'crs': 'EPSG:4326',
        'transform': from_bounds(0, 0, 1, 1, width, height)
    }
    
    with rasterio.open(output_path, 'w', **profile) as dst:
        dst.write(data.astype(np.uint8), 1)
    
    return output_path


def test_perfect_match():
    """Test metrics with perfect prediction."""
    # Create identical masks
    mask_data = np.array([
        [0, 0, 1, 1],
        [0, 1, 1, 0],
        [1, 1, 0, 0],
        [1, 0, 0, 1]
    ])
    
    pred_path = create_binary_mask(mask_data)
    gt_path = create_binary_mask(mask_data)
    
    try:
        # Test Jaccard index
        jaccard = calculate_jaccard_index(pred_path, gt_path)
        assert jaccard == 1.0
        
        # Test F1 score
        f1, precision, recall = calculate_f1_score(pred_path, gt_path)
        assert f1 == 1.0
        assert precision == 1.0
        assert recall == 1.0
        
        # Test accuracy
        accuracy = calculate_accuracy(pred_path, gt_path)
        assert accuracy == 1.0
        
        # Test confusion matrix
        cm = calculate_confusion_matrix(pred_path, gt_path)
        assert cm['true_positives'] == 8  # Number of 1s
        assert cm['true_negatives'] == 8   # Number of 0s
        assert cm['false_positives'] == 0
        assert cm['false_negatives'] == 0
        
    finally:
        os.unlink(pred_path)
        os.unlink(gt_path)


def test_no_overlap():
    """Test metrics with no overlap between prediction and ground truth."""
    # Create complementary masks
    pred_data = np.array([
        [1, 1, 0, 0],
        [1, 1, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0]
    ])
    
    gt_data = np.array([
        [0, 0, 1, 1],
        [0, 0, 1, 1],
        [1, 1, 1, 1],
        [1, 1, 1, 1]
    ])
    
    pred_path = create_binary_mask(pred_data)
    gt_path = create_binary_mask(gt_data)
    
    try:
        # Test Jaccard index
        jaccard = calculate_jaccard_index(pred_path, gt_path)
        assert jaccard == 0.0
        
        # Test F1 score
        f1, precision, recall = calculate_f1_score(pred_path, gt_path)
        assert f1 == 0.0
        assert precision == 0.0
        assert recall == 0.0
        
        # Test confusion matrix
        cm = calculate_confusion_matrix(pred_path, gt_path)
        assert cm['true_positives'] == 0
        assert cm['false_positives'] == 4  # pred=1, gt=0
        assert cm['false_negatives'] == 10  # pred=0, gt=1
        assert cm['true_negatives'] == 2   # pred=0, gt=0
        
    finally:
        os.unlink(pred_path)
        os.unlink(gt_path)


def test_partial_overlap():
    """Test metrics with partial overlap."""
    pred_data = np.array([
        [1, 1, 0, 0],
        [1, 1, 1, 0],
        [0, 1, 1, 0],
        [0, 0, 0, 0]
    ])
    
    gt_data = np.array([
        [1, 0, 0, 0],
        [1, 1, 0, 0],
        [1, 1, 1, 1],
        [0, 0, 1, 1]
    ])
    
    pred_path = create_binary_mask(pred_data)
    gt_path = create_binary_mask(gt_data)
    
    try:
        # Calculate expected values manually
        # TP: positions where both pred=1 and gt=1
        tp = np.sum((pred_data == 1) & (gt_data == 1))  # Should be 4
        
        # FP: positions where pred=1 and gt=0
        fp = np.sum((pred_data == 1) & (gt_data == 0))  # Should be 3
        
        # FN: positions where pred=0 and gt=1
        fn = np.sum((pred_data == 0) & (gt_data == 1))  # Should be 5
        
        # TN: positions where pred=0 and gt=0
        tn = np.sum((pred_data == 0) & (gt_data == 0))  # Should be 4
        
        # Test confusion matrix
        cm = calculate_confusion_matrix(pred_path, gt_path)
        assert cm['true_positives'] == tp
        assert cm['false_positives'] == fp
        assert cm['false_negatives'] == fn
        assert cm['true_negatives'] == tn
        
        # Test Jaccard index: TP / (TP + FP + FN)
        expected_jaccard = tp / (tp + fp + fn)
        jaccard = calculate_jaccard_index(pred_path, gt_path)
        assert abs(jaccard - expected_jaccard) < 1e-6
        
        # Test F1 score
        expected_precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        expected_recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        expected_f1 = 2 * (expected_precision * expected_recall) / (expected_precision + expected_recall) if (expected_precision + expected_recall) > 0 else 0
        
        f1, precision, recall = calculate_f1_score(pred_path, gt_path)
        assert abs(f1 - expected_f1) < 1e-6
        assert abs(precision - expected_precision) < 1e-6
        assert abs(recall - expected_recall) < 1e-6
        
        # Test accuracy
        expected_accuracy = (tp + tn) / (tp + tn + fp + fn)
        accuracy = calculate_accuracy(pred_path, gt_path)
        assert abs(accuracy - expected_accuracy) < 1e-6
        
    finally:
        os.unlink(pred_path)
        os.unlink(gt_path)


def test_empty_masks():
    """Test metrics with empty masks."""
    # Both masks empty
    empty_data = np.zeros((4, 4))
    
    pred_path = create_binary_mask(empty_data)
    gt_path = create_binary_mask(empty_data)
    
    try:
        jaccard = calculate_jaccard_index(pred_path, gt_path)
        assert jaccard == 1.0  # Empty intersection and union should give 1.0
        
        f1, precision, recall = calculate_f1_score(pred_path, gt_path)
        assert f1 == 0.0  # No positive predictions or ground truth
        assert precision == 0.0
        assert recall == 0.0
        
    finally:
        os.unlink(pred_path)
        os.unlink(gt_path)


def test_comprehensive_evaluation():
    """Test comprehensive evaluation function."""
    pred_data = np.array([
        [1, 1, 0, 0],
        [1, 0, 1, 0],
        [0, 1, 1, 0],
        [0, 0, 0, 1]
    ])
    
    gt_data = np.array([
        [1, 0, 0, 0],
        [1, 1, 0, 0],
        [1, 1, 1, 1],
        [0, 0, 1, 1]
    ])
    
    pred_path = create_binary_mask(pred_data)
    gt_path = create_binary_mask(gt_path)
    
    try:
        # Test with pixel size
        pixel_size_m2 = 100.0  # 100 m² per pixel
        
        metrics = evaluate_change_detection(pred_path, gt_path, pixel_size_m2)
        
        # Check that all expected metrics are present
        expected_keys = [
            'jaccard_index', 'f1_score', 'precision', 'recall', 'accuracy',
            'confusion_matrix', 'predicted_area_m2', 'ground_truth_area_m2',
            'intersection_area_m2', 'area_precision', 'area_recall', 'relative_area_error'
        ]
        
        for key in expected_keys:
            assert key in metrics
        
        # Check area calculations
        pred_pixels = np.sum(pred_data)
        gt_pixels = np.sum(gt_data)
        intersection_pixels = np.sum((pred_data == 1) & (gt_data == 1))
        
        assert metrics['predicted_area_m2'] == pred_pixels * pixel_size_m2
        assert metrics['ground_truth_area_m2'] == gt_pixels * pixel_size_m2
        assert metrics['intersection_area_m2'] == intersection_pixels * pixel_size_m2
        
        # Check area-based metrics
        expected_area_precision = intersection_pixels / pred_pixels if pred_pixels > 0 else 0
        expected_area_recall = intersection_pixels / gt_pixels if gt_pixels > 0 else 0
        
        assert abs(metrics['area_precision'] - expected_area_precision) < 1e-6
        assert abs(metrics['area_recall'] - expected_area_recall) < 1e-6
        
    finally:
        os.unlink(pred_path)
        os.unlink(gt_path)


def test_mismatched_dimensions():
    """Test error handling for mismatched dimensions."""
    pred_data = np.ones((4, 4))
    gt_data = np.ones((3, 3))  # Different size
    
    pred_path = create_binary_mask(pred_data)
    gt_path = create_binary_mask(gt_data)
    
    try:
        with pytest.raises(ValueError):
            calculate_jaccard_index(pred_path, gt_path)
            
    finally:
        os.unlink(pred_path)
        os.unlink(gt_path)


if __name__ == '__main__':
    # Run tests
    test_perfect_match()
    test_no_overlap()
    test_partial_overlap()
    test_empty_masks()
    test_comprehensive_evaluation()
    test_mismatched_dimensions()
    
    print("All metrics tests passed!")