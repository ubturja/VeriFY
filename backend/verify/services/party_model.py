"""A local party-name model trained from reviewer corrections.

The few-shot store remembers an exact pair. This model is fit on those pairs
and written next to them, so the next pipeline run loads the new weights
without a separate deploy step. It only speaks inside the gray band, after an
exact correction has already been checked, and its note is a suggestion.
Only that exact correction may turn a mismatch into a match.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from rapidfuzz import fuzz

from verify.text.normalize import fold_party

_PARTY = {"shipper", "consignee", "notify_party"}
_MIN_EXAMPLES = 4


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sigmoid(value: float) -> float:
    if value >= 20:
        return 1.0
    if value <= -20:
        return 0.0
    return 1.0 / (1.0 + math.exp(-value))


def _features(left: str, right: str) -> list[float]:
    a = fold_party(left)
    b = fold_party(right)
    ratio = fuzz.ratio(a, b) / 100
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    union = tokens_a | tokens_b
    jaccard = (len(tokens_a & tokens_b) / len(union)) if union else 0.0
    prefix = 1.0 if a[:4] and a[:4] == b[:4] else 0.0
    longer = max(len(a), len(b), 1)
    length_ratio = min(len(a), len(b)) / longer
    return [ratio, jaccard, prefix, length_ratio]


@dataclass
class PartyDecision:
    same: bool
    confidence: float
    version: str


class PartyModel:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.ready = False
        self.version = ""
        self.weights = [0.0, 0.0, 0.0, 0.0]
        self.bias = 0.0
        self.n_examples = 0
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not payload.get("ready"):
            return
        weights = payload.get("weights") or []
        if len(weights) != 4:
            return
        self.ready = True
        self.version = str(payload.get("version") or "")
        self.weights = [float(item) for item in weights]
        self.bias = float(payload.get("bias") or 0.0)
        self.n_examples = int(payload.get("n_examples") or 0)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "ready": self.ready,
                    "version": self.version,
                    "weights": self.weights,
                    "bias": self.bias,
                    "n_examples": self.n_examples,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def retrain(self, examples: list[dict]) -> str | None:
        """Fit on party corrections. Returns the deployed version, or None."""
        rows: list[tuple[list[float], float]] = []
        for item in examples:
            if item.get("field") not in _PARTY:
                continue
            left = item.get("si_value")
            right = item.get("bl_value")
            if not left or not right:
                continue
            rows.append((_features(str(left), str(right)), 1.0 if item.get("same") else 0.0))
        classes = {label for _features_row, label in rows}
        if len(rows) < _MIN_EXAMPLES or len(classes) < 2:
            return self.version or None
        weights = [0.0, 0.0, 0.0, 0.0]
        bias = 0.0
        rate = 0.35
        for _epoch in range(500):
            for features, label in rows:
                score = sum(weight * feature for weight, feature in zip(weights, features, strict=True))
                prediction = _sigmoid(score + bias)
                error = prediction - label
                for index, feature in enumerate(features):
                    weights[index] -= rate * error * feature
                bias -= rate * error
        self.weights = weights
        self.bias = bias
        self.ready = True
        self.n_examples = len(rows)
        self.version = _now()
        self._save()
        return self.version

    def predict(self, left: str | None, right: str | None) -> PartyDecision | None:
        if not self.ready or not self.version or not left or not right:
            return None
        features = _features(left, right)
        total = sum(weight * feature for weight, feature in zip(self.weights, features, strict=True))
        score = _sigmoid(total + self.bias)
        same = score >= 0.5
        confidence = score if same else 1.0 - score
        if confidence < 0.8:
            return None
        return PartyDecision(same=same, confidence=confidence, version=self.version)


def version_from_notes(notes: list[str]) -> str | None:
    for note in notes:
        if note.startswith("local-model:") and "@" in note:
            return "local-party:" + note.rsplit("@", 1)[1]
    return None
