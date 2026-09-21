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
    <div className="section-blur-enter h-full overflow-y-auto space-y-6">
      <div>
        <p className="font-mono text-xs tracking-[0.25em] text-[#8a7470] uppercase mb-1">
          {t("submit.subtitle", "Upload")}
        </p>
        <h2 className="text-3xl font-display text-[#f0ebe9]">{t("submit.title", "Submit Email")}</h2>
      </div>

      <div className="card-glass rounded-xl p-8 max-w-2xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-[radial-gradient(ellipse_at_center,rgba(229,207,128,0.08)_0%,transparent_60%)] -mr-32 -mt-32 pointer-events-none blur-xl"></div>
        <form className="space-y-6 relative z-10" onSubmit={(e) => void onSubmit(e)}>
          {error && <p className="text-[#e5997e] font-mono text-xs">{error}</p>}

          <div className="space-y-2">
            <label className="text-xs font-mono text-[#8a7470] uppercase tracking-wide block">
              {t("submit.sender", "Sender")}
            </label>
            <input
              className="w-full text-sm px-4 py-3 rounded-lg transition-all focus:outline-none"
              style={{ background: "rgba(13,10,9,0.6)", border: "1px solid rgba(142,59,49,0.15)", color: "#f0ebe9" }}
              value={sender}
              onChange={(e) => setSender(e.target.value)}
              disabled={busy}
            />
          </div>

          <div className="space-y-2">
            <label className="text-xs font-mono text-[#8a7470] uppercase tracking-wide block">
              {t("submit.subject", "Subject")}
            </label>
            <input
              className="w-full text-sm px-4 py-3 rounded-lg transition-all focus:outline-none"
              style={{ background: "rgba(13,10,9,0.6)", border: "1px solid rgba(142,59,49,0.15)", color: "#f0ebe9" }}
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              required
              disabled={busy}
            />
          </div>

          <div className="space-y-2">
            <label className="text-xs font-mono text-[#8a7470] uppercase tracking-wide block">
              {t("submit.body", "Email Body / Raw Content")}
            </label>
            <textarea
              className="w-full text-sm px-4 py-3 rounded-lg transition-all focus:outline-none min-h-[160px]"
              style={{ background: "rgba(13,10,9,0.6)", border: "1px solid rgba(142,59,49,0.15)", color: "#f0ebe9", resize: "vertical" }}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              disabled={busy}
            />
          </div>

          <div className="space-y-2">
            <label className="text-xs font-mono text-[#8a7470] uppercase tracking-wide block">
              {t("submit.paths", "Attachment Paths (one per line)")}
            </label>
            <textarea
              className="w-full text-sm px-4 py-3 rounded-lg transition-all focus:outline-none min-h-[100px]"
              style={{ background: "rgba(13,10,9,0.6)", border: "1px solid rgba(142,59,49,0.15)", color: "#f0ebe9", resize: "vertical" }}
              value={paths}
              onChange={(e) => setPaths(e.target.value)}
              disabled={busy}
            />
          </div>

          <button
            type="submit"
            disabled={busy || !subject}
            className="w-full font-semibold px-4 py-3 rounded-lg transition-all hover:scale-[1.01] hover:brightness-110 disabled:opacity-50 cursor-pointer"
            style={{ background: 'linear-gradient(135deg, #8e3b31, #b8963a)', color: '#f0ebe9', boxShadow: '0 0 20px rgba(142,59,49,0.4)' }}
          >
            {busy ? t("submit.sending", "Injecting to Pipeline...") : t("submit.send", "Submit to AI Scanner")}
          </button>
        </form>
      </div>
    </div>
  );
}
