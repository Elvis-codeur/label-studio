# Spec — Idea 1: Annotation Geometry Filter + Bulk Correction

**Branch:** `feature/annotation-geometry-filter`
**Docker mode:** Phase 1 → `backend-only` · Phase 2–3 → `full`
**Status:** not started

---

## Goal

Allow users to filter tasks in the Data Manager based on geometric properties of their
annotation regions, and bulk-correct the matching tasks.

---

## Phase 1 — Backend geometry predicates + filter API

### New file: `label_studio/data_manager/geometry.py`

Create this module with the geometry primitives. All coordinates are in Label Studio
percentage format (x, y, width, height in [0, 100]).

```python
def aspect_ratio(value: dict) -> float:
    """value = region['value']. Returns width/height, inf if height==0."""

def area_pct(value: dict) -> float:
    """Returns (width * height) / 10000. Fraction of image area [0,1]."""

def iou(a: dict, b: dict) -> float:
    """Intersection over Union of two value dicts. [0,1]."""

def containment(inner: dict, outer: dict) -> float:
    """Fraction of inner's area that falls inside outer. [0,1]."""

def contains(outer: dict, inner: dict, threshold: float = 0.70) -> bool:
    """True if outer contains inner by at least threshold."""
```

### New file: `label_studio/data_manager/annotation_filters.py`

Functions that take a task's full annotation result list and return True/False.
These are called in a Python-side post-filter after the main Django ORM query.

```python
def has_extreme_aspect_ratio(result: list, threshold: float = 20.0) -> bool:
    """True if any rectanglelabels region has aspect_ratio > threshold."""

def has_tiny_box(result: list, threshold: float = 0.003) -> bool:
    """True if any region has area_pct < threshold."""

def has_nested_same_class(result: list, containment_threshold: float = 0.70) -> bool:
    """True if any two same-label regions where one contains the other."""

def has_cross_class_containment(result: list, containment_threshold: float = 0.70) -> bool:
    """True if any region of label A contains a region of label B (A != B)."""

def has_high_region_count(result: list, threshold: int = 20) -> bool:
    """True if the annotation has more than `threshold` regions."""

def has_near_duplicate(result: list, iou_threshold: float = 0.80) -> bool:
    """True if any two same-label regions have IoU > iou_threshold."""
```

### Changes to `label_studio/data_manager/managers/task.py`

Add a new filter group `annotation_geometry` to `filter_tasks()`. Because geometry
predicates require iterating over JSON result arrays (not pure SQL), use a two-step
approach:

1. Run the existing ORM filter to get candidate tasks
2. For geometry predicates, post-filter in Python using `annotation_filters.py`

```python
# In filter_tasks(), add handling for filter ids starting with "filter:tasks:annotations:geometry:"
GEOMETRY_FILTER_PREFIX = "filter:tasks:annotations:geometry:"

if filter_id.startswith(GEOMETRY_FILTER_PREFIX):
    predicate_name = filter_id.removeprefix(GEOMETRY_FILTER_PREFIX)
    threshold = filter_value  # numeric threshold from the filter
    # Post-filter: load annotations for candidate tasks and apply predicate
    tasks = _apply_geometry_postfilter(tasks, predicate_name, threshold)
```

### New API endpoint: `POST /api/dm/actions/bulk-geometry-correct`

Request body:
```json
{
  "project": 3,
  "task_ids": [101, 102, 103],
  "action": "drop_regions_matching",
  "predicate": "extreme_aspect_ratio",
  "threshold": 20.0,
  "keep": "outer"
}
```

Actions:
- `drop_regions_matching`: delete all regions where predicate(region) is True
- `resolve_nesting`: for nested same-class pairs, keep `outer` or `inner` (configurable)

Response: `{ "tasks_modified": N, "regions_deleted": M }`

The endpoint reads each task's latest annotation, applies the correction to the
`result` array in Python, then writes back via `annotation.result = corrected_result`.

### Register new filter columns in `label_studio/data_manager/prepare_params.py`

```python
# Add to the columns list:
{
    "id": "filter:tasks:annotations:geometry:extreme_aspect_ratio",
    "title": "Any region: aspect ratio > N",
    "type": "Number",
    "target": "tasks",
    "operators": ["greater"],
    "default_value": 20.0,
},
{
    "id": "filter:tasks:annotations:geometry:tiny_box",
    "title": "Any region: area < N% of image",
    "type": "Number",
    "target": "tasks",
    "operators": ["less"],
    "default_value": 0.3,
},
{
    "id": "filter:tasks:annotations:geometry:nested_same_class",
    "title": "Has nested same-class boxes",
    "type": "Boolean",
    "target": "tasks",
    "operators": ["equal"],
},
{
    "id": "filter:tasks:annotations:geometry:cross_class_containment",
    "title": "Has cross-class containment",
    "type": "Boolean",
    "target": "tasks",
    "operators": ["equal"],
},
{
    "id": "filter:tasks:annotations:geometry:region_count",
    "title": "Region count > N",
    "type": "Number",
    "target": "tasks",
    "operators": ["greater", "less"],
},
```

---

## Phase 2 — Frontend filter panel UI

**Docker mode:** `full` required (modifies `web/libs/datamanager/`)

### Changes to `web/libs/datamanager/src/stores/Filters/FilterRegistry.js`

Register the new geometry column types so the filter panel renders them correctly.
Geometry Number types use a standard numeric input. Geometry Boolean types use a
toggle (same as existing boolean filters).

### Changes to `web/libs/datamanager/src/components/Filters/FilterInput.jsx`

No new input type needed — geometry Number filters reuse the existing `Number` input
component. Geometry Boolean filters reuse the existing `Boolean` toggle. The column
`title` strings already describe what the predicate means.

### No other frontend changes needed for Phase 2

The filter panel dynamically renders from the registry — adding the column definitions
above is sufficient. The Data Manager will show the new geometry predicates in the
"Add filter" dropdown under a "Annotation Geometry" group.

---

## Phase 3 — Bulk correction action button

**Docker mode:** `full`

### Changes to `web/libs/datamanager/src/components/DataManager/`

Add a "Fix selected" button to the Data Manager toolbar that appears when tasks are
selected. Clicking it opens a modal:

```
Fix selected tasks
─────────────────
Action: [ Drop regions matching predicate ▼ ]
Predicate: [ Extreme aspect ratio ▼ ]  Threshold: [ 20 ]
On nesting: [ Keep outer ▼ ]

[ Cancel ]  [ Apply to 47 tasks ]
```

On confirm: calls `POST /api/dm/actions/bulk-geometry-correct` with selected task IDs.
Shows result toast: "Modified 47 tasks, deleted 312 regions."

---

## Acceptance criteria

- [ ] Filter `extreme_aspect_ratio > 20` returns only tasks containing such regions
- [ ] Filter `nested_same_class = true` returns only tasks with same-class nesting
- [ ] Filters compose with existing metadata filters (AND logic)
- [ ] Bulk correction with `drop_regions_matching extreme_aspect_ratio 20` removes
      correct regions and leaves the rest intact
- [ ] Works against PostgreSQL (not just SQLite)
- [ ] No regression on existing filter behavior (test with a standard label/choice filter)
