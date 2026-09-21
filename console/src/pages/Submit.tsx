import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api, type SubmitAttachment } from "../api";

function readAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || "");
      const comma = result.indexOf(",");
      resolve(comma >= 0 ? result.slice(comma + 1) : result);
    };
    reader.onerror = () => reject(reader.error ?? new Error("Unable to read file"));
    reader.readAsDataURL(file);
  });
}

export function SubmitPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [sender, setSender] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [paths, setPaths] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const attachments: SubmitAttachment[] = paths
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .map((path) => ({ path, filename: path.split("/").pop() }));
      for (const file of files) {
        attachments.push({
          filename: file.name,
          content_base64: await readAsBase64(file),
        });
      }
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
          {t("submit.files")}
          <input
            type="file"
            multiple
            onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
          />
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
