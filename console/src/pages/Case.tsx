import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api, type CaseRow, COMPARE_FIELDS, } from "../api";

type Comparison = NonNullable<CaseRow["result"]["comparisons"]>[number];
type FieldEvidence = NonNullable<Comparison["si_evidence"]>;

const CATEGORIES = ["BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM"] as const;
const STATUSES = ["OK", "MISMATCH", "NEEDS_REVIEW"] as const;
const REASONS = ["wrong_doc_type", "missing_attachment", "unreadable", "missing_value"] as const;

function attachmentLeaf(path: string): string {
  const cleaned = path.replaceAll("\\", "/");
  const parts = cleaned.split("/");
  return parts[parts.length - 1] || path;
}

function renderEvidence(evidence: FieldEvidence | null | undefined) {
  if (!evidence) return null;
  const label = `${attachmentLeaf(evidence.attachment)} · ${evidence.locator}`;
  return (
    <div
      className="text-[11px] font-mono text-[#8a7470] mt-1 break-words"
      title={evidence.snippet || undefined}
    >
      {label}
    </div>
  );
}

export function CasePage() {
  const { t } = useTranslation();
  const { id } = useParams();
  const [row, setRow] = useState<CaseRow | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"confirm" | "retry" | "correct" | null>(null);
  const [note, setNote] = useState("");
  const [showCorrect, setShowCorrect] = useState(false);
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [reason, setReason] = useState("");
  const [defects, setDefects] = useState<string[]>([]);
  const [reply, setReply] = useState<{ subject: string; body: string; to: string } | null>(null);
  const [replyBusy, setReplyBusy] = useState(false);
  const [related, setRelated] = useState<{
    shipment_id: string | null;
    matches: {
      email_id: string;
      subject: string;
      status: string;
    }[];
  } | null>(null);

  useEffect(() => {
    if (!id) return;
    api
      .case(id)
      .then((next) => {
        setRow(next);
        setCategory(next.result.category);
        setStatus(next.result.status);
        setReason(next.result.review_reason ?? "");
        setDefects(next.result.defect_fields ?? []);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Not found"));
    api
      .related(id)
      .then(setRelated)
      .catch(() => setRelated(null));
  }, [id]);

  async function loadReply() {
    if (!id) return;
    setReplyBusy(true);
    try {
      setReply(await api.replyDraft(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reply draft failed");
    } finally {
      setReplyBusy(false);
    }
  }

  function applyRow(next: CaseRow) {
    setRow(next);
    setCategory(next.result.category);
    setStatus(next.result.status);
    setReason(next.result.review_reason ?? "");
    setDefects(next.result.defect_fields ?? []);
  }

  async function confirm() {
    if (!id) return;
    setBusy("confirm");
    setError(null);
    try {
      applyRow(await api.confirm(id, { note: note.trim() || undefined }));
      setNote("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Confirm failed");
    } finally {
      setBusy(null);
    }
  }

  async function retry() {
    if (!id) return;
    setBusy("retry");
    setError(null);
    try {
      applyRow(await api.retry(id));
      setShowCorrect(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Retry failed");
    } finally {
      setBusy(null);
    }
  }

  async function correct() {
    if (!id) return;
    setBusy("correct");
    setError(null);
    try {
      applyRow(
        await api.correct(id, {
          note: note.trim() || undefined,
          category,
          status,
          review_reason: status === "NEEDS_REVIEW" ? reason || undefined : undefined,
          defect_fields: status === "MISMATCH" ? defects : [],
        }),
      );
      setNote("");
      setShowCorrect(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Correct failed");
    } finally {
      setBusy(null);
    }
  }

  function toggleDefect(field: string) {
    setDefects((current) =>
      current.includes(field) ? current.filter((item) => item !== field) : [...current, field],
    );
  }

  if (error && !row) return <p className="muted">{error}</p>;
  if (!row) return <p className="muted">Loading…</p>;

  const comparisons = row.result.comparisons ?? [];
  const confirmed = row.review?.action === "confirm";
  const corrected = row.review?.action === "correct";
  const reviewed = confirmed || corrected;

  const ok = comparisons.filter((c) => c.match === true).length;
  const mismatch = comparisons.filter((c) => c.match === false).length;
  const unsure = comparisons.filter((c) => c.match == null).length;

  const compareFields = Array.from(new Set([...comparisons.map((c) => c.field), ...defects]));

  return (
    <div className="section-blur-enter h-full overflow-y-auto space-y-6">
      <Link to="/" className="text-sm font-mono text-[#8a7470] hover:text-[#e5cf80] transition-colors inline-block">
        ← {t("case.back")}
      </Link>

      <div>
        <p className="font-mono text-xs tracking-[0.25em] text-[#8a7470] uppercase mb-1">
          {row.from} · {t(`category.${row.result.category}`)}
        </p>
        <h2 className="text-3xl font-display text-[#f0ebe9]">{row.subject || row.email_id}</h2>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <span
          className="text-xs font-mono px-2 py-0.5 rounded-sm font-medium tracking-wide"
          style={{ background: "rgba(229,153,126,0.12)", border: "1px solid rgba(229,153,126,0.3)", color: "#e5cf80" }}
        >
          {row.result.status}
        </span>
        {row.result.review_reason && (
          <span
            className="text-xs font-mono px-2 py-0.5 rounded-sm font-medium tracking-wide"
            style={{ background: "rgba(229,207,128,0.12)", border: "1px solid rgba(229,207,128,0.35)", color: "#e5cf80" }}
          >
            {row.result.review_reason}
          </span>
        )}
        {confirmed && (
          <span
            className="text-xs font-mono px-2 py-0.5 rounded-sm font-medium tracking-wide"
            style={{ background: "rgba(126,207,160,0.12)", border: "1px solid rgba(126,207,160,0.35)", color: "#7ecfa0" }}
          >
            {t("case.confirmed")}
          </span>
        )}

        <button
          className="text-xs font-semibold px-4 py-2 rounded-lg transition-all hover:scale-105 disabled:opacity-50 cursor-pointer ml-auto"
          style={{ background: "linear-gradient(135deg, #8e3b31, #b8963a)", color: "#f0ebe9", boxShadow: "0 0 16px rgba(142,59,49,0.25)" }}
          onClick={() => void confirm()}
          disabled={busy !== null || reviewed}
        >
          {busy === "confirm" ? t("case.confirming") : t("case.confirm")}
        </button>
        <button
          className="btn secondary"
          type="button"
          onClick={() => setShowCorrect((open) => !open)}
          disabled={busy !== null}
        >
          {t("case.correct")}
        </button>
        <button
          className="btn secondary"
          type="button"
          onClick={() => void retry()}
          disabled={busy !== null}
        >
          {busy === "retry" ? t("case.retrying") : t("case.retry")}
        </button>
        <button
          className="btn secondary"
          type="button"
          onClick={() => void loadReply()}
          disabled={replyBusy}
        >
          {replyBusy ? t("case.replyLoading") : t("case.reply")}
        </button>
      </div>

      {reply ? (
        <section className="reply-panel">
          <div className="reply-head">
            <span>{t("case.replySubject")}: {reply.subject}</span>
            <span className="muted small">
              {t("case.replyTo")}: {reply.to || "-"}
            </span>
          </div>
          <textarea readOnly value={reply.body} />
          <div>
            <button
              className="btn secondary small"
              type="button"
              onClick={() => {
                void navigator.clipboard?.writeText(reply.body);
              }}
            >
              {t("case.copyReply")}
            </button>
            <button
              className="btn secondary small"
              type="button"
              onClick={() => setReply(null)}
              style={{ marginLeft: 8 }}
            >
              {t("case.dismissReply")}
            </button>
          </div>
        </section>
      ) : null}

      {related && related.matches.length ? (
        <section className="related">
          <h2 style={{ fontSize: 16, fontWeight: 600 }}>
            {t("case.related")}{" "}
            <span className="muted small">({related.shipment_id})</span>
          </h2>
          <ul>
            {related.matches.map((match) => (
              <li key={match.email_id}>
                <Link to={`/cases/${encodeURIComponent(match.email_id)}`}>
                  {match.subject || match.email_id}
                </Link>{" "}
                <span className="muted small">{match.status}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {error ? <p className="text-[#e5997e] font-mono text-sm">{error}</p> : null}

      {reviewed && row.review ? (
        <div className="card-glass rounded-xl p-4 text-xs font-mono text-[#8a7470]">
          <span className="text-[#e5cf80] font-semibold">
            {t(corrected ? "case.correctedBy" : "case.confirmedBy", {
              name: row.review.by,
              time: row.review.at.replace("T", " ").replace("Z", " UTC"),
            })}
          </span>
          {row.review.note && <span> · {row.review.note}</span>}
        </div>
      ) : null}

      {showCorrect ? (
        <form
          className="correct-panel"
          onSubmit={(event) => {
            event.preventDefault();
            void correct();
          }}
        >
          <p className="muted">{t("case.correctHint")}</p>
          <div className="correct-grid">
            <label className="field">
              <span>{t("case.category")}</span>
              <select value={category} onChange={(e) => setCategory(e.target.value)} disabled={busy !== null}>
                {CATEGORIES.map((item) => (
                  <option key={item} value={item}>
                    {t(`category.${item}`)}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>{t("case.status")}</span>
              <select value={status} onChange={(e) => setStatus(e.target.value)} disabled={busy !== null}>
                {STATUSES.map((item) => (
                  <option key={item} value={item}>
                    {t(`status.${item}`)}
                  </option>
                ))}
              </select>
            </label>
            {status === "NEEDS_REVIEW" ? (
              <label className="field">
                <span>{t("case.reason")}</span>
                <select value={reason} onChange={(e) => setReason(e.target.value)} disabled={busy !== null}>
                  {REASONS.map((item) => (
                    <option key={item} value={item}>
                      {item.replaceAll("_", " ")}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
          </div>
          {status === "MISMATCH" ? (
            <fieldset className="defect-fields">
              <legend>{t("case.defectFields")}</legend>
              {compareFields.map((field) => (
                <label key={field}>
                  <input
                    type="checkbox"
                    checked={defects.includes(field)}
                    onChange={() => toggleDefect(field)}
                    disabled={busy !== null}
                  />
                  {field.replaceAll("_", " ")}
                </label>
              ))}
            </fieldset>
          ) : null}
          <label className="field" style={{ maxWidth: 420 }}>
            <span className="muted">{t("case.note")}</span>
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder={t("case.correctNoteHint")}
              disabled={busy !== null}
            />
          </label>
          <div>
            <button
              className="text-xs font-semibold px-4 py-2 rounded-lg transition-all hover:scale-105 disabled:opacity-50 cursor-pointer"
              style={{ background: "linear-gradient(135deg, #8e3b31, #b8963a)", color: "#f0ebe9", boxShadow: "0 0 16px rgba(142,59,49,0.25)" }}
              type="submit"
              disabled={busy !== null}
            >
              {busy === "correct" ? t("case.correcting") : t("case.saveCorrection")}
            </button>
          </div>
        </form>
      ) : !reviewed ? (
        <div className="card-glass rounded-xl p-5 space-y-3">
          <p className="text-xs font-mono text-[#8a7470] uppercase tracking-wide">{t("case.note")}</p>
          <input
            className="w-full max-w-md text-sm px-3 py-2 rounded-lg transition-all focus:outline-none"
            style={{ background: "rgba(13,10,9,0.6)", border: "1px solid rgba(142,59,49,0.15)", color: "#f0ebe9" }}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder={t("case.noteHint")}
            disabled={busy !== null}
          />
        </div>
      ) : null}

      {comparisons.length === 0 ? (
        <div className="card-glass rounded-xl p-5 text-sm font-mono text-[#8a7470]">
          {row.result.review_reason === "missing_attachment"
            ? t("case.missingDocs")
            : t("case.noCompare")}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: "Matched", val: ok, color: "#7ecfa0", bg: "rgba(126,207,160,0.08)", border: "rgba(126,207,160,0.25)" },
              { label: "Discrepancies", val: mismatch, color: "#e5997e", bg: "rgba(229,153,126,0.08)", border: "rgba(229,153,126,0.3)" },
              { label: "Unsure", val: unsure, color: "#e5cf80", bg: "rgba(229,207,128,0.08)", border: "rgba(229,207,128,0.25)" },
            ].map((s) => (
              <div
                key={s.label}
                className="rounded-xl p-4 text-center"
                style={{ background: s.bg, border: `1px solid ${s.border}` }}
              >
                <p className="text-3xl font-semibold font-display" style={{ color: s.color }}>{s.val}</p>
                <p className="text-xs font-mono mt-1" style={{ color: s.color }}>{s.label}</p>
              </div>
            ))}
          </div>

          <h2 style={{ fontSize: 16, fontWeight: 600 }}>{t("case.fields")}</h2>

          <div className="card-glass rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b border-[rgba(142,59,49,0.2)] grid grid-cols-12 text-xs font-mono text-[#8a7470] uppercase tracking-wide">
              <div className="col-span-3">Field</div>
              <div className="col-span-3">{t("case.si")}</div>
              <div className="col-span-3">{t("case.bl")}</div>
              <div className="col-span-3 text-right">Result</div>
            </div>
            {comparisons.map((r) => {
              const isDisc = r.match === false;
              const isMissing = r.match == null;
              return (
                <div
                  key={r.field}
                  className="px-5 py-3.5 grid grid-cols-12 gap-2 items-start text-xs border-b border-[rgba(142,59,49,0.1)] transition-all hover:bg-[rgba(142,59,49,0.04)]"
                  style={{ background: isDisc ? "rgba(229,153,126,0.04)" : isMissing ? "rgba(229,207,128,0.03)" : undefined }}
                >
                  <div className="col-span-3 font-mono font-medium text-[#f0ebe9]">
                    {r.field.replaceAll("_", " ")}
                  </div>
                  <div className="col-span-3">
                    <div className="text-[#f0ebe9] leading-relaxed">{r.si_value ?? "—"}</div>
                    {renderEvidence(r.si_evidence)}
                  </div>
                  <div className="col-span-3">
                    <div style={{ color: isDisc ? "#e5997e" : isMissing ? "#e5cf80" : "#f0ebe9" }}>
                      {r.bl_value ?? <em className="text-[#8a7470]">not stated</em>}
                    </div>
                    {renderEvidence(r.bl_evidence)}
                  </div>
                  <div className="col-span-3 text-right">
                    {r.match === true && <span className="font-mono text-[#7ecfa0]">✓ Match</span>}
                    {r.match === false && <span className="font-mono text-[#e5997e] font-semibold">⚠ Differs</span>}
                    {r.match == null && <span className="font-mono text-[#e5cf80]">— Unsure</span>}
                    {r.note ? (
                      <p className="text-[11px] font-mono text-[#8a7470] mt-1 break-words">{r.note}</p>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {row.attachments.length > 0 && (
        <div className="card-glass rounded-xl p-5 space-y-3">
          <p className="text-sm font-semibold text-[#f0ebe9]">{t("case.attachments")}</p>
          <ul className="text-xs font-mono text-[#8a7470] space-y-1">
            {row.attachments.map((item) => (
              <li key={`${item.path}-${item.filename}`}>{item.filename}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="card-glass rounded-xl p-5 space-y-3">
        <p className="text-xs font-mono text-[#8a7470] uppercase tracking-wide">{t("case.email")}</p>
        <pre className="text-xs font-mono text-[#f0ebe9] whitespace-pre-wrap leading-relaxed max-h-96 overflow-y-auto w-full p-4 rounded-lg bg-[rgba(13,10,9,0.6)] border border-[rgba(142,59,49,0.15)]">
          {row.body}
        </pre>
      </div>
    </div>
  );
}