from __future__ import annotations

import re
import unicodedata

BLANK_TOKENS = {
    "???",
    "_______",
    "tba",
    "tbc",
    "n/a",
    "na",
    "____mt",
    "-",
    "--",
    "null",
    "none",
}

_LEGAL_RE = re.compile(
    r"\b(pte\.?\s*ltd\.?|co\.?,?\s*ltd\.?|sdn\.?\s*bhd\.?|llc|gmbh|inc\.?|"
    r"ltd\.?|limited|joint stock company|fze|fz-llc|pty\.?\s*ltd\.?)\b",
    re.IGNORECASE,
)
_UNLOCODE_RE = re.compile(r"\(([A-Z]{2}[A-Z0-9]{3})\)")
_NON_ALNUM = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+")


def nfkc(value: str | None) -> str:
    if value is None:
        return ""
    return unicodedata.normalize("NFKC", value).strip()


def collapse_ws(value: str) -> str:
    return _WS.sub(" ", nfkc(value))


def is_blank_token(value: str | None) -> bool:
    text = collapse_ws(value).lower().replace(" ", "")
    if not text:
        return True
    return text in {token.replace(" ", "") for token in BLANK_TOKENS} or set(text) <= {"_", "?"}


def strip_unlocode(value: str) -> str:
    return collapse_ws(_UNLOCODE_RE.sub("", value))


def strip_legal_suffix(value: str) -> str:
    return collapse_ws(_LEGAL_RE.sub("", value))


def fold_party(value: str) -> str:
    text = strip_legal_suffix(value).casefold()
    text = _NON_ALNUM.sub(" ", text)
    return collapse_ws(text)


def fold_port(value: str) -> str:
    return collapse_ws(strip_unlocode(value)).casefold()


def parse_int(value: str | None) -> int | None:
    if value is None or is_blank_token(value):
        return None
    match = re.search(r"(\d[\d,]*)", nfkc(value))
    if not match:
        return None
    try:
        return int(match.group(1).replace(",", ""))
    except ValueError:
        return None


def parse_weight_kg(value: str | None) -> int | None:
    if value is None or is_blank_token(value):
        return None
    text = nfkc(value)
    match = re.search(r"([\d,.]+)\s*(mt|mts|t|tonnes?|kg|kgs)?", text, re.IGNORECASE)
    if not match:
        return parse_int(text)
    number = match.group(1).replace(",", "")
    try:
        amount = float(number)
    except ValueError:
        return None
    unit = (match.group(2) or "kg").lower()
    if unit in {"mt", "mts", "t", "tonne", "tonnes"}:
        amount *= 1000
    return int(round(amount))


def parse_container_count(value: str | None) -> int | None:
    if value is None or is_blank_token(value):
        return None
    text = nfkc(value)
    match = re.search(r"(\d+)\s*[xX×]", text)
    if match:
        return int(match.group(1))
    return parse_int(text)


_LEGAL_END = re.compile(
    r"^(.*?\b(?:pte\.?\s*ltd\.?|co\.?,?\s*ltd\.?|sdn\.?\s*bhd\.?|llc|gmbh|inc\.?|"
    r"ltd\.?|limited|fze|fz-llc|pty\.?\s*ltd\.?|joint stock company)\b)",
    re.IGNORECASE,
)
_ADDRESS_CUT = re.compile(
    r"(?:\s+p\.?o\.?\s*box|\s+on behalf of|\s+#\d|\s+\blot\b|\s+\bjalan\b|"
    r"\s+\broad\b|\s+\bstreet\b|\s+\bavenue\b|\s+\btower\b|\s+\bplaza\b|"
    r"\s+\bno\.?\s+\d|\s+\d{2,})",
    re.IGNORECASE,
)


def party_name_only(value: str | None) -> str:
    if not value:
        return ""
    text = collapse_ws(value.replace("|", " ").replace("\n", " "))
    legal = _LEGAL_END.search(text)
    if legal:
        return collapse_ws(legal.group(1))
    cut = _ADDRESS_CUT.search(text)
    if cut:
        text = text[: cut.start()]
    return collapse_ws(text)


def _is_noisy(value: str | None) -> bool:
    if not value:
        return True
    compact = re.sub(r"[^A-Za-z]", "", value)
    if len(compact) >= 8:
        up = sum(1 for ch in compact if ch.isupper())
        lo = sum(1 for ch in compact if ch.islower())
        if lo and up / max(len(compact), 1) > 0.55 and re.search(r"[a-z][A-Z][a-z][A-Z]", compact):
            return True
    return "intermediate cons" in value.casefold()

