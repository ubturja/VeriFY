from enum import StrEnum


class Category(StrEnum):
    BL_COMPARISON = "BL_COMPARISON"
    SI_REQUEST = "SI_REQUEST"
    INVOICE_QUERY = "INVOICE_QUERY"
    GENERAL = "GENERAL"
    SPAM = "SPAM"


class Status(StrEnum):
    OK = "OK"
    MISMATCH = "MISMATCH"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ReviewReason(StrEnum):
    WRONG_DOC_TYPE = "wrong_doc_type"
    MISSING_ATTACHMENT = "missing_attachment"
    UNREADABLE = "unreadable"
    MISSING_VALUE = "missing_value"


class DecidedBy(StrEnum):
    RULE = "rule"
    LLM = "llm"
    HUMAN = "human"


class DocumentKind(StrEnum):
    SI = "SI"
    BL = "BL"
    INVOICE = "INVOICE"
    PACKING_LIST = "PACKING_LIST"
    CERTIFICATE_OF_ORIGIN = "CERTIFICATE_OF_ORIGIN"
    UNKNOWN = "UNKNOWN"
    UNREADABLE = "UNREADABLE"


class CompareIntent(StrEnum):
    COMPARE_ATTACHED = "compare_attached"
    REQUEST_DRAFT = "request_draft"
    UNKNOWN = "unknown"


COMPARE_FIELDS: tuple[str, ...] = (
    "shipper",
    "consignee",
    "notify_party",
    "port_of_loading",
    "port_of_discharge",
    "container_count",
    "gross_weight_kg",
)
