"""
Annotation correction functions.

Each function takes a list of raw Label Studio result items and returns a
corrected copy — original list is never mutated.

Usage:
    original_result = annotation["result"]
    corrected_result = drop_nested_same_class(original_result)
    # then PATCH /api/annotations/{id}/ with corrected_result
"""

from __future__ import annotations
from typing import Callable
from .geometry import box_from_result_item, aspect_ratio, area_pct, containment, iou


def drop_regions_by_predicate(
    result: list[dict],
    predicate: Callable[[dict], bool],
) -> list[dict]:
    """
    Remove all result items for which `predicate(item)` returns True.
    Non-rectanglelabels items (relations, keypointlabels, etc.) are always kept.

    Args:
        result:    Raw LS result list.
        predicate: Function that takes a raw result item and returns True to drop it.

    Returns:
        New result list with matching items removed.
    """
    return [item for item in result if not predicate(item)]


def drop_extreme_aspect_ratio(
    result: list[dict],
    threshold: float = 20.0,
) -> list[dict]:
    """
    Remove all rectanglelabels boxes whose aspect ratio >= `threshold`.

    Args:
        threshold: Aspect ratio cutoff (default 20 = 20:1 sliver).

    Returns:
        Corrected result list.
    """
    def _should_drop(item: dict) -> bool:
        box = box_from_result_item(item)
        return box is not None and aspect_ratio(box) >= threshold

    return drop_regions_by_predicate(result, _should_drop)


def drop_tiny_boxes(
    result: list[dict],
    threshold: float = 0.003,
) -> list[dict]:
    """
    Remove all rectanglelabels boxes whose area < `threshold` (fraction of image).

    Args:
        threshold: Area cutoff (default 0.003 = 0.3% of image).

    Returns:
        Corrected result list.
    """
    def _should_drop(item: dict) -> bool:
        box = box_from_result_item(item)
        return box is not None and area_pct(box) < threshold

    return drop_regions_by_predicate(result, _should_drop)


def drop_nested_same_class(
    result: list[dict],
    threshold: float = 0.85,
    keep: str = "outer",
) -> list[dict]:
    """
    For each pair of same-class boxes where one contains the other by >= `threshold`,
    remove the unwanted box.

    Args:
        threshold: Containment fraction to consider a box "nested" (default 0.85).
        keep:      Which box to keep: "outer" (default) or "inner".
                   "outer" = keep the larger enclosing box, drop the inner one.
                   "inner" = keep the smaller contained box, drop the outer one.

    Returns:
        Corrected result list.

    Note:
        When multiple nested pairs exist, the function iterates until stable
        (no more nested pairs remain).
    """
    if keep not in ("outer", "inner"):
        raise ValueError('keep must be "outer" or "inner"')

    items = list(result)

    changed = True
    while changed:
        changed = False
        boxes = [box_from_result_item(item) for item in items]
        to_drop = set()

        for i, box_i in enumerate(boxes):
            if box_i is None or i in to_drop:
                continue
            for j, box_j in enumerate(boxes):
                if box_j is None or j in to_drop or i == j:
                    continue
                if box_i["label"] != box_j["label"]:
                    continue
                # Check if i is contained within j
                if containment(box_i, box_j) >= threshold:
                    # box_i is the inner, box_j is the outer
                    if keep == "outer":
                        to_drop.add(i)  # drop inner
                    else:
                        to_drop.add(j)  # drop outer
                    changed = True

        if to_drop:
            items = [item for k, item in enumerate(items) if k not in to_drop]

    return items


def drop_cross_class_containment(
    result: list[dict],
    threshold: float = 0.70,
    drop: str = "inner",
) -> list[dict]:
    """
    For each pair of different-class boxes where one contains the other by >= `threshold`,
    remove the specified box.

    Args:
        threshold: Containment fraction cutoff (default 0.70).
        drop:      Which box to remove: "inner" (default, removes the contained box)
                   or "outer" (removes the containing box).

    Returns:
        Corrected result list.
    """
    if drop not in ("inner", "outer"):
        raise ValueError('drop must be "inner" or "outer"')

    items = list(result)
    changed = True

    while changed:
        changed = False
        boxes = [box_from_result_item(item) for item in items]
        to_drop = set()

        for i, box_i in enumerate(boxes):
            if box_i is None or i in to_drop:
                continue
            for j, box_j in enumerate(boxes):
                if box_j is None or j in to_drop or i == j:
                    continue
                if box_i["label"] == box_j["label"]:
                    continue
                # box_i is inner candidate, box_j is outer candidate
                if containment(box_i, box_j) >= threshold:
                    if drop == "inner":
                        to_drop.add(i)
                    else:
                        to_drop.add(j)
                    changed = True

        if to_drop:
            items = [item for k, item in enumerate(items) if k not in to_drop]

    return items


def drop_near_duplicates(
    result: list[dict],
    iou_threshold: float = 0.85,
) -> list[dict]:
    """
    For each pair of same-class boxes with IoU >= `iou_threshold`,
    keep the larger box and drop the smaller one.

    Args:
        iou_threshold: IoU cutoff to consider two boxes near-duplicates (default 0.85).

    Returns:
        Corrected result list.
    """
    items = list(result)
    changed = True

    while changed:
        changed = False
        boxes = [box_from_result_item(item) for item in items]
        to_drop = set()

        for i, box_i in enumerate(boxes):
            if box_i is None or i in to_drop:
                continue
            for j, box_j in enumerate(boxes):
                if box_j is None or j in to_drop or j <= i:
                    continue
                if box_i["label"] != box_j["label"]:
                    continue
                if iou(box_i, box_j) >= iou_threshold:
                    # Drop the smaller box
                    area_i = box_i["width"] * box_i["height"]
                    area_j = box_j["width"] * box_j["height"]
                    to_drop.add(i if area_i <= area_j else j)
                    changed = True

        if to_drop:
            items = [item for k, item in enumerate(items) if k not in to_drop]

    return items


# ------------------------------------------------------------------
# Composite correction: apply all rules in sequence
# ------------------------------------------------------------------

def auto_correct(
    result: list[dict],
    drop_ar_threshold: float = 20.0,
    drop_tiny_threshold: float = 0.003,
    nesting_threshold: float = 0.85,
    cross_class_threshold: float = 0.70,
) -> tuple[list[dict], dict[str, int]]:
    """
    Apply all correction rules in sequence and return the corrected result
    plus a summary of how many regions were removed by each rule.

    Rule application order (same as empirically validated order):
        1. drop_cross_class_containment  (most unambiguous)
        2. drop_nested_same_class
        3. drop_near_duplicates
        4. drop_tiny_boxes
        5. drop_extreme_aspect_ratio

    Returns:
        (corrected_result, stats) where stats = {rule_name: n_dropped}
    """
    stats: dict[str, int] = {}
    current = list(result)

    def _apply(name: str, fn, *args, **kwargs):
        before = len(current)
        corrected = fn(current, *args, **kwargs)
        stats[name] = before - len(corrected)
        current[:] = corrected

    _apply("cross_class_containment", drop_cross_class_containment, threshold=cross_class_threshold)
    _apply("nested_same_class",        drop_nested_same_class,        threshold=nesting_threshold)
    _apply("near_duplicates",          drop_near_duplicates)
    _apply("tiny_boxes",               drop_tiny_boxes,               threshold=drop_tiny_threshold)
    _apply("extreme_aspect_ratio",     drop_extreme_aspect_ratio,     threshold=drop_ar_threshold)

    return current, stats
