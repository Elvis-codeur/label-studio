"""
End-to-end example: audit a project, filter tasks by geometry, and bulk-correct.

Set your Label Studio URL and API key via environment variables:
    export LS_URL=http://localhost:8080
    export LS_API_KEY=your-personal-access-token
    export LS_PROJECT_ID=1

Then run:
    python example_usage.py
"""

import os
import json
from ls_api import LSClient
from predicates import has_nested_same_class, has_extreme_aspect_ratio, audit
from corrections import auto_correct

LS_URL        = os.environ.get("LS_URL", "http://localhost:8080")
LS_API_KEY    = os.environ.get("LS_API_KEY", "")
LS_PROJECT_ID = int(os.environ.get("LS_PROJECT_ID", "1"))

client = LSClient(url=LS_URL, api_key=LS_API_KEY)


# ──────────────────────────────────────────────────────────────────────────────
# 1. AUDIT — get an overview of geometry issues across the whole project
# ──────────────────────────────────────────────────────────────────────────────

print("=== Auditing project ===")
audit_report = client.audit_project(LS_PROJECT_ID)

total = len(audit_report)
counts = {}
for row in audit_report:
    for issue, flagged in row.items():
        if issue in ("task_id", "annotation_id"):
            continue
        if flagged:
            counts[issue] = counts.get(issue, 0) + 1

print(f"Total annotations audited: {total}")
print("Issues found:")
for issue, count in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"  {issue:30s}: {count:5d}  ({100*count/total:.1f}%)")


# ──────────────────────────────────────────────────────────────────────────────
# 2. FILTER — find all tasks with nested same-class boxes
# ──────────────────────────────────────────────────────────────────────────────

print("\n=== Filtering tasks with nested same-class boxes ===")
matching_tasks = []
for task_id, ann_id, result in client.filter_tasks_by_geometry(
    LS_PROJECT_ID, has_nested_same_class
):
    matching_tasks.append((task_id, ann_id))
    print(f"  task {task_id}  annotation {ann_id}")

print(f"Total: {len(matching_tasks)} tasks")


# ──────────────────────────────────────────────────────────────────────────────
# 3. DRY RUN — preview what auto_correct would do, without writing anything
# ──────────────────────────────────────────────────────────────────────────────

print("\n=== Dry run: bulk auto-correct (no writes) ===")
dry_report = client.bulk_auto_correct(LS_PROJECT_ID, dry_run=True)

total_dropped = sum(sum(r["stats"].values()) for r in dry_report)
print(f"Would correct {len(dry_report)} annotations, dropping {total_dropped} regions total")
print("Breakdown by rule:")
rule_totals: dict[str, int] = {}
for r in dry_report:
    for rule, n in r["stats"].items():
        rule_totals[rule] = rule_totals.get(rule, 0) + n
for rule, n in sorted(rule_totals.items(), key=lambda x: -x[1]):
    print(f"  {rule:30s}: {n}")


# ──────────────────────────────────────────────────────────────────────────────
# 4. APPLY — write corrections (uncomment when ready)
# ──────────────────────────────────────────────────────────────────────────────

# print("\n=== Applying corrections ===")
# report = client.bulk_auto_correct(LS_PROJECT_ID, dry_run=False)
# written = [r for r in report if r["written"]]
# print(f"Corrected and wrote {len(written)} annotations")
# with open("correction_report.json", "w") as f:
#     json.dump(report, f, indent=2)
# print("Full report saved to correction_report.json")


# ──────────────────────────────────────────────────────────────────────────────
# 5. CUSTOM PREDICATE — combine geometry with task metadata
# ──────────────────────────────────────────────────────────────────────────────

# Example: find tasks where split=="train" AND any box has aspect_ratio > 20
# (requires your tasks to have a "split" field in task.data)

from predicates import has_extreme_aspect_ratio

print("\n=== Custom predicate: split=train AND extreme_aspect_ratio ===")
tasks = client.export_annotations(LS_PROJECT_ID)
for task in tasks:
    if task.get("data", {}).get("split") != "train":
        continue
    for annotation in task.get("annotations", []):
        if has_extreme_aspect_ratio(annotation["result"]):
            print(f"  task {task['id']}  annotation {annotation['id']}")
