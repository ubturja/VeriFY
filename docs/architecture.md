# Architecture

VeriFY is an event-driven verification service. A mail source emits messages. A pipeline classifies, extracts, compares, and either records a verdict or opens a review case. The console is the human interface for those cases.

## Runtime view

```
Sign-in (any Gmail address + app password)  -->  mailbox tenant
MailSource (hackathon folder | HTTP inbox | that mailbox's IMAP | manual submit)
        |
        v
   Ingest  -->  object store (raw email + attachments)
        |
        v
   File job queue (retry, then dead letter)  -->  Pipeline orchestrator
                           |
           +---------------+---------------+
           |               |               |
        Classify        Doc-type        Extract
           |               |               |
           +-------+-------+-------+-------+
                   |               |
              Normalise        Compare
                   |               |
                   +-------+-------+
                           |
                     Confidence gate
                           |
              OK | MISMATCH | NEEDS_REVIEW
                           |
        Per-mailbox case store, audit log, webhook record
```

Each pipeline stage is a pure function of typed domain objects. Providers (LLM, OCR, blob, queue, mail) are interfaces. Local implementations run on a laptop. Azure implementations are swapped by configuration.

## Design constraints

- **No dataset-specific hardcoding.** Subject codes from the sample inbox are a high-confidence shortcut, not the definition of a category. Unknown layouts fall through to structured LLM extraction.
- **Unicode-clean.** All text is NFKC-normalised. Comparison is script-aware. The console ships fonts that render Latin, CJK, and Arabic.
- **Fail visibly.** Parser crashes, empty files, and low-confidence fields become `NEEDS_REVIEW` with a reason. They are never silent passes.
- **Evidence-linked output.** Every extracted field stores file, location, and span so a reviewer can see why the system decided.

## Scaling sketch

Ingestion is object-storage backed and queue-driven. Workers scale on queue depth (KEDA on Azure Container Apps). The LLM is off the hot path: rules and deterministic parsers handle the majority of emails. Idempotency keys on message id make retries safe.

This is the same shape that supports tens of millions of messages per day. Azure Container Apps with KEDA is the Averis production mapping. Until Azure credits exist, the public demo runs on Render (scale-to-sleep) with the same container and APIs. See [docs/cloud.md](cloud.md).

## Cloud mapping

| Concern | Local | Hackathon cloud | Averis Azure |
| --- | --- | --- | --- |
| Compute | Docker / uvicorn | Render free Web Service (Docker) | Container Apps |
| Database | Postgres 16 | Neon free (optional) | Flexible Server |
| Blobs | filesystem or Azurite | container disk | Blob Storage |
| Queue | file job queue with dead letters | same file on the container disk | Service Bus |
| OCR | Tesseract (`eng`, `chi_sim`, `msa`) | Tesseract in the image | Document Intelligence F0 |
| LLM | rules on the scoreboard; Gemini, then Groq, on live mail | same, keys in host env | same providers, keys in Key Vault |
| Console | Vite. `/` is welcome, `/queue` is the desk | Cloudflare Pages or Render static | Static Web Apps |
| Review | Confirm / Correct per mailbox. JSON or SQLite | same, ephemeral disk | persisted store + audit |

## Human review

- **Confirm** stamps who accepted the current machine verdict. Category, status, and defect fields do not change.
- **Correct** is the override. The reviewer sets category, status, and defect fields. `decided_by` becomes `human`. The previous machine values are kept on the review stamp.
- **Retry** re-runs the pipeline and clears the review stamp.
- A correction stores the exact party-name pair and refits `party_model.json` for that mailbox. The model may note that two gray-band names look like the same entity. It does not change `match`. Only the exact stored correction does.

## Mail ingest

Sign-in is a Gmail address plus an app password. There is no built-in mailbox. IMAP poll for that mailbox skips message ids already in the case store and marks a message seen only after ingest succeeds. Background polling uses `UNSEEN`. **Poll mailbox** also reads recent mail that is already seen, and still skips ids that have been ingested. A failed job retries, then appears on the dead-letter list.

`make eval` and the multi-seed scorer pass no model. Gemini and Groq are used on live mail only.

Azure OpenAI is the intended production model host inside Averis's tenant. It is not available on Azure for Students, so the prototype uses Gemini with a Groq fallback behind the same `LLMProvider` interface. `infra/` stays as the Terraform mapping; it is not required to run the demo.

