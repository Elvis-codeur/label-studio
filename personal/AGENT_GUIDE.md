# Agent Guide — Personal Label Studio Fork

This document is the single source of truth for any agent (or the user in a new session)
continuing development on this fork. Read it entirely before touching any code.

---

## 1. Context

This is a personal fork of [HumanSignal/label-studio](https://github.com/HumanSignal/label-studio)
maintained by the repo owner. It is deployed as the `labelstudio` service in the
`datasheet-manager` Docker Compose stack in place of the official image.

**Goal:** add annotation quality features that do not exist upstream — see ROADMAP.md.

**This is NOT upstream contribution work.** No CLA, no upstream PR standards, no need
to wait for maintainer approval. Code must work correctly and cleanly, but it does not
need to meet HumanSignal's review bar.

---

## 2. Repository layout (relevant parts)

```
contributions/label-studio/
├── personal/                  ← YOU ARE HERE — specs, roadmap, this guide
│   ├── AGENT_GUIDE.md         ← read first every session
│   ├── ROADMAP.md             ← feature list and status
│   ├── spec_idea1_*.md        ← one spec per feature
│   └── ...
├── Dockerfile.personal        ← build file used by docker-compose.dev.yml
├── label_studio/              ← Django backend (Python)
│   ├── data_manager/          ← filter engine — main backend target
│   │   ├── managers/          ← queryset-level filter logic
│   │   ├── serializers/       ← column/filter serializers
│   │   └── api.py             ← Data Manager REST endpoints
│   └── tasks/                 ← Task and Annotation models
│       ├── models.py
│       └── serializers.py
└── web/                       ← React frontend
    └── libs/datamanager/      ← Data Manager UI — main frontend target
        ├── src/
        │   ├── components/    ← React components
        │   ├── stores/        ← MobX stores
        │   └── utils/         ← utilities
        └── src/sdk/           ← public SDK surface
```

---

## 3. Branch strategy

| Branch | Purpose | Rules |
|--------|---------|-------|
| `develop` | Tracks upstream `HumanSignal/label-studio:develop` | Never commit here |
| `personal/main` | **Production branch** — what runs in Docker | Only merge finished features |
| `feature/<name>` | One branch per feature | Branch from `personal/main`, merge back when done |

```bash
# Start a new feature
git checkout personal/main
git checkout -b feature/annotation-geometry-filter

# When done
git checkout personal/main
git merge --no-ff feature/annotation-geometry-filter
git push origin personal/main
```

---

## 4. How the Docker build works

`datasheet-manager/docker-compose.dev.yml` builds from this fork:

```yaml
labelstudio:
  build:
    context: ../contributions/label-studio
    dockerfile: Dockerfile.personal
    args:
      BUILD_MODE: backend-only   # or: full
```

**`backend-only` mode (default):**
- Layers our modified `label_studio/` Python files on top of `heartexlabs/label-studio:latest`
- Rebuild time: ~2 minutes (Docker layer cache makes it fast after the first build)
- Use for: all backend changes (new filter operators, API endpoints, bulk correction)

**`full` mode:**
- Builds frontend JS from `web/` source + Python from scratch
- Rebuild time: 30–60 minutes on first build, faster with cache
- Use for: any changes to `web/libs/datamanager/` (React components, MobX stores)

**To rebuild and restart after code changes:**
```bash
cd datasheet-manager
docker compose -f docker-compose.dev.yml build labelstudio
docker compose -f docker-compose.dev.yml up -d labelstudio
```

**When switching BUILD_MODE from backend-only to full:**
```bash
# Edit docker-compose.dev.yml: change BUILD_MODE to full
# Then force a full rebuild without cache:
docker compose -f docker-compose.dev.yml build --no-cache labelstudio
```

---

## 5. Backend architecture — how filters work

Understanding this is mandatory before writing any filter feature.

### Filter execution path

```
Data Manager UI
  → GET /api/dm/views/{id}/tasks (with filter params)
  → label_studio/data_manager/api.py :: TaskListAPI
  → label_studio/data_manager/managers/task.py :: apply_filters()
  → Django ORM queryset with annotated columns
  → tasks returned to UI
```

### How a filter is defined

Each filterable column is registered in `label_studio/data_manager/prepare_params.py`
and `label_studio/data_manager/serializers.py`. A filter has:

- `id`: string key (e.g. `"filter:tasks:data.provider"`)
- `type`: data type (`"String"`, `"Number"`, `"Boolean"`, etc.)
- `operators`: list of allowed operators (`"equal"`, `"greater"`, `"contains"`, etc.)

Operators are applied in `label_studio/data_manager/managers/task.py` in
`TaskQuerySet.filter_tasks()`. Each operator maps to a Django ORM expression or
a raw queryset annotation.

### Where to add a geometry filter

New geometry predicates require two additions:

1. **Backend** (`label_studio/data_manager/`):
   - Register new column in `prepare_params.py`
   - Add operator handler in `managers/task.py` — geometry predicates require
     a subquery against the `tasks_annotation` table, parsing the JSON `result` field

2. **Frontend** (`web/libs/datamanager/src/`):
   - Register the new column type in the filter panel component
   - Add the threshold input UI if the predicate takes a numeric argument

See `spec_idea1_geometry_filter.md` for the detailed implementation plan.

---

## 6. Frontend architecture — Data Manager

The Data Manager is a React + MobX application in `web/libs/datamanager/`.

Key files:
- `src/stores/DataStore.js` — MobX store for task list + filter state
- `src/stores/Filters/` — filter state management
- `src/components/Filters/` — filter UI components (filter panel, predicate builder)
- `src/components/DataManager/DataManager.jsx` — top-level Data Manager component
- `src/components/TaskView/` — individual task view panel

**MobX pattern used:** observable stores with `action` mutations. Do not mutate store
state outside of `action`-decorated functions.

**Adding a new filter type to the UI:**
1. Add the column definition to `src/stores/Filters/FilterRegistry.js`
2. Add the input component to `src/components/Filters/FilterInput.jsx`
3. The filter panel renders dynamically from the registry — no hardcoded lists

---

## 7. Development checklist for each feature

Before starting:
- [ ] Read the spec file for the feature (`personal/spec_idea*.md`)
- [ ] Read this guide (section 5 or 6 depending on backend/frontend scope)
- [ ] Create feature branch from `personal/main`

While implementing:
- [ ] Backend changes: modify `label_studio/data_manager/` only
- [ ] Frontend changes: modify `web/libs/datamanager/src/` only
- [ ] Do not modify test files unless the spec explicitly requires it
- [ ] Do not change `pyproject.toml` or `poetry.lock` unless adding a new dependency (avoid if possible)

Before marking done:
- [ ] Rebuild the image and verify the feature works end-to-end in Docker
- [ ] Merge feature branch into `personal/main`
- [ ] Update ROADMAP.md status

---

## 8. Geometry primitives reference

These are the geometric operations needed across multiple features.
Implement once in `label_studio/data_manager/geometry.py` (create this file).

All coordinates are in Label Studio's native format: percentage of image dimensions,
`x` and `y` are top-left corner, `width` and `height` are positive.

```python
# Box representation from a result item's value dict:
# { "x": float, "y": float, "width": float, "height": float }
# All values in range [0, 100] (percent of image dimensions)

def aspect_ratio(box) -> float:
    """width / height. Returns inf if height == 0."""

def area_pct(box) -> float:
    """(width * height) / 10000. Fraction of image area, range [0, 1]."""

def intersection_area(a, b) -> float:
    """Area of intersection of two boxes, in same percentage-squared units."""

def iou(a, b) -> float:
    """Intersection over Union, range [0, 1]."""

def containment(inner, box) -> float:
    """Fraction of `inner` area covered by `box`. Range [0, 1].
    1.0 = inner is fully inside outer. Use threshold 0.70 for 'contained'."""

def contains(outer, inner, threshold=0.70) -> bool:
    """True if `outer` contains `inner` by at least `threshold`."""
```

These mirror the functions already in the main project's:
`datasheet-manager/labelization/management/commands/apply_annotation_rules.py`

---

## 9. Label Studio result format reference

A bounding box annotation region in Label Studio JSON:

```json
{
  "id": "abc123",
  "type": "rectanglelabels",
  "from_name": "label",
  "to_name": "image",
  "original_width": 1240,
  "original_height": 1754,
  "image_rotation": 0,
  "value": {
    "rotation": 0,
    "x": 10.5,
    "y": 20.3,
    "width": 45.2,
    "height": 12.8,
    "rectanglelabels": ["text"]
  }
}
```

To extract geometry for filtering:
- Box coordinates: `value.x`, `value.y`, `value.width`, `value.height`
- Label: `value.rectanglelabels[0]`
- Type filter (only process bounding boxes): `type == "rectanglelabels"`

In the Django database, annotation results are stored as JSON in:
`tasks_annotation.result` (a JSON array of result items as shown above).

---

## 10. Running Label Studio locally (outside Docker, for faster iteration)

When iterating on backend Python code, running LS outside Docker avoids rebuild cycles:

```bash
cd contributions/label-studio
python -m venv .venv && source .venv/bin/activate
pip install poetry
poetry install --extras uwsgi

export DJANGO_DB=sqlite
export LABEL_STUDIO_BASE_DATA_DIR=/tmp/ls-dev-data
python label_studio/manage.py migrate
python label_studio/manage.py runserver 0.0.0.0:8080
```

Note: this uses SQLite not PostgreSQL. For filter logic that involves JSON queries,
test against PostgreSQL (i.e. in Docker) before considering it done.
