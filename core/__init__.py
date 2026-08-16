"""
ShelfSense Core — Computer Vision Engine

This package contains the OOP-structured CV pipeline for shelf occupancy
estimation.  The main entry point is `ShelfAnalyzer`, which orchestrates
the preprocessing, dissimilarity computation, and morphological refinement
stages.

Usage:
    from core.analyzer import ShelfAnalyzer
    analyzer = ShelfAnalyzer()
    results  = analyzer.analyze_shelf(current_img, reference_img, zones)
"""

from core.analyzer import ShelfAnalyzer

__all__ = ["ShelfAnalyzer"]
