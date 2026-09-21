from __future__ import annotations

from rapidfuzz import fuzz

from verify.domain.enums import COMPARE_FIELDS
from verify.domain.models import ExtractedDocument, ExtractedField, FieldComparison
from verify.domain.policy import MailboxPolicy
from verify.text.locode import canonical_port
from verify.text.normalize import (
    _is_noisy,
    fold_party,
    is_blank_token,
    parse_container_count,
    parse_weight_kg,
)

PARTY_FIELDS = {"shipper", "consignee", "notify_party"}
PORT_FIELDS = {"port_of_loading", "port_of_discharge"}


def compare_documents(
    si: ExtractedDocument,
    bl: ExtractedDocument,
    *,
    party_threshold: int = 90,
    policy: MailboxPolicy | None = None,
) -> list[FieldComparison]:
    rules = policy or MailboxPolicy()
    out: list[FieldComparison] = []
    for name in COMPARE_FIELDS:
        left = si.fields.get(name)
        right = bl.fields.get(name)
        item = _compare_field(
            name,
            left,
            right,
            party_threshold=party_threshold,
            weight_tolerance_kg=rules.weight_tolerance_kg,
        )
        if rules.allows_difference(name) and item.match is False:
            item.match = True
            item.note = "policy:allowed-difference"
        if left and left.evidence:
            item.si_evidence = left.evidence
        if right and right.evidence:
            item.bl_evidence = right.evidence
        out.append(item)
    return out


def _compare_field(
    name: str,
    left: ExtractedField | None,
    right: ExtractedField | None,
    *,
    party_threshold: int,
    weight_tolerance_kg: int = 0,
) -> FieldComparison:
    lv = left.value if left else None
    rv = right.value if right else None
    if (left and left.blank_token) or (right and right.blank_token) or is_blank_token(lv) or is_blank_token(rv):
        return FieldComparison(
            field=name,
            si_value=lv,
            bl_value=rv,
            match=None,
            confidence=0.2,
            note="blank",
        )
    if lv is None or rv is None:
        return FieldComparison(
            field=name,
            si_value=lv,
            bl_value=rv,
            match=None,
            confidence=0.3,
            note="missing",
        )

    if name == "container_count":
        a, b = parse_container_count(lv), parse_container_count(rv)
        ok = a is not None and b is not None and a == b
        return FieldComparison(field=name, si_value=lv, bl_value=rv, match=ok, confidence=0.95)

    if name == "gross_weight_kg":
        a, b = parse_weight_kg(lv), parse_weight_kg(rv)
        ok = a is not None and b is not None and abs(a - b) <= max(weight_tolerance_kg, 0)
        note = "tolerance" if ok and a != b else None
        return FieldComparison(field=name, si_value=lv, bl_value=rv, match=ok, confidence=0.95, note=note)

    if name in PORT_FIELDS:
        ok = canonical_port(lv) == canonical_port(rv)
        note = "locode" if ok and lv.casefold() != rv.casefold() else None
        return FieldComparison(field=name, si_value=lv, bl_value=rv, match=ok, confidence=0.93, note=note)

    if name in PARTY_FIELDS:
        if _is_noisy(lv) or _is_noisy(rv):
            return FieldComparison(
                field=name,
                si_value=lv,
                bl_value=rv,
                match=True,
                confidence=0.6,
                note="layout-noise",
            )
        a, b = fold_party(lv), fold_party(rv)
        if a == b:
            return FieldComparison(field=name, si_value=lv, bl_value=rv, match=True, confidence=0.97)
        score = fuzz.ratio(a, b)
        if score >= 97:
            return FieldComparison(
                field=name,
                si_value=lv,
                bl_value=rv,
                match=True,
                confidence=score / 100,
                note="near-identical",
            )
        return FieldComparison(
            field=name,
            si_value=lv,
            bl_value=rv,
            match=False,
            confidence=0.9,
            note=f"fuzzy:{score}",
        )

    return FieldComparison(
        field=name,
        si_value=lv,
        bl_value=rv,
        match=fold_party(lv) == fold_party(rv),
        confidence=0.8,
    )
