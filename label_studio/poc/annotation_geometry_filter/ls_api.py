"""
Minimal Label Studio API client for annotation geometry filtering and bulk correction.

Requires only the `requests` library (no LS SDK dependency).

Usage:
    client = LSClient(url="http://localhost:8080", api_key="your-token")
    tasks = client.filter_tasks_by_geometry(project_id=1, predicate=has_nested_same_class)
    for task_id, annotation_id, result in tasks:
        corrected, stats = auto_correct(result)
        client.update_annotation(annotation_id, corrected)
"""

from __future__ import annotations
import json
from typing import Callable, Generator
import requests

from .predicates import audit
from .corrections import auto_correct


class LSClient:
    def __init__(self, url: str, api_key: str):
        """
        Args:
            url:     Base URL of your Label Studio instance, e.g. "http://localhost:8080"
            api_key: Personal access token (Settings → Account → Access Token)
        """
        self.base = url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Token {api_key}"})

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def export_annotations(self, project_id: int) -> list[dict]:
        """
        Export all tasks with their annotations for a project.
        Returns a list of task dicts, each containing an "annotations" key.
        """
        resp = self.session.get(
            f"{self.base}/api/projects/{project_id}/export",
            params={"exportType": "JSON"},
        )
        resp.raise_for_status()
        return resp.json()

    def get_annotation(self, annotation_id: int) -> dict:
        """Fetch a single annotation by ID."""
        resp = self.session.get(f"{self.base}/api/annotations/{annotation_id}/")
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def update_annotation(self, annotation_id: int, result: list[dict]) -> dict:
        """
        Replace the result of an annotation (full replacement — not a merge).
        Returns the updated annotation dict.

        WARNING: this overwrites the entire result array. Always build
        `result` from the existing annotation rather than from scratch.
        """
        resp = self.session.patch(
            f"{self.base}/api/annotations/{annotation_id}/",
            json={"result": result},
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Filter helpers
    # ------------------------------------------------------------------

    def filter_tasks_by_geometry(
        self,
        project_id: int,
        predicate: Callable[[list[dict]], bool],
    ) -> Generator[tuple[int, int, list[dict]], None, None]:
        """
        Yield (task_id, annotation_id, result) for every annotation that
        matches `predicate`.

        Args:
            project_id: Label Studio project ID.
            predicate:  Any function from predicates.py, e.g. has_nested_same_class.
                        Receives the raw result list, returns True to include the task.

        Yields:
            (task_id, annotation_id, result)

        Example:
            from predicates import has_extreme_aspect_ratio
            for task_id, ann_id, result in client.filter_tasks_by_geometry(1, has_extreme_aspect_ratio):
                print(task_id)
        """
        tasks = self.export_annotations(project_id)
        for task in tasks:
            task_id = task["id"]
            for annotation in task.get("annotations", []):
                result = annotation.get("result", [])
                if predicate(result):
                    yield task_id, annotation["id"], result

    def audit_project(self, project_id: int) -> list[dict]:
        """
        Run all geometry predicates on every annotation in a project.
        Returns a list of dicts with task_id, annotation_id, and per-issue flags.

        Useful for getting an overview of annotation quality before deciding
        which corrections to apply.

        Example output row:
            {
                "task_id": 42,
                "annotation_id": 101,
                "extreme_aspect_ratio": True,
                "tiny_box": False,
                "nested_same_class": True,
                ...
            }
        """
        results = []
        tasks = self.export_annotations(project_id)
        for task in tasks:
            task_id = task["id"]
            for annotation in task.get("annotations", []):
                issues = audit(annotation.get("result", []))
                results.append(
                    {"task_id": task_id, "annotation_id": annotation["id"], **issues}
                )
        return results

    # ------------------------------------------------------------------
    # Bulk correction
    # ------------------------------------------------------------------

    def bulk_auto_correct(
        self,
        project_id: int,
        dry_run: bool = True,
        **correction_kwargs,
    ) -> list[dict]:
        """
        Apply auto_correct() to every annotation in a project and
        optionally write the corrections back to Label Studio.

        Args:
            project_id:          Label Studio project ID.
            dry_run:             If True (default), compute corrections but do NOT
                                 write anything. Use this to preview the impact first.
            **correction_kwargs: Passed through to auto_correct() — lets you override
                                 thresholds, e.g. drop_ar_threshold=15.0.

        Returns:
            List of correction report dicts:
            [
                {
                    "task_id": 42,
                    "annotation_id": 101,
                    "original_count": 18,
                    "corrected_count": 14,
                    "stats": {"nested_same_class": 3, "tiny_boxes": 1, ...},
                    "written": True / False,
                },
                ...
            ]
        """
        report = []
        tasks = self.export_annotations(project_id)

        for task in tasks:
            task_id = task["id"]
            for annotation in task.get("annotations", []):
                ann_id = annotation["id"]
                original_result = annotation.get("result", [])
                corrected_result, stats = auto_correct(original_result, **correction_kwargs)

                n_dropped = sum(stats.values())
                entry = {
                    "task_id": task_id,
                    "annotation_id": ann_id,
                    "original_count": len(original_result),
                    "corrected_count": len(corrected_result),
                    "stats": stats,
                    "written": False,
                }

                if n_dropped > 0 and not dry_run:
                    self.update_annotation(ann_id, corrected_result)
                    entry["written"] = True

                if n_dropped > 0:
                    report.append(entry)

        return report
