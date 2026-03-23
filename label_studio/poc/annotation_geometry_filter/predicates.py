"""
Task-level geometry predicates.

Each predicate takes a list of raw Label Studio result items (from one annotation)
and returns True if the task matches the pattern.

Usage:
    result = annotation["result"]  # list of LS result items

    if has_nested_same_class(result):
        # this task has at least one same-class nesting issue
        ...
"""

from __future__ import annotations
from itertools import combinations
from .geometry import box_from_result_item, aspect_ratio, area_pct, iou, containment


def _boxes(result: list[dict]) -> list[dict]:
    """Extract all rectanglelabels boxes from a result list."""
    return [b for item in result if (b := box_from_result_item(item)) is not None]


def has_extreme_aspect_ratio(result: list[dict], threshold: float = 20.0) -> bool:
    """
    True if any box has aspect ratio >= `threshold`.
    Detects sliver/artifact boxes (e.g. thin horizontal or vertical strips).

    Default threshold 20 = box is 20x wider (or taller) than its other dimension.
    """
    return any(aspect_ratio(b) >= threshold for b in _boxes(result))


def has_tiny_box(result: list[dict], threshold: float = 0.003) -> bool:
    """
    True if any box covers less than `threshold` fraction of the image area.
    Detects sub-pixel noise detections.

    Default threshold 0.003 = box covers less than 0.3% of the image.
    """
    return any(area_pct(b) < threshold for b in _boxes(result))


def has_nested_same_class(result: list[dict], threshold: float = 0.85) -> bool:
    """
    True if any box of class X is contained within another box of class X
    by at least `threshold` fraction of its area.

    Detects redundant same-class nesting (e.g. a 'text' block inside a larger 'text' block).
    """
    boxes = _boxes(result)
    for i, a in enumerate(boxes):
        for j, b in enumerate(boxes):
            if i == j:
                continue
            if a["label"] != b["label"]:
                continue
            if containment(a, b) >= threshold:
                return True
    return False


def has_cross_class_containment(result: list[dict], threshold: float = 0.70) -> bool:
    """
    True if any box of class A is contained within a box of a different class B
    by at least `threshold` fraction of its area.

    Detects cross-class nesting violations (e.g. a 'text' region inside a 'figure' region).
    """
    boxes = _boxes(result)
    for i, inner in enumerate(boxes):
        for j, outer in enumerate(boxes):
            if i == j:
                continue
            if inner["label"] == outer["label"]:
                continue
            if containment(inner, outer) >= threshold:
                return True
    return False


def has_high_density(result: list[dict], threshold: int = 20) -> bool:
    """
    True if the annotation contains more than `threshold` regions.
    Detects over-segmented tasks where the model annotated at element level
    instead of block level.
    """
    return len(_boxes(result)) > threshold


def has_near_duplicate(result: list[dict], iou_threshold: float = 0.85) -> bool:
    """
    True if any two boxes of the same class have IoU >= `iou_threshold`.
    Detects near-duplicate predictions (slightly offset copies of the same region).
    """
    boxes = _boxes(result)
    for a, b in combinations(boxes, 2):
        if a["label"] == b["label"] and iou(a, b) >= iou_threshold:
            return True
    return False


def has_full_page_box(result: list[dict], threshold: float = 0.75) -> bool:
    """
    True if any box covers more than `threshold` fraction of the image area.
    Detects over-coarse annotations that span nearly the entire page.
    """
    return any(area_pct(b) > threshold for b in _boxes(result))


# ------------------------------------------------------------------
# Composite predicate: run all checks and return a summary dict
# ------------------------------------------------------------------

def audit(result: list[dict]) -> dict[str, bool]:
    """
    Run all geometry predicates on a result list.
    Returns a dict of {issue_name: bool}.

    Example:
        issues = audit(annotation["result"])
        if any(issues.values()):
            print("Task has geometry issues:", [k for k, v in issues.items() if v])
    """
    return {
        "extreme_aspect_ratio":     has_extreme_aspect_ratio(result),
        "tiny_box":                 has_tiny_box(result),
        "nested_same_class":        has_nested_same_class(result),
        "cross_class_containment":  has_cross_class_containment(result),
        "high_density":             has_high_density(result),
        "near_duplicate":           has_near_duplicate(result),
        "full_page_box":            has_full_page_box(result),
    }
