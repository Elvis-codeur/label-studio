# Spec — Idea 3: Filter Panel Accessible from Task View

**Branch:** `feature/filter-in-task-view`
**Docker mode:** `full`
**Status:** not started

---

## Goal

When the user is viewing a specific task (the task detail panel on the right side of
the Data Manager), they can open and edit the current tab's filter without navigating
back to the project data list. Changes to the filter take effect immediately on the
task list, and the previous/next navigation reflects the updated filter.

---

## Problem in detail

Current URL when viewing a task:
`/projects/3/data?tab=3&task=1307`

The filter panel only renders when no task is selected (i.e. `task` param absent from
URL). Opening a task hides the filter panel. To adjust the filter, the user must:
1. Close the task (navigate back to `/projects/3/data?tab=3`)
2. Adjust the filter
3. Find and re-open the relevant task

This is disruptive when iterating on filter thresholds while looking at borderline cases.

---

## Implementation

### Changes to `web/libs/datamanager/src/components/DataManager/DataManager.jsx`

Add an "Edit filter" icon button in the task view header bar (top-right area, next to
the close button). The button is only shown when a task is open AND the current tab
has an active filter.

```jsx
// In the task view header:
{hasActiveFilter && (
  <Button
    icon="filter"
    look="ghost"
    size="small"
    tooltip="Edit current filter"
    onClick={() => setFilterPanelOpen(true)}
  />
)}
```

### Filter panel as slide-over overlay

When `filterPanelOpen` is true, render the existing `<Filters />` component as a
slide-over panel anchored to the left side of the task view, overlapping the task
list partially. The task detail remains visible on the right.

Use the existing `<Filters />` component — do not duplicate it. Just change its
rendering context from "embedded in list view" to "floating overlay".

The filter panel must:
- Show the current filter state (same as when viewed from the list)
- Allow all the same edits (add/remove predicates, change values)
- Apply changes live (same behaviour as the list view filter)
- Close on Escape or clicking outside
- Not navigate away from the current task

### MobX store changes (`web/libs/datamanager/src/stores/`)

Add a `filterPanelOpen` observable to the view store. Toggle it from the task view
header button. The `<Filters />` component already reads/writes filter state from
the view store — no filter logic changes needed.

---

## Acceptance criteria

- [ ] When a task is open and the tab has an active filter, an "Edit filter" icon
      appears in the task view header
- [ ] Clicking it opens the filter panel as a slide-over without navigating away
- [ ] Filter changes apply immediately (task list updates, task count updates)
- [ ] Previous/next task navigation respects the updated filter
- [ ] The panel closes on Escape or outside click
- [ ] When no filter is active on the tab, the button is not shown
- [ ] No regression on the normal (non-task-view) filter panel behavior
