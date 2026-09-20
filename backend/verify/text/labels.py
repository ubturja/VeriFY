"""Canonical field labels and known synonyms.

This dictionary is a cache of mappings, not the definition of a field.
Unknown labels fall through to LLM extraction. Human corrections append here
at runtime (see learning store) without a code change.
"""

from __future__ import annotations

from verify.text.normalize import collapse_ws

LABEL_SYNONYMS: dict[str, tuple[str, ...]] = {
    "shipper": (
        "shipper",
        "shipper/exporter",
        "shipper (principal or seller)",
        "shipper (发货人)",
        "exporter",
        "seller",
        "发货人",
    ),
    "consignee": (
        "consignee",
        "consignee (non-negotiable)",
        "consignee (收货人)",
        "to the order of",
        "buyer",
        "收货人",
    ),
    "notify_party": (
        "notify party",
        "notify",
        "notify party/intermediate consignee",
        "notify party (通知人)",
        "通知人",
    ),
    "port_of_loading": (
        "port of loading",
        "port of loading (pol)",
        "load port",
        "pol",
        "port of loading (装货港)",
        "装货港",
    ),
    "port_of_discharge": (
        "port of discharge",
        "port of discharge (pod)",
        "discharge port",
        "pod",
        "port of discharge (卸货港)",
        "卸货港",
    ),
    "container_count": (
        "no. of containers",
        "no. of containers or packages",
        "total containers",
        "container count",
        "箱数",
        "no. of containers or packages (箱数)",
        "container count (箱数)",
    ),
    "gross_weight_kg": (
        "gross weight (kg)",
        "gross wt (kgs)",
        "gross weight毛重(kgs)",
        "gross weight",
        "gross weight (毛重 kgs)",
        "total gross weight (kg)",
        "毛重",
        "gross wt",
    ),
}

_LOOKUP: dict[str, str] = {}
for field, labels in LABEL_SYNONYMS.items():
    for label in labels:
        _LOOKUP[collapse_ws(label).casefold()] = field


def canonical_field(label: str) -> str | None:
    key = collapse_ws(label).casefold()
    if key in _LOOKUP:
        return _LOOKUP[key]
    # Allow bilingual "English (Chinese)" by taking the part before '('.
    head = key.split("(")[0].strip()
    return _LOOKUP.get(head)
