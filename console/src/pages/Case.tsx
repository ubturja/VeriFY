import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api, type CaseRow } from "../api";

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

  if (error && !row) return <p className="text-[#e5997e] font-mono text-sm">{error}</p>;
  if (!row) return (
    <div className="section-blur-enter text-center mt-10">
      <div className="flex justify-center gap-1.5 mt-8">
          {[0, 1, 2, 3, 4].map(i => (
              <div key={i} className="w-1.5 h-1.5 rounded-full"
                  style={{ background: '#e5cf80', animation: `pulse 1s ease-in-out ${i * 0.12}s infinite alternate`, opacity: 0.4 }} />
          ))}
      </div>
      <p className="text-xs font-mono text-[#8a7470] mt-4">Loading case data...</p>
    </div>
  );

  const comparisons = row.result.comparisons ?? [];
  const confirmed = row.review?.action === "confirm";
  
  const ok = comparisons.filter((c) => c.match === true).length;
  const mismatch = comparisons.filter((c) => c.match === false).length;
  const unsure = comparisons.filter((c) => c.match === null).length;

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
        <span className="text-xs font-mono px-2 py-0.5 rounded-sm font-medium tracking-wide"
          style={{ background: 'rgba(229,153,126,0.12)', border: '1px solid rgba(229,153,126,0.3)', color: '#e5cf80' }}>
          {row.result.status}
        </span>
        {row.result.review_reason && (
          <span className="text-xs font-mono px-2 py-0.5 rounded-sm font-medium tracking-wide"
            style={{ background: 'rgba(229,207,128,0.12)', border: '1px solid rgba(229,207,128,0.35)', color: '#e5cf80' }}>
            {row.result.review_reason}
          </span>
        )}
        {confirmed && (
          <span className="text-xs font-mono px-2 py-0.5 rounded-sm font-medium tracking-wide"
            style={{ background: 'rgba(126,207,160,0.12)', border: '1px solid rgba(126,207,160,0.35)', color: '#7ecfa0' }}>
            {t("case.confirmed")}
          </span>
        )}
        
        <button
          className="text-xs font-semibold px-4 py-2 rounded-lg transition-all hover:scale-105 disabled:opacity-50 cursor-pointer ml-auto"
          style={{ background: 'linear-gradient(135deg, #8e3b31, #b8963a)', color: '#f0ebe9', boxShadow: '0 0 16px rgba(142,59,49,0.25)' }}
          onClick={() => void confirm()}
          disabled={busy !== null || confirmed}
        >
          {busy === "confirm" ? t("case.confirming") : t("case.confirm")}
        </button>
        <button
          className="text-xs font-semibold px-4 py-2 rounded-lg transition-all hover:scale-105 disabled:opacity-50 cursor-pointer"
          style={{ background: 'rgba(28,22,21,0.8)', border: '1px solid rgba(142,59,49,0.25)', color: '#e5cf80' }}
          onClick={() => void retry()}
          disabled={busy !== null}
        >
          {busy === "retry" ? t("case.retrying") : t("case.retry")}
        </button>
      </div>

      {error ? <p className="text-[#e5997e] font-mono text-sm">{error}</p> : null}

      {confirmed && row.review ? (
        <div className="card-glass rounded-xl p-4 text-xs font-mono text-[#8a7470]">
          <span className="text-[#e5cf80] font-semibold">Reviewed by {row.review.by} </span>
          at {row.review.at.replace("T", " ").replace("Z", " UTC")}
          {row.review.note && <span> · Note: {row.review.note}</span>}
        </div>
      ) : (
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
      )}

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
              { label: 'Matched', val: ok, color: '#7ecfa0', bg: 'rgba(126,207,160,0.08)', border: 'rgba(126,207,160,0.25)' },
              { label: 'Discrepancies', val: mismatch, color: '#e5997e', bg: 'rgba(229,153,126,0.08)', border: 'rgba(229,153,126,0.3)' },
              { label: 'Unsure', val: unsure, color: '#e5cf80', bg: 'rgba(229,207,128,0.08)', border: 'rgba(229,207,128,0.25)' },
            ].map(s => (
              <div key={s.label} className="rounded-xl p-4 text-center"
                style={{ background: s.bg, border: `1px solid ${s.border}` }}>
                <p className="text-3xl font-semibold font-display" style={{ color: s.color }}>{s.val}</p>
                <p className="text-xs font-mono mt-1" style={{ color: s.color }}>{s.label}</p>
              </div>
            ))}
          </div>

          <div className="card-glass rounded-xl overflow-hidden">
            <div className="px-5 py-3 border-b border-[rgba(142,59,49,0.2)] grid grid-cols-12 text-xs font-mono text-[#8a7470] uppercase tracking-wide">
              <div className="col-span-3">Field</div>
              <div className="col-span-3">SI Value</div>
              <div className="col-span-3">BL Value</div>
              <div className="col-span-3 text-right">Result</div>
            </div>
            {comparisons.map(r => {
              const isDisc = r.match === false;
              const isMissing = r.match === null;
              return (
                <div key={r.field}
                  className="px-5 py-3.5 grid grid-cols-12 gap-2 items-start text-xs border-b border-[rgba(142,59,49,0.1)] transition-all hover:bg-[rgba(142,59,49,0.04)]"
                  style={{ background: isDisc ? 'rgba(229,153,126,0.04)' : isMissing ? 'rgba(229,207,128,0.03)' : undefined }}>
                  <div className="col-span-3 font-mono font-medium text-[#f0ebe9]">{r.field.replaceAll("_", " ")}</div>
                  <div className="col-span-3 text-[#f0ebe9] leading-relaxed">{r.si_value ?? "—"}</div>
                  <div className="col-span-3" style={{ color: isDisc ? '#e5997e' : isMissing ? '#e5cf80' : '#f0ebe9' }}>
                    {r.bl_value ?? <em className="text-[#8a7470]">not stated</em>}
                  </div>
                  <div className="col-span-3 text-right">
                    {r.match === true && <span className="font-mono text-[#7ecfa0]">✓ Match</span>}
                    {r.match === false && <span className="font-mono text-[#e5997e] font-semibold">⚠ Differs</span>}
                    {r.match === null && <span className="font-mono text-[#e5cf80]">— Unsure</span>}
                  </div>
                </div>
              )
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
          <pre className="text-xs font-mono text-[#f0ebe9] whitespace-pre-wrap leading-relaxed max-height-96 overflow-y-auto w-full p-4 rounded-lg bg-[rgba(13,10,9,0.6)] border border-[rgba(142,59,49,0.15)]">
              {row.body}
          </pre>
      </div>

    </div>
  );
}
