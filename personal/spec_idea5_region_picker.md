# Spec — Idea 5: Graphical Region Picker → Code Snippet

**Branch:** `feature/region-picker`
**Docker mode:** `full`
**Depends on:** Idea 4 (custom JS filter editor where the snippet is inserted)
**Status:** not started — implement last

---

## Goal

Let users draw a rectangle on the annotation canvas with the mouse and immediately
receive the corresponding coordinate object as a code snippet. The snippet can be
copied or inserted directly into the custom JS filter expression editor (Idea 4).

This removes the need to know Label Studio's coordinate system (percentage-based,
origin top-left) when writing spatial zone predicates.

---

## Use case

A user wants to filter tasks where any annotation box falls within a specific zone
of the image — for example, the left half of the image between 20% and 60% height.
Instead of guessing `{ x: 0, y: 20, width: 50, height: 40 }`, they:

1. Click the "Pick zone" button in the filter panel
2. Draw a rectangle on the currently visible task image
3. The sidebar shows:

```js
// Zone drawn on canvas:
const zone = { x: 0.0, y: 20.3, width: 49.8, height: 39.7 };

// Use in filter expression:
task.annotations.some(a =>
  a.result.some(r =>
    r.type === "rectanglelabels" && inside_zone(r.value, zone)
  )
)
```

4. They click "Insert into filter" to paste the snippet into the active expression editor

---

## Implementation

### New utility function

Add to `web/libs/datamanager/src/utils/geometry.js`:

```js
/**
 * Returns true if the center of `value` falls inside `zone`.
 * Both use Label Studio percentage coordinates.
 * @param {Object} value - region value dict {x, y, width, height}
 * @param {Object} zone  - zone dict {x, y, width, height}
 */
export function inside_zone(value, zone) {
  const cx = value.x + value.width / 2;
  const cy = value.y + value.height / 2;
  return (
    cx >= zone.x && cx <= zone.x + zone.width &&
    cy >= zone.y && cy <= zone.y + zone.height
  );
}
```

### "Pick zone" mode in the annotation canvas

The annotation canvas already supports drawing rectangles (it's the core interaction
for bounding box annotation). Add a new tool mode `zone-picker` that:

- Is activated by a "Pick zone" button in the filter panel (NOT in the main annotation toolbar)
- When active, cursor changes to crosshair
- User draws a rectangle — fires a `zone-picked` event with the coordinate object
- Does NOT create an annotation — this is read-only zone selection
- Deactivates automatically after one zone is drawn

The canvas interaction is in `web/apps/labelstudio/src/` (the main Label Studio app
canvas). The zone-picker mode should be implemented as a minimal, non-destructive
overlay — it does not touch the annotation creation logic.

### Snippet sidebar

When a zone is picked, a small sidebar panel appears (or the filter panel updates)
showing:
- The coordinate object
- A pre-written `inside_zone` filter snippet
- A "Copy" button
- An "Insert into expression editor" button (only shown if Idea 4 custom filter is active)

### Coordinate display format

Show coordinates rounded to 1 decimal place. Show both the raw object and the
ready-to-use snippet. Do not show the internal LS format (x/y as top-left corner,
percentage) — just expose it as-is since that's what the geometry utils expect.

---

## Acceptance criteria

- [ ] "Pick zone" button appears in the filter panel (when at least one task is open)
- [ ] Clicking it enters zone-picker mode without modifying any annotation
- [ ] Drawing a rectangle generates the correct coordinate object (percentage, top-left)
- [ ] The generated snippet is syntactically valid JS and works in the Idea 4 editor
- [ ] `inside_zone(value, zone)` is available as a built-in in the custom JS scope
- [ ] "Insert into expression editor" works when the custom JS filter is active
- [ ] Zone-picker mode does not interfere with normal annotation creation
- [ ] Works for images at any zoom level (coordinates must be image-relative, not screen-relative)
