import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";

export function SubmitPage() {
  const { t } = useTranslation();
  const [data, setData] = useState({ subject: "", body: "" });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setMsg("");
    try {
      await api.submit(data);
      setMsg("Submitted successfully");
      setData({ subject: "", body: "" });
    } catch (err: unknown) {
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
         <form className="space-y-6 relative z-10" onSubmit={submit}>
            {error && <p className="text-[#e5997e] font-mono text-xs">{error}</p>}
            {msg && <p className="text-[#7ecfa0] font-mono text-xs">{msg}</p>}

            <div className="space-y-2">
              <label className="text-xs font-mono text-[#8a7470] uppercase tracking-wide block">Subject</label>
              <input
                className="w-full text-sm px-4 py-3 rounded-lg transition-all focus:outline-none"
                style={{ background: "rgba(13,10,9,0.6)", border: "1px solid rgba(142,59,49,0.15)", color: "#f0ebe9" }}
                value={data.subject}
                onChange={(e) => setData({ ...data, subject: e.target.value })}
                required
                disabled={busy}
              />
            </div>
            
            <div className="space-y-2">
              <label className="text-xs font-mono text-[#8a7470] uppercase tracking-wide block">Email Body / Raw Content</label>
              <textarea
                className="w-full text-sm px-4 py-3 rounded-lg transition-all focus:outline-none min-h-[200px]"
                style={{ background: "rgba(13,10,9,0.6)", border: "1px solid rgba(142,59,49,0.15)", color: "#f0ebe9", resize: "vertical" }}
                value={data.body}
                onChange={(e) => setData({ ...data, body: e.target.value })}
                required
                disabled={busy}
              />
            </div>

            <button
               type="submit" disabled={busy}
               className="w-full font-semibold px-4 py-3 rounded-lg transition-all hover:scale-[1.01] hover:brightness-110 disabled:opacity-50 cursor-pointer"
               style={{ background: 'linear-gradient(135deg, #8e3b31, #b8963a)', color: '#f0ebe9', boxShadow: '0 0 20px rgba(142,59,49,0.4)' }}
            >
              {busy ? "Injecting to Pipeline..." : "Submit to AI Scanner"}
            </button>
         </form>
      </div>
    </div>
  );
}
