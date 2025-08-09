#!/usr/bin/env python3
"""
Jaccard Index (IoU) calculation for change detection evaluation.

Usage: python jaccard.py --pred prediction.tif --gt ground_truth.tif
"""

import argparse
import sys
import os
from pathlib import Path

# Add common modules to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'common'))

from metrics import evaluate_change_detection, print_evaluation_report


def main():
    parser = argparse.ArgumentParser(
        description='Calculate Jaccard Index and other metrics for change detection evaluation'
    )
    
    parser.add_argument('--pred', required=True, 
                       help='Path to predicted binary mask (GeoTIFF)')
    parser.add_argument('--gt', required=True,
                       help='Path to ground truth binary mask (GeoTIFF)')
    parser.add_argument('--pixel-size', type=float,
                       help='Pixel area in square meters (auto-calculated if not provided)')
    parser.add_argument('--output', 
                       help='Output JSON file for detailed metrics')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Only output the Jaccard index value')
    
    args = parser.parse_args()
    
    # Validate input files
    if not os.path.exists(args.pred):
        print(f"Error: Prediction file not found: {args.pred}", file=sys.stderr)
        sys.exit(1)
    
    if not os.path.exists(args.gt):
        print(f"Error: Ground truth file not found: {args.gt}", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Calculate metrics
        metrics = evaluate_change_detection(args.pred, args.gt, args.pixel_size)
        
        if not metrics:
            print("Error: Failed to calculate metrics", file=sys.stderr)
            sys.exit(1)
        
        if args.quiet:
            # Only output Jaccard index
            print(f"{metrics['jaccard_index']:.6f}")
        else:
            # Print detailed report
            print_evaluation_report(metrics)
        
        # Save to JSON if requested
        if args.output:
            import json
            os.makedirs(os.path.dirname(args.output), exist_ok=True)
            with open(args.output, 'w') as f:
                json.dump(metrics, f, indent=2)
            
            if not args.quiet:
                print(f"\nDetailed metrics saved to: {args.output}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()