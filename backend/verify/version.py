"""Versions stamped on every pipeline result and audit row.

PROMPT_VERSION changes when a prompt in classify, extract, judge, or doc-type
changes. MODEL_VERSION is the configured model name, filled at runtime; this
constant is the fallback when the run never called a model.
"""

PROMPT_VERSION = "2026-09-22"
RULES_MODEL_VERSION = "rules"
