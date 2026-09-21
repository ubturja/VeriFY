import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api, type CaseRow } from "../api";
import { StatusPill } from "../components/StatusPill";

export function CasePage() {
  const { t } = useTranslation();
  const { id } = useParams();
  const [row, setRow] = useState<CaseRow | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"confirm" | "retry" | null>(null);
  const [note, setNote] = useState("");

  useEffect(() => {
    if (!id) return;
    api
      .case(id)
      .then(setRow)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Not found"));
  }, [id]);

  async function confirm() {
    if (!id) return;
    setBusy("confirm");
    setError(null);
    try {
      setRow(await api.confirm(id, { note: note.trim() || undefined }));
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
      setRow(await api.retry(id));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Retry failed");
    } finally {
      setBusy(null);
    }
  }

  if (error && !row) return <p className="muted">{error}</p>;
  if (!row) return <p className="muted">Loading…</p>;

  const comparisons = row.result.comparisons ?? [];
  const confirmed = row.review?.action === "confirm";

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
        <button
          className="btn secondary"
          type="button"
          onClick={() => void confirm()}
          disabled={busy !== null || confirmed}
        >
          {busy === "confirm" ? t("case.confirming") : t("case.confirm")}
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
      {confirmed && row.review ? (
        <p className="muted">
          {t("case.confirmedBy", { name: row.review.by, time: row.review.at.replace("T", " ").replace("Z", " UTC") })}
          {row.review.note ? ` · ${row.review.note}` : ""}
        </p>
      ) : (
        <label className="field" style={{ maxWidth: 420, marginBottom: 24 }}>
          <span className="muted">{t("case.note")}</span>
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder={t("case.noteHint")}
            disabled={busy !== null}
          />
        </label>
      )}
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
                <div>{item.si_value ?? "—"}</div>
                <div>{item.bl_value ?? "—"}</div>
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
