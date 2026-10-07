"""
ShelfSense Core — Computer Vision Engine

This package contains the OOP-structured CV pipeline for shelf occupancy
estimation.  The main entry point is `ShelfAnalyzer`, which orchestrates
the preprocessing, dissimilarity computation, and morphological refinement
stages.  An optional `ProductCounter` uses YOLO to count products per zone.

Usage:
    from core.analyzer import ShelfAnalyzer
    from core.product_counter import ProductCounter

    counter  = ProductCounter()
    analyzer = ShelfAnalyzer(product_counter=counter)
    results  = analyzer.analyze_shelf(current_img, reference_img, zones)
"""

from core.analyzer import ShelfAnalyzer
from core.product_counter import ProductCounter

__all__ = ["ShelfAnalyzer", "ProductCounter"]
