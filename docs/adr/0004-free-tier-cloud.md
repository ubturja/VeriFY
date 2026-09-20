# ADR 0004: Free-tier host until Azure credits exist

## Status

Accepted

## Context

The brief asks for a cloud-backed system. Azure for Students and the author's personal Microsoft account are not eligible for free credits, so Container Apps, Key Vault, and Static Web Apps cannot be the live demo. Paid hyperscaler trials that require a card are also out of scope.

## Decision

Run the public prototype on Render (Docker API) plus Cloudflare Pages or a Render static site (console). Keep Gemini and Groq behind `LLMProvider`. Keep Gmail IMAP as the live mailbox. Leave `infra/` Terraform as the Averis production mapping and do not delete it.

## Consequences

- Judges can open a URL without an Azure subscription.
- Cold starts replace scale-to-zero; the architecture document still describes KEDA on Container Apps as the production shape.
- Ephemeral free disks mean Confirm state should be replayable. Neon is the optional durable store.
- Switching to Azure later is configuration and Terraform apply, not a rewrite.
