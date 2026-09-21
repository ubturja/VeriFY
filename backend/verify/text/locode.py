"""UN/LOCODE lookup for the ports this inbox actually uses.

`PORT KLANG (MYPKG)` and a bare `MYPKG` both resolve to the same canonical
name. Unknown strings fall through to the existing fold, so a port that is
not in the table still compares exactly as before.
"""

from __future__ import annotations

import re

from verify.text.normalize import collapse_ws, fold_port

# (canonical folded name, locode, extra surface forms)
_PORTS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("singapore", "SGSIN", ("singapore",)),
    ("nantong", "CNNTG", ("nantong",)),
    ("shanghai", "CNSHA", ("rugao/nantong/shanghai", "shanghai")),
    ("port klang", "MYPKG", ("port klang", "port klang (westport)", "westport")),
    ("nhava sheva", "INNSA", ("nhava sheva", "nhava sheva (jawaharlal nehru)")),
    ("buatan", "IDBUA", ("buatan",)),
    ("jebel ali", "AEJEA", ("jebel ali",)),
    ("mombasa", "KEMBA", ("mombasa",)),
    ("tuticorin", "INTUT", ("tuticorin",)),
    ("klaipeda", "LTKLJ", ("klaipeda",)),
    ("houston", "USHOU", ("houston",)),
    ("new york", "USNYC", ("new york",)),
    ("long beach", "USLGB", ("long beach",)),
    ("savannah", "USSAV", ("savannah",)),
    ("baltimore", "USBAL", ("baltimore",)),
    ("ho chi minh city", "VNSGN", ("hochiminh city", "ho chi minh city", "ho chi minh")),
    ("pyeongtaek", "KRPTK", ("pyeongtaek",)),
    ("busan", "KRPUS", ("busan", "pusan")),
    ("koper", "SIKOP", ("koper",)),
    ("gdansk", "PLGDN", ("gdansk",)),
    ("mersin", "TRMER", ("mersin",)),
    ("ashdod", "ILASH", ("ashdod",)),
    ("apapa", "NGAPP", ("apapa",)),
    ("conakry", "GNCKY", ("conakry",)),
    ("valparaiso", "CLVAP", ("valparaiso",)),
    ("callao", "PECLL", ("callao",)),
    ("fremantle", "AUFRE", ("fremantle",)),
    ("brisbane", "AUBNE", ("brisbane",)),
    ("yangon", "MMRGN", ("yangon",)),
    ("karachi", "PKKHI", ("karachi",)),
    ("aqaba", "JOAQB", ("aqaba",)),
    ("cebu", "PHCEB", ("cebu",)),
    ("hamburg", "DEHAM", ("hamburg",)),
    ("rotterdam", "NLRTM", ("rotterdam",)),
    ("tanjung priok", "IDTPP", ("tanjung priok",)),
    ("osaka", "JPOSA", ("osaka",)),
    ("penang", "MYPEN", ("penang",)),
    ("guangzhou", "CNGZG", ("guangzhou",)),
    ("gothenburg", "SEGOT", ("gothenburg", "goteborg")),
)

BY_CODE: dict[str, str] = {}
BY_NAME: dict[str, str] = {}
for canonical, code, names in _PORTS:
    BY_CODE[code] = canonical
    BY_NAME[canonical] = canonical
    for name in names:
        BY_NAME[fold_port(name)] = canonical

_CODE_RE = re.compile(r"\b([A-Z]{2}[A-Z0-9]{3})\b")


def _known_name(value: str) -> str | None:
    folded = fold_port(value)
    if not folded:
        return None
    if folded in BY_NAME:
        return BY_NAME[folded]
    head = folded.split(",")[0].strip()
    if head in BY_NAME:
        return BY_NAME[head]
    return None


def _embedded_code(value: str) -> str | None:
    upper = collapse_ws(value).upper()
    if re.fullmatch(r"[A-Z]{2}[A-Z0-9]{3}", upper) and upper in BY_CODE:
        return BY_CODE[upper]
    for match in _CODE_RE.finditer(upper):
        code = match.group(1)
        if code in BY_CODE:
            return BY_CODE[code]
    return None


def canonical_port(value: str | None) -> str:
    """Resolve a port to one comparable name.

    A bare code and a name that carries the same code are the same port.
    When the written name is a different known port from the code in
    parentheses, the name wins. The generator keeps the original code
    after it changes the port name, and that stale code must not hide
    the defect.
    """
    if not value:
        return ""
    code_name = _embedded_code(value)
    written = _known_name(value)
    if written and code_name and written != code_name:
        return written
    if code_name:
        return code_name
    if written:
        return written
    return fold_port(value)
