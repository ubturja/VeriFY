# ADR 0002: Rules first, LLM second

## Status

Accepted

## Context

Shipping inboxes contain strong operational codes, and LLM calls are rate-limited on free tiers. False alarms on a Bill of Lading are expensive.

## Decision

A deterministic rules layer may auto-decide only when confidence is high and the signal is unambiguous. Every other case goes to a structured LLM call. The LLM is prompted with category *definitions*, not with examples copied from the sample inbox. Deterministic parsers fill fields they can read; the LLM fills gaps and never silently overrides a high-confidence parse.

## Consequences

- Sample-inbox subject codes accelerate the demo without locking the product to that generator.
- Novel emails still classify.
- LLM quota is spent where judgement is required.
