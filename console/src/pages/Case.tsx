import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api, COMPARE_FIELDS, type CaseRow } from "../api";
import { StatusPill } from "../components/StatusPill";

const CATEGORIES = ["BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM"] as const;
const STATUSES = ["OK", "MISMATCH", "NEEDS_REVIEW"] as const;
const REASONS = ["wrong_doc_type", "missing_attachment", "unreadable", "missing_value"] as const;

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
  }, [id]);

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

  return (
    <section>
      <Link to="/" className="muted">
        ← {t("case.back")}
      </Link>
      <div className="page-head" style={{ marginTop: 16 }}>
        <h1>{row.subject || row.email_id}</h1>
        <p>
          {row.from} · {t(`category.${row.result.category}`)}
        </p>
      </div>
      <div className="case-actions">
        <StatusPill status={row.result.status} />
        {row.result.review_reason ? (
          <span className="pill review">{row.result.review_reason}</span>
        ) : null}
        {confirmed ? <span className="pill confirmed">{t("case.confirmed")}</span> : null}
        {corrected ? <span className="pill corrected">{t("case.corrected")}</span> : null}
        <button
          className="btn secondary"
          type="button"
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
      </div>
      {error ? <p className="muted">{error}</p> : null}
      {reviewed && row.review ? (
        <p className="muted">
          {corrected
            ? t("case.correctedBy", {
                name: row.review.by,
                time: row.review.at.replace("T", " ").replace("Z", " UTC"),
              })
            : t("case.confirmedBy", {
                name: row.review.by,
                time: row.review.at.replace("T", " ").replace("Z", " UTC"),
              })}
          {row.review.note ? ` · ${row.review.note}` : ""}
        </p>
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
              {COMPARE_FIELDS.map((field) => (
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
            <button className="btn" type="submit" disabled={busy !== null}>
              {busy === "correct" ? t("case.correcting") : t("case.saveCorrection")}
            </button>
          </div>
        </form>
      ) : !reviewed ? (
        <label className="field" style={{ maxWidth: 420, marginBottom: 24 }}>
          <span className="muted">{t("case.note")}</span>
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder={t("case.noteHint")}
            disabled={busy !== null}
          />
        </label>
      ) : null}
      {row.attachments.length > 0 ? (
        <>
          <h2 style={{ fontSize: 16, fontWeight: 600 }}>{t("case.attachments")}</h2>
          <ul className="attachment-list">
            {row.attachments.map((item) => (
              <li key={`${item.path}-${item.filename}`}>{item.filename}</li>
            ))}
          </ul>
        </>
      ) : null}
      {comparisons.length === 0 ? (
        <p className="muted">
          {row.result.review_reason === "missing_attachment"
            ? t("case.missingDocs")
            : t("case.noCompare")}
        </p>
      ) : (
        <>
          <h2 style={{ fontSize: 16, fontWeight: 600 }}>{t("case.fields")}</h2>
          <div className="compare">
            <div className="head">Field</div>
            <div className="head">{t("case.si")}</div>
            <div className="head">{t("case.bl")}</div>
            <div className="head">Result</div>
            {comparisons.map((item) => (
              <div key={item.field} style={{ display: "contents" }}>
                <div>{item.field.replaceAll("_", " ")}</div>
                <div>{item.si_value ?? "-"}</div>
                <div>{item.bl_value ?? "-"}</div>
                <div>
                  {item.match === true ? "Match" : item.match === false ? "Differ" : "Unsure"}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
      <h2 style={{ fontSize: 16, fontWeight: 600, marginTop: 32 }}>{t("case.email")}</h2>
      <pre
        style={{
          whiteSpace: "pre-wrap",
          background: "var(--surface)",
          border: "1px solid var(--line)",
          borderRadius: 12,
          padding: 16,
        }}
      >
        {row.body}
      </pre>
    </section>
  );
}
