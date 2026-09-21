"""Confusion matrix, field precision and recall, and the headline score.

Works on any ground-truth file shaped like the hackathon bundle.
"""

from __future__ import annotations

from typing import Any

from verify.domain.enums import COMPARE_FIELDS
from verify.eval.score import CATEGORIES, prf, score_submission


def confusion_matrix(truth: dict[str, Any], submission: dict[str, Any]) -> dict[str, dict[str, int]]:
    matrix = {gold: {pred: 0 for pred in CATEGORIES} for gold in CATEGORIES}
    for eid, gold in truth.items():
        actual = gold["category"]
        pred = submission.get(eid, {}).get("category", "GENERAL")
        if actual not in matrix:
            continue
        if pred not in matrix[actual]:
            matrix[actual][pred] = 0
        matrix[actual][pred] += 1
    return matrix


def field_scores(truth: dict[str, Any], submission: dict[str, Any]) -> dict[str, Any]:
    """Precision and recall of each defect field on comparable BL cases."""
    per: dict[str, dict[str, int]] = {name: {"tp": 0, "fp": 0, "fn": 0} for name in COMPARE_FIELDS}
    for eid, gold in truth.items():
        if gold.get("category") != "BL_COMPARISON" or gold.get("status") == "NEEDS_REVIEW":
            continue
        gold_fields = set(gold.get("defect_fields") or [])
        row = submission.get(eid, {})
        pred_fields = set(row.get("defect_fields") or []) if row.get("category") == "BL_COMPARISON" else set()
        for name in COMPARE_FIELDS:
            if name in gold_fields and name in pred_fields:
                per[name]["tp"] += 1
            elif name in pred_fields:
                per[name]["fp"] += 1
            elif name in gold_fields:
                per[name]["fn"] += 1
    scored = {}
    for name, counts in per.items():
        precision, recall, f1 = prf(counts["tp"], counts["fp"], counts["fn"])
        scored[name] = {
            **counts,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }
    return scored


def full_report(truth: dict[str, Any], submission: dict[str, Any]) -> dict[str, Any]:
    return {
        "score": score_submission(truth, submission),
        "confusion_matrix": confusion_matrix(truth, submission),
        "fields": field_scores(truth, submission),
    }
