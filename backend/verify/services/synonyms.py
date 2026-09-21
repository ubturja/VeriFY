"""Per-tenant synonym learning.

Every time a reviewer corrects a MISMATCH into an OK on a party or port
field, we remember that the two strings referred to the same real-world
value. Later pipeline runs treat that pair as a match without touching the
rules or the LLM.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from verify.domain.enums import Status
from verify.domain.models import FieldComparison, PipelineResult
from verify.text.normalize import fold_party, fold_port

_PARTY = {"shipper", "consignee", "notify_party"}
_PORT = {"port_of_loading", "port_of_discharge"}


def _key(field: str, value: str) -> str:
    if field in _PARTY:
        return fold_party(value)
    if field in _PORT:
        return fold_port(value)
    return (value or "").strip().casefold()


class SynonymStore:
    """A simple JSON-backed set of ``(field, key_a, key_b)`` tuples."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._pairs: dict[str, set[frozenset[str]]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        for field, entries in (data.get("pairs") or {}).items():
            bucket: set[frozenset[str]] = set()
            for pair in entries:
                if len(pair) == 2:
                    bucket.add(frozenset(pair))
            self._pairs[field] = bucket

    def _save(self) -> None:
        payload = {
            "pairs": {
                field: [list(pair) for pair in sorted(bucket, key=lambda p: sorted(p))]
                for field, bucket in self._pairs.items()
            }
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def remember(self, field: str, a: str | None, b: str | None) -> bool:
        if not a or not b:
            return False
        ka, kb = _key(field, a), _key(field, b)
        if not ka or not kb or ka == kb:
            return False
        bucket = self._pairs.setdefault(field, set())
        pair = frozenset({ka, kb})
        if pair in bucket:
            return False
        bucket.add(pair)
        self._save()
        return True

    def are_same(self, field: str, a: str | None, b: str | None) -> bool:
        if not a or not b:
            return False
        ka, kb = _key(field, a), _key(field, b)
        if ka == kb:
            return True
        pair = frozenset({ka, kb})
        return pair in self._pairs.get(field, set())

    def apply(self, comparisons: list[FieldComparison]) -> list[str]:
        """Rewrite comparisons in place. Returns fields that were promoted."""
        promoted: list[str] = []
        for item in comparisons:
            if item.match is not False:
                continue
            if self.are_same(item.field, item.si_value, item.bl_value):
                item.match = True
                item.confidence = max(item.confidence, 0.98)
                item.note = "learned-synonym"
                promoted.append(item.field)
        return promoted

    def apply_to_result(self, result: PipelineResult) -> list[str]:
        """Post-process a fresh pipeline result: promote any comparison rows
        the tenant has already taught us to accept, then rebuild the
        derived defect_fields / has_defect / status flags. Returns the list
        of fields that were promoted."""
        if not getattr(result, "comparisons", None):
            return []
        promoted = self.apply(result.comparisons)
        if not promoted:
            return []
        result.defect_fields = [item.field for item in result.comparisons if item.match is False]
        result.has_defect = bool(result.defect_fields)
        if result.status == Status.MISMATCH and not result.defect_fields:
            result.status = Status.OK
        note = f"synonyms-applied:{','.join(promoted)}"
        if note not in (result.notes or []):
            result.notes = (result.notes or []) + [note]
        return promoted

    def learn_from_correction(
        self,
        *,
        previous_defects: list[str],
        current_defects: list[str],
        comparisons: list[dict[str, Any]] | list[FieldComparison],
    ) -> list[str]:
        """Record any field that used to be a defect and no longer is."""
        cleared = set(previous_defects) - set(current_defects)
        if not cleared:
            return []
        remembered: list[str] = []
        for comp in comparisons:
            data = comp.model_dump() if hasattr(comp, "model_dump") else comp
            field = data.get("field")
            if field in cleared and self.remember(field, data.get("si_value"), data.get("bl_value")):
                remembered.append(field)
        return remembered
