"""
Pure geometric primitives for Label Studio rectanglelabels result items.

All functions operate on a "box" dict extracted from a rectanglelabels result item:
    {
        "x":      float,   # left edge,  0–100 (% of image width)
        "y":      float,   # top edge,   0–100 (% of image height)
        "width":  float,   # box width,  0–100
        "height": float,   # box height, 0–100
        "label":  str,     # class name (first element of rectanglelabels list)
    }

Use `box_from_result_item()` to extract this dict from a raw LS result item.
"""

from __future__ import annotations
from typing import TypedDict


class Box(TypedDict):
    x: float
    y: float
    width: float
    height: float
    label: str


def box_from_result_item(item: dict) -> Box | None:
    """
    Extract a Box from a raw Label Studio result item.
    Returns None if the item is not a rectanglelabels region.
    """
    if item.get("type") != "rectanglelabels":
        return None
    v = item["value"]
    labels = v.get("rectanglelabels", [])
    return Box(
        x=v["x"],
        y=v["y"],
        width=v["width"],
        height=v["height"],
        label=labels[0] if labels else "",
    )


def to_xyxy(box: Box) -> tuple[float, float, float, float]:
    """Convert (x, y, w, h) percentage format to (x1, y1, x2, y2)."""
    return (
        box["x"],
        box["y"],
        box["x"] + box["width"],
        box["y"] + box["height"],
    )


def aspect_ratio(box: Box) -> float:
    """
    Width-to-height ratio, always >= 1 (portrait boxes are inverted).
    A value of 20 means the box is 20x wider (or taller) than its other dimension.
    """
    w = box["width"]
    h = box["height"]
    if h == 0:
        return float("inf")
    r = w / h
    return r if r >= 1 else 1 / r


def area_pct(box: Box) -> float:
    """
    Box area as a fraction of the full image area (0–1).
    Example: 0.003 means the box covers 0.3% of the image.
    """
    return (box["width"] * box["height"]) / 10_000.0


def intersection_area(a: Box, b: Box) -> float:
    """Area of the intersection rectangle between two boxes (in % units squared)."""
    ax1, ay1, ax2, ay2 = to_xyxy(a)
    bx1, by1, bx2, by2 = to_xyxy(b)
    ix = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    iy = max(0.0, min(ay2, by2) - max(ay1, by1))
    return ix * iy


def iou(a: Box, b: Box) -> float:
    """
    Intersection over Union (Jaccard index), 0–1.
    1.0 = identical boxes, 0.0 = no overlap.
    """
    inter = intersection_area(a, b)
    if inter == 0:
        return 0.0
    area_a = a["width"] * a["height"]
    area_b = b["width"] * b["height"]
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def containment(inner: Box, outer: Box) -> float:
    """
    Fraction of `inner` covered by `outer` (0–1).
    1.0 means `inner` is fully inside `outer`.
    Used to detect nesting: containment(small, large) >= 0.85 → small is nested in large.
    """
    inner_area = inner["width"] * inner["height"]
    if inner_area == 0:
        return 0.0
    return intersection_area(inner, outer) / inner_area


def is_contained(inner: Box, outer: Box, threshold: float = 0.85) -> bool:
    """Return True if `inner` is contained within `outer` by at least `threshold`."""
    return containment(inner, outer) >= threshold
