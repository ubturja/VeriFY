import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api, type CaseRow } from "../api";

export function QueuePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [rows, setRows] = useState<CaseRow[]>([]);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState<"replay" | "poll" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      const query = status ? `?status=${status}` : "";
      setRows(await api.cases(query));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load cases");
    }
  }

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 15000);
    return () => window.clearInterval(timer);
  }, [status]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter((row) =>
      `${row.email_id} ${row.subject} ${row.from}`.toLowerCase().includes(needle),
    );
  }, [rows, q]);

  async function replay() {
    setBusy("replay");
    setError(null);
    try {
      await api.replay();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Replay failed");
    } finally {
      setBusy(null);
    }
  }

  async function pollMailbox() {
    setBusy("poll");
    setError(null);
    try {
      await api.pollMailbox();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Mailbox poll failed");
    } finally {
      setBusy(null);
    }
  }

  const getStatusMeta = (st: string) => {
    if (st === "OK") return { color: "#7ecfa0", bg: "rgba(126,207,160,0.12)", border: "rgba(126,207,160,0.35)", label: "Clear" };
    if (st === "MISMATCH") return { color: "#e5997e", bg: "rgba(229,153,126,0.12)", border: "rgba(229,153,126,0.35)", label: "Mismatch" };
    if (st === "NEEDS_REVIEW") return { color: "#e5cf80", bg: "rgba(229,207,128,0.12)", border: "rgba(229,207,128,0.35)", label: "Review" };
    return { color: "#8a7470", bg: "rgba(138,116,112,0.12)", border: "rgba(138,116,112,0.35)", label: st };
  };

  return (
    <div className="section-blur-enter h-full overflow-y-auto space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <p className="font-mono text-xs tracking-[0.25em] text-[#8a7470] uppercase mb-1">
            {t("queue.subtitle", "Inbox")}
          </p>
          <h2 className="text-3xl font-display text-[#f0ebe9]">{t("queue.title", "Email Queue")}</h2>
        </div>
        
        <div className="flex flex-wrap gap-2 items-center">
          <input
            className="text-xs font-mono px-3 py-1.5 rounded-full transition-all focus:outline-none"
            style={{ background: "rgba(28,22,21,0.8)", border: "1px solid rgba(142,59,49,0.25)", color: "#e5cf80" }}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t("queue.search") || "Search emails..."}
          />
          {[
            { id: "", label: "All" },
            { id: "NEEDS_REVIEW", label: "Review" },
            { id: "MISMATCH", label: "Mismatch" },
            { id: "OK", label: "Clear" }
          ].map(f => {
            const active = status === f.id;
            const meta = f.id ? getStatusMeta(f.id) : { bg: "rgba(28,22,21,0.8)", border: "rgba(142,59,49,0.25)", color: "#8a7470" };
            return (
              <button key={f.id} onClick={() => setStatus(f.id)}
                className="text-xs font-mono px-3 py-1.5 rounded-full transition-all cursor-pointer"
                style={{
                  background: active ? (f.id ? meta.bg : "rgba(229,207,128,0.12)") : "rgba(28,22,21,0.8)",
                  border: `1px solid ${active ? (f.id ? meta.border : "rgba(229,207,128,0.4)") : "rgba(142,59,49,0.25)"}`,
                  color: active ? (f.id ? meta.color : "#e5cf80") : "#8a7470",
                }}>
                {f.label}
              </button>
            )
          })}
        </div>
      </div>

      <div className="flex gap-2">
          <button 
            onClick={() => void replay()} disabled={busy !== null}
            className="text-xs font-semibold px-4 py-2 rounded-lg transition-all hover:scale-105 disabled:opacity-50 cursor-pointer"
            style={{ background: 'linear-gradient(135deg, #8e3b31, #b8963a)', color: '#f0ebe9', boxShadow: '0 0 16px rgba(142,59,49,0.25)' }}>
            {busy === "replay" ? t("queue.replaying") : t("queue.replay")}
          </button>
          <button 
             onClick={() => void pollMailbox()} disabled={busy !== null}
             className="text-xs font-semibold px-4 py-2 rounded-lg transition-all hover:scale-105 disabled:opacity-50 cursor-pointer"
             style={{ background: 'rgba(126,207,160,0.15)', color: '#7ecfa0', border: '1px solid rgba(126,207,160,0.3)' }}>
              {busy === "poll" ? t("queue.polling") : t("queue.poll")}
          </button>
      </div>

      {error ? <p className="text-[#e5997e] font-mono text-xs">{error}</p> : null}

      <div className="space-y-2">
        {filtered.length === 0 && <div className="text-center py-10 text-xs font-mono text-[#8a7470]">{t("queue.empty")}</div>}
        {filtered.map((e) => {
          const m = getStatusMeta(e.result.status);
          const needsReview = e.result.status === "NEEDS_REVIEW" || e.result.status === "MISMATCH";
          return (
            <div key={e.email_id}
              onClick={() => navigate(`/cases/${e.email_id}`)}
              className="card-glass rounded-xl cursor-pointer transition-all duration-200 hover:border-[rgba(229,207,128,0.25)] overflow-hidden">
              <div className="p-4 flex items-center gap-4">
                <div className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-mono font-bold"
                  style={{ background: needsReview ? 'rgba(229,153,126,0.2)' : 'rgba(142,59,49,0.2)', color: needsReview ? '#e5997e' : '#e5cf80' }}>
                  {e.from[0]?.toUpperCase() || "?"}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-mono text-[#8a7470] truncate">{e.from}</p>
                  <p className="text-sm text-[#f0ebe9] font-medium truncate">{e.subject}</p>
                </div>
                <div className="flex items-center gap-4 flex-shrink-0">
                  <span className="text-xs font-mono px-2 py-0.5 rounded-sm font-medium tracking-wide"
                    style={{ color: m.color, background: m.bg, border: `1px solid ${m.border}` }}>
                    {m.label}
                  </span>
                  {e.review?.action === "confirm" && (
                    <span className="text-xs font-mono px-2 py-0.5 rounded-sm font-medium tracking-wide"
                      style={{ color: "#7ecfa0", background: "rgba(126,207,160,0.12)", border: "1px solid rgba(126,207,160,0.35)" }}>
                      Confirmed
                    </span>

                     )}
                  {e.review?.action === "correct" ? (
                    <span className="text-xs font-mono px-2 py-0.5 rounded-full text-[#e5cf80] border border-[rgba(229,207,128,0.25)] bg-[rgba(229,207,128,0.08)]">
                      {t("queue.corrected")}
                    </span>
                  ) : null}
                  <span className="text-xs text-[#8a7470] font-mono w-14 text-right">
                    {e.email_id}
                  </span>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
                  
  );
}
