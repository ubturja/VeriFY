import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api";

export function SubmitPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [sender, setSender] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [paths, setPaths] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const attachments = paths
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .map((path) => ({ path, filename: path.split("/").pop() }));
      const row = await api.submit({ sender, subject, body, attachments });
      navigate(`/cases/${row.email_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submit failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <div className="page-head">
        <h1>{t("submit.title")}</h1>
        <p>{t("submit.subtitle")}</p>
      </div>
      <form className="stack" onSubmit={(e) => void onSubmit(e)}>
        <label className="field">
          {t("submit.sender")}
          <input value={sender} onChange={(e) => setSender(e.target.value)} />
        </label>
        <label className="field">
          {t("submit.subject")}
          <input value={subject} onChange={(e) => setSubject(e.target.value)} />
        </label>
        <label className="field">
          {t("submit.body")}
          <textarea value={body} onChange={(e) => setBody(e.target.value)} />
        </label>
        <label className="field">
          {t("submit.paths")}
          <textarea value={paths} onChange={(e) => setPaths(e.target.value)} />
        </label>
        {error ? <p className="muted">{error}</p> : null}
        <div>
          <button className="btn" disabled={busy || !subject}>
            {busy ? t("submit.sending") : t("submit.send")}
          </button>
        </div>
      </form>
    </section>
  );
}
