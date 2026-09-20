# ADR 0003: Escalate instead of guessing

## Status

Accepted

## Context

The scoring model and Averis's own LC practice both treat a false mismatch as costly. Blank fields, scans without a text layer, and the wrong document type are not discrepancies.

## Decision

The gate emits `NEEDS_REVIEW` with one of `wrong_doc_type`, `missing_attachment`, `unreadable`, or `missing_value` whenever a comparison cannot be completed with high confidence. OCR of a scan produces a *proposed* comparison that still requires a human confirm.

## Consequences

- Reviewers see evidence and a reason, not a silent failure.
- The scoreboard's reliability axis is treated as a first-class product behaviour.
