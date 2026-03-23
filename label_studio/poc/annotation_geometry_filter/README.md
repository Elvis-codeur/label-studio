# PoC: Annotation Geometry Filter & Bulk Correction

This is a proof-of-concept for a [proposed Label Studio feature](https://github.com/HumanSignal/label-studio/issues/TODO):
**filtering tasks by annotation geometry patterns and applying bulk corrections directly from the Data Manager.**

---

## The Problem

Label Studio's Data Manager can filter tasks by metadata fields and label names,
but not by the geometric properties of annotation regions.

When working with model-generated pre-annotations (predictions), systematic
geometry errors appear at scale. In one project (2,379 tasks, 38,784 regions):

| Issue | Count | % of tasks affected |
|---|---|---|
| High region density (> 20 boxes/task) | 15,837 regions | 99% of tasks |
| Tiny boxes (area < 0.3% of image)     | 11,661 regions | 86% of tasks |
| Nested same-class boxes               |  8,982 regions | 78% of tasks |
| Extreme aspect ratio (> 20:1 slivers) |  7,375 regions | 67% of tasks |
| Cross-class containment               |  1,893 regions | 42% of tasks |

**99% of 2,379 pre-annotated tasks had at least one geometric quality issue.**

Currently there is no way to identify or batch-fix these in the Label Studio UI.
The only workaround is scripting against the REST API — which is what this PoC implements.

Applying the geometric correction rules to 2,238 pseudo-labeled tasks and retraining
improved model mAP50 from **0.874 → 0.955** (+8.1 pp) and mAP50-95 from **0.686 → 0.900**
(+21.4 pp). Cleaning annotations before training matters.

---

## Structure

```
annotation_geometry_filter/
├── geometry.py       # Pure geometric primitives (aspect_ratio, iou, containment, ...)
├── predicates.py     # Task-level predicates (has_nested_same_class, has_tiny_box, ...)
├── corrections.py    # Correction functions (drop_nested_same_class, auto_correct, ...)
├── ls_api.py         # Thin LS REST API client (filter_tasks_by_geometry, bulk_auto_correct)
└── example_usage.py  # End-to-end example
```

---

## Requirements

```
pip install requests
```

No Label Studio SDK dependency. Works against any Label Studio instance (Community or Enterprise).

---

## Quick Start

```bash
export LS_URL=http://localhost:8080
export LS_API_KEY=your-personal-access-token
export LS_PROJECT_ID=1

cd label_studio/poc/annotation_geometry_filter
python example_usage.py
```

---

## API Reference

### geometry.py

| Function | Description |
|---|---|
| `box_from_result_item(item)` | Extract a Box dict from a raw LS result item |
| `aspect_ratio(box)` | Width/height ratio, always ≥ 1 |
| `area_pct(box)` | Box area as fraction of image (0–1) |
| `iou(a, b)` | Intersection over Union (0–1) |
| `containment(inner, outer)` | Fraction of `inner` covered by `outer` (0–1) |
| `is_contained(inner, outer, threshold)` | Boolean containment test |

### predicates.py

Each predicate takes a raw LS `result` list and returns `bool`.

| Function | Default threshold | Detects |
|---|---|---|
| `has_extreme_aspect_ratio(result)` | AR ≥ 20 | Sliver/artifact boxes |
| `has_tiny_box(result)` | area < 0.3% | Sub-pixel noise detections |
| `has_nested_same_class(result)` | containment ≥ 85% | Redundant same-class nesting |
| `has_cross_class_containment(result)` | containment ≥ 70% | Cross-class containment violations |
| `has_high_density(result)` | > 20 regions | Over-segmented tasks |
| `has_near_duplicate(result)` | IoU ≥ 85% | Near-duplicate boxes |
| `audit(result)` | — | Run all predicates, return dict |

### corrections.py

Each correction function takes a `result` list and returns a corrected copy (immutable).

| Function | Description |
|---|---|
| `drop_extreme_aspect_ratio(result)` | Remove sliver boxes |
| `drop_tiny_boxes(result)` | Remove sub-pixel boxes |
| `drop_nested_same_class(result, keep="outer")` | Remove nested duplicates |
| `drop_cross_class_containment(result, drop="inner")` | Remove contained cross-class boxes |
| `drop_near_duplicates(result)` | Remove near-duplicate boxes |
| `auto_correct(result)` | Apply all rules in sequence, return (corrected, stats) |

### ls_api.py — LSClient

```python
client = LSClient(url="http://localhost:8080", api_key="token")
```

| Method | Description |
|---|---|
| `export_annotations(project_id)` | Export all tasks + annotations |
| `get_annotation(annotation_id)` | Fetch single annotation |
| `update_annotation(annotation_id, result)` | PATCH annotation result |
| `filter_tasks_by_geometry(project_id, predicate)` | Yield matching (task_id, ann_id, result) |
| `audit_project(project_id)` | Run all predicates on all annotations |
| `bulk_auto_correct(project_id, dry_run=True)` | Apply all corrections, return report |

---

## Example: filter + correct in 10 lines

```python
from ls_api import LSClient
from predicates import has_nested_same_class
from corrections import drop_nested_same_class

client = LSClient(url="http://localhost:8080", api_key="my-token")

for task_id, ann_id, result in client.filter_tasks_by_geometry(
    project_id=1,
    predicate=has_nested_same_class,
):
    corrected = drop_nested_same_class(result, keep="outer")
    client.update_annotation(ann_id, corrected)
    print(f"task {task_id}: {len(result)} → {len(corrected)} regions")
```

---

## Why this belongs in Label Studio

The geometric primitives (`iou`, `containment`, `aspect_ratio`) are already computed
inside the annotation editor for display purposes. Exposing them as Data Manager filter
predicates would let annotators and reviewers:

1. **Find** affected tasks without scripting
2. **Inspect** them interactively before correcting
3. **Bulk-apply** corrections with a single action

This PoC demonstrates the predicate logic and API interaction pattern that a native
implementation could build on.
