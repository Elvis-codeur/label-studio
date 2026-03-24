# Personal Fork Roadmap

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done

---

## Idea 1 — Annotation geometry filter + bulk correction
**Spec:** `spec_idea1_geometry_filter.md`
**Branch:** `feature/annotation-geometry-filter`
**Docker mode:** `backend-only` for Phase 1, `full` for Phase 2

- [ ] Phase 1 — Backend geometry predicates + filter API
- [ ] Phase 2 — Frontend filter panel UI (predicate builder)
- [ ] Phase 3 — Bulk correction action

---

## Idea 2 — Persistent saved rule library
**Spec:** `spec_idea2_saved_rules.md`
**Branch:** `feature/saved-rule-library`
**Depends on:** Idea 1 (Phase 2 done)

- [ ] Phase 1 — Backend model + API (save/load/delete rules)
- [ ] Phase 2 — Frontend save button + rule picker in filter panel

---

## Idea 3 — Filter panel accessible from task view
**Spec:** `spec_idea3_filter_in_task_view.md`
**Branch:** `feature/filter-in-task-view`
**Docker mode:** `full`

- [ ] Phase 1 — "Edit filter" button in task view header
- [ ] Phase 2 — Filter panel opens as slide-over, updates task list live

---

## Idea 4 — Custom JS filter expression editor
**Spec:** `spec_idea4_custom_js_filter.md`
**Branch:** `feature/custom-js-filter`
**Depends on:** Idea 1 (geometry primitives available as JS utils)

- [ ] Phase 1 — JS expression editor component in filter panel
- [ ] Phase 2 — Expose geometry utils in expression scope
- [ ] Phase 3 — Server-side safe evaluation (sandboxed)

---

## Idea 5 — Graphical region picker → code snippet
**Spec:** `spec_idea5_region_picker.md`
**Branch:** `feature/region-picker`
**Docker mode:** `full`

- [ ] Phase 1 — "Pick region" mode toggle in annotation canvas
- [ ] Phase 2 — Draw zone → generate coordinate object + code snippet
- [ ] Phase 3 — Copy-to-clipboard + insert into filter expression editor
