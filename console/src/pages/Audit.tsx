import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api, type AuditEvent } from "../api";

export function AuditPage() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<AuditEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .audit()
      .then(setRows)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unable to load audit"));
  }, []);

  return (
    <div className="section-blur-enter h-full overflow-y-auto space-y-6">
      <div>
        <p className="font-mono text-xs tracking-[0.25em] text-[#8a7470] uppercase mb-1">
          {t("audit.subtitle", "Compliance")}
        </p>
        <h2 className="text-3xl font-display text-[#f0ebe9]">{t("audit.title", "Audit Log")}</h2>
      </div>

      {error && <p className="text-[#e5997e] font-mono text-sm">{error}</p>}

      {rows.length === 0 ? (
        <div className="text-center py-10 text-xs font-mono text-[#8a7470]">
          {t("audit.empty")}
        </div>
      ) : (
        <div className="card-glass rounded-xl overflow-hidden">
          <div className="grid grid-cols-12 gap-3 px-6 py-3 text-xs font-mono text-[#8a7470] uppercase tracking-wide border-b border-[rgba(142,59,49,0.2)]">
            <div className="col-span-3">{t("audit.when")}</div>
            <div className="col-span-2">{t("audit.case")}</div>
            <div className="col-span-3">{t("audit.action")}</div>
            <div className="col-span-4">{t("audit.by")}</div>
          </div>
          {[...rows].reverse().map((row, index) => (
            <div
              key={`${row.at}-${row.email_id}-${index}`}
              className="grid grid-cols-12 gap-3 px-6 py-4 text-xs border-b border-[rgba(142,59,49,0.1)] transition-all hover:bg-[rgba(142,59,49,0.04)]"
            >
              <div className="col-span-3 font-mono text-[#8a7470]">
                {row.at.replace("T", " ").replace("Z", " UTC")}
              </div>
              <div className="col-span-2 font-mono text-[#e5cf80]">
                <Link to={`/cases/${encodeURIComponent(row.email_id)}`} className="hover:underline">
                  {row.email_id}
                </Link>
              </div>
              <div className="col-span-3 font-semibold text-[#f0ebe9]">
                {row.action}
              </div>
              <div className="col-span-4 text-[#8a7470] truncate">
                <span className="text-[#f0ebe9]">{row.by}</span>
                {row.note ? <span className="ml-2 font-mono italic">· {row.note}</span> : null}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
