from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CATEGORIES = ["BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM"]


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def score_submission(truth: dict[str, Any], submission: dict[str, Any]) -> dict[str, Any]:
    per = {c: {"tp": 0, "fp": 0, "fn": 0} for c in CATEGORIES}
    correct = 0
    for eid, gold in truth.items():
        actual = gold["category"]
        pred = submission.get(eid, {}).get("category", "GENERAL")
        if pred == actual:
            correct += 1
            per[actual]["tp"] += 1
        else:
            per[actual]["fn"] += 1
            if pred in per:
                per[pred]["fp"] += 1
    accuracy = correct / len(truth) if truth else 0.0
    macro_f1 = sum(prf(**per[c])[2] for c in CATEGORIES) / len(CATEGORIES)

    tp = fp = fn = 0
    for eid, gold in truth.items():
        if gold["category"] != "BL_COMPARISON" or gold.get("status") == "NEEDS_REVIEW":
            continue
        row = submission.get(eid, {})
        routed = row.get("category") == "BL_COMPARISON"
        pred_defect = bool(row.get("has_defect")) and routed
        gold_defect = gold["has_defect"]
        if gold_defect and pred_defect:
            tp += 1
        elif gold_defect and not pred_defect:
            fn += 1
        elif not gold_defect and pred_defect:
            fp += 1
    _, _, defect_f1 = prf(tp, fp, fn)

    e2e_ok = e2e_total = 0
    for eid, gold in truth.items():
        if not (gold["category"] == "BL_COMPARISON" and gold.get("has_defect")):
            continue
        e2e_total += 1
        row = submission.get(eid, {})
        if (
            row.get("category") == "BL_COMPARISON"
            and row.get("has_defect")
            and set(row.get("defect_fields") or []) == set(gold.get("defect_fields") or [])
        ):
            e2e_ok += 1
    e2e = e2e_ok / e2e_total if e2e_total else 0.0

    esc_tp = esc_fn = pred_review = esc_correct = gold_review = 0
    for eid, gold in truth.items():
        row = submission.get(eid, {})
        pred_needs = row.get("status") == "NEEDS_REVIEW"
        gold_needs = gold.get("status") == "NEEDS_REVIEW"
        if pred_needs:
            pred_review += 1
            if gold_needs:
                esc_correct += 1
        if gold_needs:
            gold_review += 1
            if pred_needs:
                esc_tp += 1
            else:
                esc_fn += 1
    rec = esc_tp / gold_review if gold_review else 0.0
    prec = esc_correct / pred_review if pred_review else 0.0
    esc_f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0

    final = 0.30 * macro_f1 + 0.20 * defect_f1 + 0.50 * e2e
    return {
        "n_emails": len(truth),
        "stage1_accuracy": round(accuracy, 4),
        "stage1_macro_f1": round(macro_f1, 4),
        "stage3_defect_f1": round(defect_f1, 4),
        "end_to_end": round(e2e, 4),
        "escalation_f1": round(esc_f1, 4),
        "final_score": round(final, 4),
    }


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
