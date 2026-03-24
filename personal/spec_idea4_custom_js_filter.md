# Spec — Idea 4: Custom JavaScript Filter Expression Editor

**Branch:** `feature/custom-js-filter`
**Docker mode:** `full`
**Depends on:** Idea 1 (geometry primitives as JS utils)
**Status:** not started — implement after Ideas 1, 2, 3 are done

---

## Goal

Let power users write a custom JavaScript expression that receives the full task object
and returns a boolean. The expression has access to built-in geometry utility functions.
Tasks for which the expression returns true are included in the filtered list.

---

## Why this matters

Predefined geometry predicates (Idea 1) cover the most common patterns. But some
annotation quality issues require combining task metadata with annotation geometry
in ways no predefined predicate can express. Example:

```js
// Tasks in the "train" split where any box has aspect ratio > 20
task.data.split === "train" &&
task.annotations.some(a =>
  a.result.some(r => r.type === "rectanglelabels" && aspect_ratio(r.value) > 20)
)
```

---

## Implementation

### Backend: safe expression evaluation

**Do not use Python `eval()` on arbitrary JS.** The expression runs client-side in the
browser — the backend only receives a list of matching task IDs, not the expression
itself. This avoids any server-side code injection risk.

The filter works as follows:
1. The frontend fetches the full task list (or a page of tasks) from the existing API
2. The JS expression is evaluated client-side against each task object
3. Only matching task IDs are passed back to the server for display

This means: no backend changes needed for basic custom JS filtering. The expression
runs entirely in the browser.

### Frontend: expression editor component

New component: `web/libs/datamanager/src/components/Filters/CustomFilterEditor.jsx`

```jsx
// Renders a code editor (use CodeMirror, already a dependency in LS) with:
// - Syntax highlighting (JavaScript)
// - A "task" variable description shown above the editor
// - Inline documentation for available utils: aspect_ratio, area_pct, iou, containment
// - A "Test" button that runs the expression against the current task (if one is open)
// - An error display if the expression throws
```

### Built-in geometry utils exposed to the expression scope

```js
// Available in the expression as global functions:
aspect_ratio(value)      // value = region.value dict
area_pct(value)          // fraction of image area [0,1]
iou(value_a, value_b)    // intersection over union [0,1]
containment(inner, outer) // fraction of inner inside outer [0,1]
contains(outer, inner, threshold=0.70) // boolean
```

These are the JS equivalents of the Python geometry primitives from Idea 1.
Implement them in `web/libs/datamanager/src/utils/geometry.js` (create this file).

### Filter panel integration

In the "Add filter" dropdown, add a special entry "Custom expression (JS)" at the
bottom. Selecting it opens the `<CustomFilterEditor />` instead of the standard
predicate builder.

Only one custom expression filter can be active at a time. It can be combined with
standard filters (AND logic: task must pass all active filters).

### Performance considerations

Running a JS expression against every task in a large project (2,000+ tasks) is fast
in the browser (< 100ms for simple expressions). For projects with > 10,000 tasks,
add a warning: "Custom expressions evaluate client-side. Large projects may be slow."

Do not implement server-side expression evaluation. Keep it simple.

---

## Acceptance criteria

- [ ] A custom JS expression can be entered in the filter panel
- [ ] The expression receives the full task object (data, annotations, predictions, metadata)
- [ ] Built-in geometry functions are available (aspect_ratio, area_pct, iou, containment)
- [ ] Syntax errors in the expression are caught and shown to the user
- [ ] The expression filter composes with standard filters (AND logic)
- [ ] Expression is persisted in the tab's filter state (survives page reload)
- [ ] No server-side code execution — expression runs in the browser only
