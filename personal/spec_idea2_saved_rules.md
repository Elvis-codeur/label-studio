# Spec — Idea 2: Persistent Saved Rule Library

**Branch:** `feature/saved-rule-library`
**Docker mode:** Phase 1 → `backend-only` · Phase 2 → `full`
**Depends on:** Idea 1 Phase 2 (geometry filters working in UI)
**Status:** not started

---

## Goal

Allow users to save a set of filter predicates (including geometry predicates) as a
named rule, and reapply that rule to any project without redefining it from scratch.

---

## Phase 1 — Backend: model + API

### New Django model: `AnnotationRule`

Location: `label_studio/data_manager/models.py` (or a new `rules/models.py`)

```python
class AnnotationRule(models.Model):
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    # Stored as JSON: list of filter dicts matching the Data Manager filter format
    # e.g. [{"id": "filter:tasks:annotations:geometry:extreme_aspect_ratio",
    #         "operator": "greater", "value": 20.0}]
    filters = models.JSONField(default=list)
    # Optional: bulk correction action to apply when this rule is triggered
    # e.g. {"action": "drop_regions_matching", "predicate": "extreme_aspect_ratio",
    #        "threshold": 20.0}
    correction_action = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        unique_together = [["organization", "name"]]
```

### New API endpoints

```
GET    /api/rules/                   List all rules for the user's org
POST   /api/rules/                   Create a new rule
GET    /api/rules/{id}/              Retrieve a rule
PATCH  /api/rules/{id}/              Update a rule
DELETE /api/rules/{id}/              Delete a rule
POST   /api/rules/{id}/apply/        Apply rule filters to a project (returns task count)
```

### Migration

Create and run a Django migration for the new model.

---

## Phase 2 — Frontend: save + apply UI

**Docker mode:** `full`

### Save rule button in filter panel

In `web/libs/datamanager/src/components/Filters/`, add a "Save as rule" button
at the bottom of the filter panel. It opens a small dialog:

```
Save current filters as rule
─────────────────────────────
Name: [ Nested same-class boxes    ]
Description: [ optional            ]
Also save correction action: [ ✓ ]
Action: [ Drop regions matching ▼ ]

[ Cancel ]  [ Save rule ]
```

On save: calls `POST /api/rules/` with the current filter state serialized.

### Apply rule picker in filter panel

Add a "Load rule" dropdown at the top of the filter panel. Selecting a rule replaces
the current filters with the rule's saved filters. Optionally shows the correction
action associated with the rule.

### Rule management page (optional, Phase 2b)

A simple settings page at `/rules/` listing all saved rules with edit/delete actions.
This can be a minimal Django admin view initially.

---

## Acceptance criteria

- [ ] A user can save the current filter state as a named rule
- [ ] Rules persist across browser sessions and across projects
- [ ] A user can load a saved rule into the filter panel of any project
- [ ] Rules are scoped to the organization (not per-project)
- [ ] A rule can optionally store a correction action alongside its filters
- [ ] Rules can be deleted without affecting existing annotations
