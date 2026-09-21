"""Corrections become retrievable examples for the party-name judge.

Lookup is exact on the folded pair, so a stored decision short-circuits the
LLM. A handful of recent examples are also offered to the model as context
when the pair has not been seen before.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from verify.text.normalize import fold_party, fold_port

_PARTY = {"shipper", "consignee", "notify_party"}
_PORT = {"port_of_loading", "port_of_discharge"}


def _fold(field: str, value: str) -> str:
    if field in _PARTY:
        return fold_party(value)
    if field in _PORT:
        return fold_port(value)
    return (value or "").strip().casefold()


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class FewShotStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._items: list[dict] = []
        self._load()

    def items(self) -> list[dict]:
        return list(self._items)

    def _load(self) -> None:
        if self.path.is_file():
            self._items = json.loads(self.path.read_text(encoding="utf-8")).get("items") or []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"items": self._items}, indent=2), encoding="utf-8")

    def remember(
        self,
        *,
        field: str,
        si_value: str | None,
        bl_value: str | None,
        same: bool,
        note: str | None = None,
        email_id: str | None = None,
    ) -> bool:
        if not si_value or not bl_value:
            return False
        key = (_fold(field, si_value), _fold(field, bl_value))
        for item in self._items:
            if item.get("field") == field and (item.get("left"), item.get("right")) == key:
                item["same"] = same
                item["note"] = note or ""
                item["at"] = _now()
                self._save()
                return True
        self._items.append(
            {
                "field": field,
                "left": key[0],
                "right": key[1],
                "si_value": si_value,
                "bl_value": bl_value,
                "same": same,
                "note": note or "",
                "email_id": email_id,
                "at": _now(),
            }
        )
        self._save()
        return True

    def lookup(self, field: str, si_value: str | None, bl_value: str | None) -> bool | None:
        if not si_value or not bl_value:
            return None
        key = (_fold(field, si_value), _fold(field, bl_value))
        flipped = (key[1], key[0])
        for item in reversed(self._items):
            if item.get("field") != field:
                continue
            pair = (item.get("left"), item.get("right"))
            if pair == key or pair == flipped:
                return bool(item.get("same"))
        return None

    def examples(self, field: str, *, limit: int = 3) -> list[dict]:
        matched = [item for item in self._items if item.get("field") == field]
        return matched[-limit:]

    def learn_from_correction(
        self,
        *,
        previous_defects: list[str],
        current_defects: list[str],
        comparisons: list[dict],
        email_id: str | None = None,
        note: str | None = None,
    ) -> list[str]:
        """A field that left the defect list is a same-entity example.
        A field that entered the defect list is a distinct-entity example."""
        previous = set(previous_defects)
        current = set(current_defects)
        remembered: list[str] = []
        for comp in comparisons:
            field = comp.get("field")
            if field in previous and field not in current:
                same = True
            elif field in current and field not in previous:
                same = False
            else:
                continue
            if self.remember(
                field=field,
                si_value=comp.get("si_value"),
                bl_value=comp.get("bl_value"),
                same=same,
                note=note,
                email_id=email_id,
            ):
                remembered.append(field)
        return remembered
