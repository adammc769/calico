"""OCR-DOM Coordinate Matching and Weight Calculation.

This module matches OCR text annotations with DOM element coordinates
and assigns weight values based on spatial overlap and text similarity.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class BoundingBox:
    """Normalized bounding box representation."""
    
    x: float
    y: float
    width: float
    height: float
    
    @property
    def x2(self) -> float:
        """Right edge coordinate."""
        return self.x + self.width
    
    @property
    def y2(self) -> float:
        """Bottom edge coordinate."""
        return self.y + self.height
    
    @property
    def center_x(self) -> float:
        """Center X coordinate."""
        return self.x + self.width / 2
    
    @property
    def center_y(self) -> float:
        """Center Y coordinate."""
        return self.y + self.height / 2
    
    @property
    def area(self) -> float:
        """Box area."""
        return self.width * self.height
    
    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> BoundingBox:
        """Create from dict with various formats."""
        if "width" in data and "height" in data:
            return cls(
                x=data.get("x", data.get("left", 0)),
                y=data.get("y", data.get("top", 0)),
                width=data["width"],
                height=data["height"]
            )
        else:
            # Convert from left/top/right/bottom format
            left = data.get("left", data.get("x", 0))
            top = data.get("top", data.get("y", 0))
            right = data.get("right", left)
            bottom = data.get("bottom", top)
            return cls(
                x=left,
                y=top,
                width=right - left,
                height=bottom - top
            )
    
    def intersection_over_union(self, other: BoundingBox) -> float:
        """Calculate IoU (Intersection over Union) with another box."""
        # Calculate intersection
        x_left = max(self.x, other.x)
        y_top = max(self.y, other.y)
        x_right = min(self.x2, other.x2)
        y_bottom = min(self.y2, other.y2)
        
        if x_right < x_left or y_bottom < y_top:
            return 0.0  # No intersection
        
        intersection_area = (x_right - x_left) * (y_bottom - y_top)
        union_area = self.area + other.area - intersection_area
        
        if union_area == 0:
            return 0.0
        
        return intersection_area / union_area
    
    def contains_point(self, x: float, y: float) -> bool:
        """Check if point is inside the box."""
        return self.x <= x <= self.x2 and self.y <= y <= self.y2
    
    def distance_to(self, other: BoundingBox) -> float:
        """Calculate center-to-center distance."""
        dx = self.center_x - other.center_x
        dy = self.center_y - other.center_y
        return (dx * dx + dy * dy) ** 0.5


@dataclass
class OCRDOMMatch:
    """Represents a match between OCR annotation and DOM element."""
    
    dom_selector: str
    dom_bbox: BoundingBox
    dom_text: str
    ocr_text: str
    ocr_bbox: BoundingBox
    ocr_confidence: float
    
    # Calculated weights
    spatial_weight: float = 0.0  # IoU-based spatial overlap
    text_similarity_weight: float = 0.0  # Text similarity score
    confidence_weight: float = 0.0  # OCR confidence
    combined_weight: float = 0.0  # Final combined score
    
    def __post_init__(self):
        """Calculate weights after initialization."""
        self.spatial_weight = self._calculate_spatial_weight()
        self.text_similarity_weight = self._calculate_text_similarity()
        self.confidence_weight = self.ocr_confidence
        self.combined_weight = self._calculate_combined_weight()
    
    def _calculate_spatial_weight(self) -> float:
        """Calculate spatial overlap weight using IoU."""
        iou = self.dom_bbox.intersection_over_union(self.ocr_bbox)
        
        # If low IoU, check if OCR is contained within DOM (common for buttons)
        if iou < 0.3:
            ocr_center_in_dom = self.dom_bbox.contains_point(
                self.ocr_bbox.center_x, 
                self.ocr_bbox.center_y
            )
            if ocr_center_in_dom:
                # OCR text is inside DOM element - good match
                return 0.7
        
        return iou
    
    def _calculate_text_similarity(self) -> float:
        """Calculate text similarity between DOM and OCR text."""
        if not self.dom_text or not self.ocr_text:
            return 0.0
        
        # Normalize texts
        dom_normalized = self.dom_text.lower().strip()
        ocr_normalized = self.ocr_text.lower().strip()
        
        # Exact match
        if dom_normalized == ocr_normalized:
            return 1.0
        
        # Substring match
        if ocr_normalized in dom_normalized or dom_normalized in ocr_normalized:
            return 0.8
        
        # Levenshtein-like similarity (simple version)
        try:
            from difflib import SequenceMatcher
            matcher = SequenceMatcher(None, dom_normalized, ocr_normalized)
            return matcher.ratio()
        except ImportError:
            # Fallback: word overlap
            dom_words = set(dom_normalized.split())
            ocr_words = set(ocr_normalized.split())
            if not dom_words or not ocr_words:
                return 0.0
            overlap = len(dom_words & ocr_words)
            total = len(dom_words | ocr_words)
            return overlap / total if total > 0 else 0.0
    
    def _calculate_combined_weight(self) -> float:
        """Calculate final combined weight."""
        # Weighted combination of all factors
        weights = {
            'spatial': 0.4,  # Spatial overlap is very important
            'text': 0.4,     # Text similarity is very important
            'confidence': 0.2  # OCR confidence matters less if other metrics are good
        }
        
        combined = (
            self.spatial_weight * weights['spatial'] +
            self.text_similarity_weight * weights['text'] +
            self.confidence_weight * weights['confidence']
        )
        
        # Bonus if both spatial and text are high
        if self.spatial_weight > 0.6 and self.text_similarity_weight > 0.6:
            combined = min(1.0, combined * 1.2)
        
        return combined
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "selector": self.dom_selector,
            "dom_text": self.dom_text,
            "ocr_text": self.ocr_text,
            "dom_bbox": {
                "x": self.dom_bbox.x,
                "y": self.dom_bbox.y,
                "width": self.dom_bbox.width,
                "height": self.dom_bbox.height
            },
            "ocr_bbox": {
                "x": self.ocr_bbox.x,
                "y": self.ocr_bbox.y,
                "width": self.ocr_bbox.width,
                "height": self.ocr_bbox.height
            },
            "weights": {
                "spatial": round(self.spatial_weight, 3),
                "text_similarity": round(self.text_similarity_weight, 3),
                "ocr_confidence": round(self.confidence_weight, 3),
                "combined": round(self.combined_weight, 3)
            }
        }


class OCRDOMMatcher:
    """Matches OCR annotations with DOM elements based on coordinates."""
    
    def __init__(self, min_match_threshold: float = 0.3):
        """
        Initialize matcher.
        
        Args:
            min_match_threshold: Minimum combined weight to consider a match valid
        """
        self.min_match_threshold = min_match_threshold
    
    def match_ocr_to_dom(
        self,
        ocr_annotations: List[Dict[str, Any]],
        dom_elements: List[Dict[str, Any]]
    ) -> List[OCRDOMMatch]:
        """
        Match OCR annotations to DOM elements.
        
        Args:
            ocr_annotations: List of OCR annotations with bounding_poly and description
            dom_elements: List of DOM elements with boundingBox, selector, and text
        
        Returns:
            List of matches sorted by combined weight (best first)
        """
        matches: List[OCRDOMMatch] = []
        
        for ocr_ann in ocr_annotations:
            ocr_text = ocr_ann.get("description", "")
            if not ocr_text.strip():
                continue
            
            ocr_bbox = self._parse_ocr_bbox(ocr_ann.get("bounding_poly", []))
            if ocr_bbox is None:
                continue
            
            ocr_confidence = ocr_ann.get("confidence", 1.0)
            
            # Try to match with each DOM element
            for dom_elem in dom_elements:
                dom_bbox_data = dom_elem.get("boundingBox", dom_elem.get("bounding_box"))
                if not dom_bbox_data:
                    continue
                
                try:
                    dom_bbox = BoundingBox.from_dict(dom_bbox_data)
                except (KeyError, TypeError, ValueError) as e:
                    logger.debug(f"Invalid DOM bounding box: {e}")
                    continue
                
                dom_selector = dom_elem.get("selector", dom_elem.get("css_selector", ""))
                dom_text = dom_elem.get("text", dom_elem.get("textContent", ""))
                
                # Create match
                match = OCRDOMMatch(
                    dom_selector=dom_selector,
                    dom_bbox=dom_bbox,
                    dom_text=dom_text,
                    ocr_text=ocr_text,
                    ocr_bbox=ocr_bbox,
                    ocr_confidence=ocr_confidence
                )
                
                # Only include if above threshold
                if match.combined_weight >= self.min_match_threshold:
                    matches.append(match)
        
        # Sort by combined weight (best first)
        matches.sort(key=lambda m: m.combined_weight, reverse=True)
        
        return matches
    
    def _parse_ocr_bbox(self, bounding_poly: List[Dict[str, float]]) -> Optional[BoundingBox]:
        """Parse OCR bounding polygon into bounding box."""
        if not bounding_poly or len(bounding_poly) < 3:
            return None
        
        try:
            # Get min/max coordinates from polygon
            xs = [v.get("x", 0) for v in bounding_poly]
            ys = [v.get("y", 0) for v in bounding_poly]
            
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)
            
            return BoundingBox(
                x=x_min,
                y=y_min,
                width=x_max - x_min,
                height=y_max - y_min
            )
        except (KeyError, TypeError, ValueError) as e:
            logger.debug(f"Failed to parse OCR bounding poly: {e}")
            return None
    
    def get_weighted_selectors(
        self,
        matches: List[OCRDOMMatch],
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get top K selectors with their weights for HuggingFace integration.
        
        Args:
            matches: List of OCR-DOM matches
            top_k: Number of top matches to return
        
        Returns:
            List of dicts with selector, score, textPreview, and contextSnippet
        """
        weighted_selectors = []
        
        for match in matches[:top_k]:
            weighted_selectors.append({
                "selector": match.dom_selector,
                "score": match.combined_weight,
                "label": "ocr_matched",
                "textPreview": match.ocr_text[:50],
                "contextSnippet": match.dom_text[:100]
            })
        
        return weighted_selectors


# Convenience function
def match_ocr_with_dom(
    ocr_result: Dict[str, Any],
    dom_elements: List[Dict[str, Any]],
    min_threshold: float = 0.3
) -> Tuple[List[OCRDOMMatch], List[Dict[str, Any]]]:
    """
    Convenience function to match OCR with DOM and get weighted selectors.
    
    Args:
        ocr_result: OCR result dict with 'annotations' key
        dom_elements: List of DOM elements with bounding boxes
        min_threshold: Minimum match threshold
    
    Returns:
        Tuple of (matches, weighted_selectors)
    """
    matcher = OCRDOMMatcher(min_match_threshold=min_threshold)
    
    annotations = ocr_result.get("annotations", [])
    matches = matcher.match_ocr_to_dom(annotations, dom_elements)
    weighted_selectors = matcher.get_weighted_selectors(matches)
    
    return matches, weighted_selectors
