# ADR 0001: Provider interfaces over vendor SDKs

## Status

Accepted

## Context

The prototype must run without paid Azure credits, while the production path Averis would use is Azure OpenAI, Document Intelligence, Service Bus, and a private network.

## Decision

All external systems are reached through small Python protocols (`LLMProvider`, `OCRProvider`, `MailSource`, `BlobStore`, `Queue`). Pipeline code never imports a vendor SDK. Configuration selects the implementation.

## Consequences

- Local eval and cloud deploy share one pipeline.
- Gemini can be replaced by Azure OpenAI without touching classification or extraction.
- Tests use in-memory fakes.
